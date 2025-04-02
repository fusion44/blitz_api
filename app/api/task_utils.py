from loguru import logger
from redis.asyncio import Redis

from app.api.error_report.report import Frame, Report
from app.api.utils import redis_delete, redis_get_raw, redis_set
from app.external.result_type.src.result.result import Err, Ok, Result


async def get_lock_status(key: str, redis: Redis | None = None) -> Result[bool, Report]:
    """
    Checks if the update lock is held.
    Returns True if lock is held.
    """
    logger.trace(f"get_lock_status({key})")

    result = await redis_get_raw(key, custom_redis=redis)
    match result:
        case Ok(None):
            logger.debug(f"Lock for key {key} not held.")
            return Ok(False)
        case Ok(data) if isinstance(data, bytes) and data.decode("utf-8") == "locked":
            logger.debug(f"Lock held for key {key}.")
            return Ok(True)
        case Ok(data) if not isinstance(data, bytes):
            return Err(Report(message=f"Unexpected data from Redis: {data}"))
        case Err(e):
            logger.error(f"Error checking if lock is held for key {key}: %s", e)
            return Err(e)

    return Err(Report(message=f"Error checking if lock is held for key {key}"))


async def acquire_lock(
    key: str, lock_ttl: int, redis: Redis | None = None
) -> Result[bool, Report]:
    """
    Attempts to acquire a lock to prevent concurrent updates.
    Returns True if lock acquired.
    """
    logger.trace(f"acquire_lock({key})")

    result = await get_lock_status(key, redis)
    match result:
        case Ok(lock_status):
            if lock_status:
                return Ok(False)
        case Err(report):
            return Err(report)

    # nx: Only set the key if it does not already exist.
    # ex: Set the specified expire time, in seconds.
    # TODO: should this even timeout automatically?
    #       do we need to do some cleanup if the status update takes too long?
    match await redis_set(
        key,
        "locked",
        nx=True,
        ex=lock_ttl,
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


async def release_update_lock(
    key: str, redis: Redis | None = None
) -> Result[None, Report]:
    """Releases the update lock."""
    logger.trace(f"release_update_lock({key})")
    match await redis_delete(key, custom_redis=redis):
        case Ok(_):
            return Ok(None)
        case Err(report):
            return Err(
                report.attach_frame(
                    Frame(message=f"Error releasing lock in Redis for {key}")
                )
            )
