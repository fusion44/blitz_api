"""
This module defines a Celery task `update_app_state_task_impl` responsible for updating
the application state cache and notifying changes via a Redis channel. The task performs
the following operations:

1. Initializes a Redis client and logs an error if initialization fails.
2. Attempts to acquire a lock to ensure only one instance of the task runs at a time.
3. Connects to a Redis channel for notifications.
4. Fetches the latest application status using the platform-specific implementation.
5. Updates the application status cache in Redis.
6. Notifies the Redis channel about the status update or any errors encountered.
7. Releases the lock after the task is completed, ensuring proper cleanup.

The task handles various error scenarios, logging detailed error messages and notifying
the Redis channel about failures.
"""

from typing import Optional

from loguru import logger
from redis.asyncio import Redis
from redis.asyncio import from_url as redis_from_url

from app.api.channel import BaseChannelNotifier
from app.api.config import config
from app.api.error_report.report import Report
from app.api.models import ApiErrors, ErrorMessage
from app.api.task_utils import acquire_lock, release_update_lock
from app.apps.constants import (
    AppManagementProcessState,
    AppsServiceKeys,
)
from app.apps.models import (
    AppStatusUpdateTaskMessage,
    CacheOperations,
)
from app.external.result_type.src.result import Err, Ok
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

LOCK_TTL_SECONDS = int(config("BAPI_LOCK_TTL_SECONDS", default=5 * 60))
if not isinstance(LOCK_TTL_SECONDS, int):
    raise TypeError("BAPI_LOCK_TTL_SECONDS must be an integer")


async def update_app_state_task_impl(
    redis_url: str, cache_ops: Optional[CacheOperations] = None
):
    if cache_ops is None:
        from app.apps.cache import cache

        cache_ops = cache

    logger.debug("update_app_state_task_impl: Starting task...")

    redis_client = None
    try:
        redis_client = redis_from_url(redis_url, decode_responses=True)
    except Exception as e:
        logger.error(f"Failed to initialize Redis client: {e}")
        logger.info("Attempting to run update_app_state_task...")

    if not isinstance(redis_client, Redis):
        raise Exception("Redis not properly initialized, got a Sentinel")

    result = await acquire_lock(
        key=AppsServiceKeys.APP_STATUS_LOCK_KEY,
        lock_ttl=LOCK_TTL_SECONDS,
        redis=redis_client,
    )
    match result:
        case Ok(acquired) if not acquired:
            logger.warning("App state update lock already held. Skipping task run.")
            return await redis_client.close()
        case Err(report):
            logger.error(f"Failed to acquire update lock: {report.format_verbose()}")
            return await redis_client.close()

    channel_notifier = BaseChannelNotifier(
        AppsServiceKeys.APP_STATUS_CHANNEL_KEY, redis_url=redis_url
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

    res = await channel_notifier.send_message(
        AppsServiceKeys.APP_STATUS_MESSAGE_KEY,
        contents=AppStatusUpdateTaskMessage(
            state=AppManagementProcessState.INITIATED,
            message=None,
        ).model_dump_json(),
    )
    match res:
        case Err(message):
            _log_notify_listeners_error(message)

    try:
        logger.info("App state update lock acquired. Fetching app status...")

        apps_impl = Apps()
        result = await apps_impl.get_app_status()
        match result:
            case Ok(data):
                logger.info("Successfully fetched app status.")
                res = await cache_ops.set_cached_app_status(data, redis_client)
                match res:
                    case Ok(_):
                        res = await channel_notifier.send_message(
                            AppsServiceKeys.APP_STATUS_MESSAGE_KEY,
                            contents=AppStatusUpdateTaskMessage(
                                state=AppManagementProcessState.SUCCESS,
                                message=data,
                            ).model_dump_json(),
                        )
                        match res:
                            case Err(message):
                                _log_notify_listeners_error(message)
                    case Err(report):
                        logger.error(
                            f"Failed to update app status cache: "
                            f"{report.format_verbose()}"
                        )
                        match await channel_notifier.send_message(
                            AppsServiceKeys.APP_STATUS_MESSAGE_KEY,
                            contents=AppStatusUpdateTaskMessage(
                                state=AppManagementProcessState.FAILURE,
                                message=ErrorMessage(
                                    error_code=ApiErrors.APP_STATUS_UPDATE_FAILED,
                                    detail="Unexpected error during app status update.",
                                    report=report.format(),
                                ),
                            ).model_dump_json(),
                        ):
                            case Err(message):
                                _log_notify_listeners_error(message)
            case Err(report):
                logger.error(f"Failed to fetch app status: {report.format()}")
                match await channel_notifier.send_message(
                    AppsServiceKeys.APP_STATUS_MESSAGE_KEY,
                    contents=AppStatusUpdateTaskMessage(
                        state=AppManagementProcessState.FAILURE,
                        message=ErrorMessage(
                            error_code=ApiErrors.APP_STATUS_UPDATE_FAILED,
                            detail="Unexpected error during app status update.",
                            report=report.format(),
                        ),
                    ).model_dump_json(),
                ):
                    case Err(message):
                        _log_notify_listeners_error(message)

    except Exception as e:
        logger.exception(f"Unexpected error during update_app_state_task: {e}")
        error_report = Report(
            f"Unexpected error during app status update: {str(e)}", error=e
        )

        match await channel_notifier.send_message(
            AppsServiceKeys.APP_STATUS_MESSAGE_KEY,
            contents=AppStatusUpdateTaskMessage(
                state=AppManagementProcessState.FAILURE,
                message=ErrorMessage(
                    error_code=ApiErrors.APP_STATUS_UPDATE_FAILED,
                    detail="Unexpected error during app status update.",
                    report=error_report.format_verbose(),
                ),
            ).model_dump_json(),
        ):
            case Err(message):
                _log_notify_listeners_error(message)

    finally:
        res = await release_update_lock(
            key=AppsServiceKeys.APP_STATUS_LOCK_KEY, redis=redis_client
        )
        match res:
            case Ok(_):
                logger.debug("App state update lock released.")
            case Err(report):
                logger.error(
                    f"Failed to release app status update lock: {report.format()}"
                )
                match await channel_notifier.send_message(
                    AppsServiceKeys.APP_STATUS_MESSAGE_KEY,
                    contents=AppStatusUpdateTaskMessage(
                        state=AppManagementProcessState.FAILURE,
                        message=ErrorMessage(
                            error_code=ApiErrors.APP_STATUS_UPDATE_FAILED,
                            detail=f"Failed to release app status update lock:"
                            f" {report.frames[0].message}",
                        ),
                    ).model_dump_json(),
                ):
                    case Err(message):
                        _log_notify_listeners_error(message)

        logger.debug("App state update lock released.")

    match await channel_notifier.send_message(
        AppsServiceKeys.APP_STATUS_MESSAGE_KEY,
        contents=AppStatusUpdateTaskMessage(
            state=AppManagementProcessState.FINISHED,
            message=None,
        ).model_dump_json(),
    ):
        case Err(message):
            _log_notify_listeners_error(message)

    await channel_notifier.aclose()
    if redis_client:
        await redis_client.aclose()


def _log_notify_listeners_error(message: Report):
    logger.error(
        f"Failed to notify Redis channel update state task message: {message.format()}"
    )
