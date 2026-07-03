"""
This module contains the caching implementation for app status data.

It provides functions to retrieve, store, and monitor app status data in Redis.
"""

import asyncio
from typing import Optional

from loguru import logger
from redis.asyncio import Redis

from app.api.config import config
from app.api.error_report.report import Report
from app.api.models import ErrorMessage
from app.api.utils import redis_get, redis_get_raw, redis_set
from app.apps.constants import AppsServiceKeys
from app.apps.models import AppStatusQueryResult, CacheOperations
from app.external.result_type.src.result import Err, Ok, Result
from app.logging import configure_logger

CACHE_TTL_SECONDS = int(config("BAPI_CACHE_TTL_SECONDS", default=35 * 60))
if not isinstance(CACHE_TTL_SECONDS, int):
    raise TypeError("BAPI_CACHE_TTL_SECONDS must be an integer")


configure_logger()


class AppCache(CacheOperations):
    """
    Implementation of the CacheOperations interface for app status caching.
    """

    async def get_cached_app_status(
        self,
        redis: Redis | None = None,
    ) -> Result[Optional[AppStatusQueryResult], Report]:
        """Retrieves the cached app status from Redis."""
        logger.trace("get_cached_app_status()")
        try:
            result = await redis_get_raw(
                AppsServiceKeys.APP_STATUS_MESSAGE_KEY, custom_redis=redis
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
                    message=f"Error retrieving app status from Redis cache: {e}",
                    error=e,
                )
            )

    async def set_cached_app_status(
        self,
        status: AppStatusQueryResult,
        redis: Redis | None = None,
    ) -> Result[None, Report]:
        """Stores the app status in the Redis cache."""
        logger.trace("set_cached_app_status()")
        try:
            json_data = status.model_dump_json()
            match await redis_set(
                AppsServiceKeys.APP_STATUS_MESSAGE_KEY,
                json_data,
                ex=CACHE_TTL_SECONDS,
                custom_redis=redis,
            ):
                case Ok(_):
                    logger.debug(
                        "App status cache updated. "
                        f"Key: {AppsServiceKeys.APP_STATUS_MESSAGE_KEY}"
                    )
                case Err(e):
                    logger.error(
                        "Error storing app status in Redis cache."
                        f"Key: {AppsServiceKeys.APP_STATUS_MESSAGE_KEY}"
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
                f"App status cache updated. Key: {AppsServiceKeys.APP_STATUS_MESSAGE_KEY}"
            )

            return Ok(None)
        except Exception as e:
            return Err(
                Report(message="Error storing app status in Redis cache", error=e)
            )


cache = AppCache()


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


async def watch_app_status_changes():
    """
    Listens for app status changes on the custom Redis channel.
    This function implements the channel listener for app state changes.
    """
    # import the listener here to avoid circular imports
    from app.apps.tasks_impl.listeners import AppStatusUpdateListener

    logger.info("Starting app status channel listener")

    try:
        while True:
            listener = AppStatusUpdateListener()
            match await listener.connect():
                case Err(report):
                    logger.error(
                        f"App status listener failed to connect: {report.format()}"
                    )
                    await listener.aclose()
                    # back off before retrying so a Redis outage doesn't
                    # spin this loop
                    await asyncio.sleep(5)
                    continue
            # This will loop forever (listen() closes its own resources)
            await listener.listen()
            logger.error("Recreating app status channel listener, as it stopped!")
            await asyncio.sleep(1)

    except Exception as e:
        return Err(Report(f"App status channel listener error: {e}", error=e))
