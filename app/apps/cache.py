import json
from typing import Optional

from loguru import logger
from redis.asyncio import Redis

from app.api.channel import BaseChannelListener
from app.api.config import config
from app.api.error_report.report import Frame, Report
from app.api.models import ErrorMessage
from app.api.utils import (
    SSE,
    broadcast_sse_msg,
    redis_delete,
    redis_get,
    redis_get_raw,
    redis_set,
)
from app.apps.constants import AppsServiceActions, AppsServiceKeys
from app.apps.models import AppStatusQueryResult
from app.external.result_type.src.result.result import Err, Ok, Result
from app.logging import configure_logger

CACHE_TTL_SECONDS = int(config("BAPI_CACHE_TTL_SECONDS", default=35 * 60))
if not isinstance(CACHE_TTL_SECONDS, int):
    raise TypeError("BAPI_CACHE_TTL_SECONDS must be an integer")

LOCK_TTL_SECONDS = int(config("BAPI_LOCK_TTL_SECONDS", default=5 * 60))
if not isinstance(LOCK_TTL_SECONDS, int):
    raise TypeError("BAPI_LOCK_TTL_SECONDS must be an integer")

configure_logger()


BAPI_REDIS_URL = config("BAPI_REDIS_URL", "redis://127.0.0.1:6379/0")
if BAPI_REDIS_URL == "":
    raise Exception("BAPI_REDIS_URL is not set")


class _AppsChannelListener(BaseChannelListener):
    def __init__(self):
        super().__init__(AppsServiceKeys.APP_STATE_CHANNEL, BAPI_REDIS_URL)

    async def handle_event(self, event):
        """Process app state change events from the Redis channel"""
        logger.debug(f"Received app state event: {event}")

        key = action = new_value = None
        try:
            key = event.get("key")
            action = event.get("action")
            new_value = event.get("new_value")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse channel event JSON data: {e}")
        except KeyError as e:
            logger.error(f"Missing required key in channel event: {e}")
        except Exception as e:
            logger.exception(f"Unexpected error handling channel event: {e}")

        if not key or not action:
            logger.error("Missing key or action in channel event")
            return

        match (key, action):
            case (AppsServiceKeys.APP_STATUS_CACHE_KEY, AppsServiceActions.STARTED):
                await broadcast_sse_msg(SSE.APP_STATE_UPDATING, None)
            case (AppsServiceKeys.APP_STATUS_CACHE_KEY, AppsServiceActions.UPDATED):
                try:
                    if new_value:
                        parsed_status = json.loads(new_value)
                        await broadcast_sse_msg(SSE.INSTALLED_APP_STATUS, parsed_status)
                        await broadcast_sse_msg(SSE.APP_STATE_UPDATING_SUCCESS, None)
                        logger.info(
                            "App state updated via channel and broadcasted to clients"
                        )
                    else:
                        logger.warning("Received app status update with no value")
                except Exception as e:
                    logger.error(f"Failed to process app status update: {e}")
            case (
                AppsServiceKeys.APP_STATUS_UPDATE_FAILED_KEY,
                AppsServiceActions.ERROR,
            ):
                try:
                    if new_value:
                        error_payload = json.loads(new_value)
                        await broadcast_sse_msg(
                            SSE.APP_STATE_UPDATE_ERROR, error_payload
                        )
                        logger.info("App state update error broadcasted to clients")
                    else:
                        logger.warning("Received app status error with no value")
                except Exception as e:
                    logger.error(f"Failed to process app status error: {e}")
            case (AppsServiceKeys.APP_STATUS_LOCK_KEY, AppsServiceActions.LOCKED):
                logger.debug(f"Received lock status change: {action}")
            case _:
                logger.warning(
                    f"Received unknown channel event - key: {key}, action: {action}"
                )


async def watch_app_status_changes() -> Result[None, Report]:
    """
    Listens for app status changes on the custom Redis channel.
    This function implements the channel listener for app state changes.
    """

    logger.info("Starting app status channel listener")

    try:
        listener = _AppsChannelListener()
        await listener.connect()
        # This will loop forever
        await listener.listen()

    except Exception as e:
        return Err(Report(f"App status channel listener error: {e}", error=e))

    logger.info("App status channel listener stopped")
    return Ok(None)


async def get_cached_app_status(
    redis: Redis | None = None,
) -> Result[Optional[AppStatusQueryResult], Report]:
    """Retrieves the cached app status from Redis."""
    logger.trace("get_cached_app_status()")
    try:
        result = await redis_get_raw(
            AppsServiceKeys.APP_STATUS_CACHE_KEY, custom_redis=redis
        )
        match result:
            case Ok(None):
                logger.debug("App status cache not hit.")
                return Ok(None)
            case Ok(data) if isinstance(data, str) and data:
                logger.debug("App status cache hit.")
                data = AppStatusQueryResult.model_validate_json(data)
            case Ok(data):
                logger.error(f"Error decoding app status from Redis cache: {data}")
                return Err(
                    Report(f"Error decoding app status from Redis cache: {data}")
                )
            case Err(e):
                logger.error(f"Error getting app status from Redis cache: {e}")
                return Err(e)

        return Ok(data)
    except Exception as e:
        return Err(
            Report(
                message=f"Error retrieving app status from Redis cache: {e}", error=e
            )
        )


async def set_cached_app_status_failed(
    error: ErrorMessage,
    redis: Redis | None = None,
) -> Result[None, Report]:
    """Stores the app status update failure in the Redis cache."""
    logger.trace("set_cached_app_status_failed()")
    try:
        match await redis_set(
            AppsServiceKeys.APP_STATUS_UPDATE_FAILED_KEY,
            error.model_dump_json(),
            ex=CACHE_TTL_SECONDS,
            custom_redis=redis,
        ):
            case Ok(_):
                logger.debug(
                    f"App status update failure cache updated. "
                    f"Key: {AppsServiceKeys.APP_STATUS_UPDATE_FAILED_KEY}"
                )
                return Ok(None)
            case Err(e):
                logger.error(
                    "Error storing app status update failure in Redis cache."
                    f"Key: {AppsServiceKeys.APP_STATUS_UPDATE_FAILED_KEY}"
                )
                return Err(e)
    except Exception as e:
        return Err(
            Report(
                message=f"Error storing app status update failure in Redis cache: {e}",
                error=e,
            )
        )


async def set_cached_app_status(
    status: AppStatusQueryResult,
    redis: Redis | None = None,
) -> Result[None, Report]:
    """Stores the app status in the Redis cache."""
    logger.trace("set_cached_app_status()")
    try:
        json_data = status.model_dump_json()
        match await redis_set(
            AppsServiceKeys.APP_STATUS_CACHE_KEY,
            json_data,
            ex=CACHE_TTL_SECONDS,
            custom_redis=redis,
        ):
            case Ok(_):
                logger.debug(
                    "App status cache updated. "
                    f"Key: {AppsServiceKeys.APP_STATUS_CACHE_KEY}"
                )
            case Err(e):
                logger.error(
                    "Error storing app status in Redis cache."
                    f"Key: {AppsServiceKeys.APP_STATUS_CACHE_KEY}"
                )
                return Err(e)

        match await redis_set(
            AppsServiceKeys.APP_STATUS_TIMESTAMP_KEY,
            status.timestamp,
            custom_redis=redis,
            ex=CACHE_TTL_SECONDS,
        ):
            case Ok(_):
                logger.debug(
                    "App status cache updated. "
                    f"Key: {AppsServiceKeys.APP_STATUS_TIMESTAMP_KEY}"
                )
            case Err(e):
                logger.error(
                    "Error storing app status in Redis cache."
                    f"Key: {AppsServiceKeys.APP_STATUS_TIMESTAMP_KEY}"
                )
                return Err(e)

        logger.debug(
            f"App status cache updated. Key: {AppsServiceKeys.APP_STATUS_CACHE_KEY}"
        )

        return Ok(None)
    except Exception as e:
        return Err(Report(message="Error storing app status in Redis cache", error=e))


async def get_cache_timestamp(
    redis: Redis | None = None,
) -> Result[Optional[int], Report]:
    """Retrieves the timestamp of the last cache update."""
    logger.trace("get_cache_timestamp()")
    try:
        timestamp_str = await redis_get(
            AppsServiceKeys.APP_STATUS_TIMESTAMP_KEY, custom_redis=redis
        )
        if timestamp_str is None or timestamp_str == "":
            return Ok(None)

        timestamp = int(timestamp_str)
        if not isinstance(timestamp, int):
            return Err(
                Report(message="Unable to convert timestamp to an int from Redis")
            )

        return Ok(timestamp if timestamp else None)
    except Exception as e:
        return Err(
            Report(message="Error retrieving cache timestamp from Redis", error=e)
        )


async def get_lock_status(redis: Redis | None = None) -> Result[bool, Report]:
    """
    Checks if the update lock is held.
    Returns True if lock is held.
    """
    logger.trace("get_lock_status()")
    result = await redis_get_raw(
        AppsServiceKeys.APP_STATUS_LOCK_KEY, custom_redis=redis
    )
    match result:
        case Ok(None):
            logger.debug("App status update lock not held.")
            return Ok(False)
        case Ok(data) if isinstance(data, bytes) and data.decode("utf-8") == "locked":
            logger.debug("App status update lock held.")
            return Ok(True)
        case Ok(data) if not isinstance(data, bytes):
            return Err(Report(message=f"Unexpected data from Redis: {data}"))
        case Err(e):
            logger.error("Error checking if app status update lock is held: %s", e)
            return Err(e)

    return Err(Report(message="Error checking if app status update lock is held"))


async def acquire_update_lock(redis: Redis | None = None) -> Result[bool, Report]:
    """
    Attempts to acquire a lock to prevent concurrent updates.
    Returns True if lock acquired.
    """
    logger.trace("acquire_update_lock()")

    result = await get_lock_status(redis)
    match result:
        case Ok(lock_status):
            if lock_status:
                return Ok(False)
        case Err(report):
            return Err(report)

    # nx: Only set the key if it does not already exist.
    # ex: Set the specified expire time, in seconds.
    match await redis_set(
        AppsServiceKeys.APP_STATUS_LOCK_KEY,
        "locked",
        nx=True,
        ex=LOCK_TTL_SECONDS,
        custom_redis=redis,
    ):
        case Ok(_):
            return Ok(True)
        case Err(report):
            return Err(
                report.attach_frame(
                    Frame(message="Error acquiring update lock in Redis")
                )
            )

    return Err(Report(message="Error acquiring update lock in Redis"))


async def release_update_lock(redis: Redis | None = None) -> Result[None, Report]:
    """Releases the update lock."""
    logger.trace("release_update_lock()")
    match await redis_delete(AppsServiceKeys.APP_STATUS_LOCK_KEY, custom_redis=redis):
        case Ok(_):
            return Ok(None)
        case Err(report):
            return Err(
                report.attach_frame(
                    Frame(message="Error releasing update lock in Redis")
                )
            )
