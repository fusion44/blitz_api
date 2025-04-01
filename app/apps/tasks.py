"""
This module defines a Celery task `update_app_state_task` responsible for updating the
application state cache and notifying changes via a Redis channel. The task performs
the following operations:

1. Checks if a Redis client is available and logs an error if not.
2. Attempts to acquire a lock to ensure only one instance of the task runs at a time.
3. Connects to a Redis channel for notifications.
4. Fetches the latest application status using the platform-specific implementation.
5. Updates the application status cache in Redis.
6. Notifies the Redis channel about the status update or any errors encountered.
7. Releases the lock after the task is completed, ensuring proper cleanup.

The task handles various error scenarios, logging detailed error messages and notifying
the Redis channel about failures.
"""

import asyncio
import json
from typing import Optional

from loguru import logger
from redis.asyncio import Redis
from redis.asyncio import from_url as redis_from_url

from app.api.channel import BaseChannelNotifier
from app.api.config import config
from app.api.error_report.report import Report
from app.api.models import ApiErrors, ErrorMessage
from app.apps.cache import (
    acquire_update_lock,
    release_update_lock,
    set_cached_app_status,
)
from app.apps.constants import AppsServiceActions, AppsServiceKeys
from app.celery_app import celery_app
from app.external.result_type.src.result import Err, Ok, Result
from app.system.models import APIPlatform

PLATFORM = config("BAPI_PLATFORM", default=APIPlatform.UNKNOWN)
if PLATFORM == APIPlatform.RASPIBLITZ:
    from app.apps.impl.raspiblitz import RaspiBlitzApps as Apps
elif PLATFORM == APIPlatform.NATIVE_PYTHON:
    from app.apps.impl.native_python import NativePythonApps as Apps
else:
    raise RuntimeError(
        f"Unsupported platform '{PLATFORM}'. Options: {APIPlatform.values_as_list()}."
    )


apps_impl = Apps()

BAPI_REDIS_URL = config("BAPI_REDIS_URL", "redis://127.0.0.1:6379/0")

if BAPI_REDIS_URL == "":
    raise Exception("BAPI_REDIS_URL is not set")


@celery_app.task(name="app.apps.tasks.update_app_state_task")
def update_app_state_task():
    """
    Celery task to fetch the latest app status, update the cache
    and notify on Redis channel.
    """
    asyncio.run(_update_app_state_task())


async def _update_app_state_task():
    redis_client = None
    try:
        redis_client = redis_from_url(BAPI_REDIS_URL, decode_responses=False)
    except Exception as e:
        logger.error(f"Failed to initialize Redis client: {e}")
        logger.info("Attempting to run update_app_state_task...")

    if not isinstance(redis_client, Redis):
        raise Exception("Redis not properly initialized, got a Sentinel")

    result = await acquire_update_lock(redis_client)
    match result:
        case Ok(acquired) if not acquired:
            logger.warning("App state update lock already held. Skipping task run.")
            return await redis_client.close()
        case Err(report):
            logger.error(f"Failed to acquire update lock: {report.format_verbose()}")
            return await redis_client.close()

    channel_notifier = BaseChannelNotifier(
        AppsServiceKeys.APP_STATE_CHANNEL, redis_url=BAPI_REDIS_URL
    )
    result = await channel_notifier.connect()
    match result:
        case Ok(_):
            logger.info("App state channel connected.")
        case Err(report):
            logger.error(
                f"Failed to connect to app state channel: {report.format_verbose()}"
            )
            return await redis_client.close()

    try:
        logger.info("App state update lock acquired. Fetching app status...")

        await channel_notifier.notify_key_change(
            AppsServiceKeys.APP_STATUS_CACHE_KEY, AppsServiceActions.STARTED
        )

        result = await apps_impl.get_app_status()
        match result:
            case Ok(data):
                logger.info("Successfully fetched app status.")
                res = await set_cached_app_status(data, redis_client)
                match res:
                    case Ok(_):
                        res = await channel_notifier.notify_key_change(
                            AppsServiceKeys.APP_STATUS_CACHE_KEY,
                            AppsServiceActions.UPDATED,
                            None,
                            data.model_dump_json(),
                        )
                        _handle_result(res)
                    case Err(report):
                        logger.error(
                            f"Failed to update app status cache: "
                            f"{report.format_verbose()}"
                        )
                        await _handle_task_error(
                            channel_notifier,
                            AppsServiceKeys.APP_STATUS_UPDATE_FAILED_KEY,
                            AppsServiceActions.ERROR,
                            f"Failed to update app status cache: "
                            f"{report.frames[0].message}",
                            ApiErrors.APP_STATUS_UPDATE_FAILED,
                            report,
                        )
            case Err(report):
                logger.error(f"Failed to fetch app status: {report.format()}")
                await _handle_task_error(
                    channel_notifier,
                    AppsServiceKeys.APP_STATUS_UPDATE_FAILED_KEY,
                    AppsServiceActions.ERROR,
                    f"Failed to update app status: {report.frames[0].message}",
                    ApiErrors.APP_STATUS_UPDATE_FAILED,
                    report,
                )

    except Exception as e:
        logger.exception(f"Unexpected error during update_app_state_task: {e}")
        error_report = Report(
            f"Unexpected error during app status update: {str(e)}", error=e
        )
        await _handle_task_error(
            channel_notifier,
            AppsServiceKeys.APP_STATUS_UPDATE_FAILED_KEY,
            AppsServiceActions.ERROR,
            f"Unexpected error during app status update: {str(e)}",
            ApiErrors.BACKGROUND_TASK_FAILED,
            error_report,
        )

    finally:
        res = await release_update_lock(redis=redis_client)
        match res:
            case Ok(_):
                logger.debug("App state update lock released.")
            case Err(report):
                logger.error(
                    f"Failed to release app status update lock: {report.format()}"
                )
                await _handle_task_error(
                    channel_notifier,
                    AppsServiceKeys.APP_STATUS_LOCK_KEY,
                    AppsServiceActions.LOCK_ERROR,
                    "Failed to release app status update lock:"
                    f" {report.frames[0].message}",
                    ApiErrors.APP_STATUS_UPDATE_FAILED,
                    report,
                )
        logger.debug("App state update lock released.")

    if redis_client:
        await redis_client.close()


def _handle_result(res):
    """Simple helper to log result of operations"""
    match res:
        case Ok(_):
            logger.info("App status cache updated.")
        case Err(report):
            logger.error(
                f"Failed to update app status cache: {report.format_verbose()}"
            )


async def _handle_task_error(
    channel_notifier: BaseChannelNotifier,
    key: str,
    action: str,
    error_message: str,
    error_code: str,
    report: Optional[Report] = None,
) -> Result[None, Report]:
    """Centralized error handling for tasks with channel notification

    Parameters
    ----------
    channel_notifier : BaseChannelNotifier
        The channel notifier to use for sending the error notification
    key : str
        The key to use for the notification
    action : str
        The action to use for the notification
    error_message : str
        The error message to include in the notification
    error_code : str
        The error code to include in the notification
    report : Optional[Report]
        The error report to include in the notification, if any

    Returns
    -------
    Result[None, Report]
        The result of the notification operation
    """
    try:
        error_payload = ErrorMessage(
            detail=error_message,
            error_code=error_code,
            report=report.format_verbose() if report else None,
        ).model_dump()

        return await channel_notifier.notify_key_change(
            key,
            action,
            None,
            json.dumps(error_payload),
        )
    except Exception as e:
        logger.exception(f"Error handling task error: {e}")
        return Err(Report(f"Error handling task error: {e}", error=e))
