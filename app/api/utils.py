import array
import asyncio
import json
import os
import random
import re
import time
from typing import Any, Dict, Optional

from fastapi.encoders import jsonable_encoder
from loguru import logger
# NB: do not import redis's TimeoutError here — it would shadow the builtin
# and asyncio.wait_for's builtin TimeoutError would never be caught below.
from redis.asyncio import Redis

from app.api.error_report.report import Report
from app.api.models import ProcessResult
from app.api.sse_manager import SSEManager
from app.external.fastapi_plugins_redis import redis_plugin
from app.external.result_type.src.result import Err, Ok, Result
from app.external.sse_starlette import ServerSentEvent

sse_mgr = SSEManager()


def build_sse_event(event: str, json_data: Optional[Dict]):
    return ServerSentEvent(
        event=event,
        data=json.dumps(jsonable_encoder(json_data)),
    )


async def broadcast_sse_msg(event: str, json_data: Optional[Dict]):
    """Broadcasts a message to all connected clients

    Parameters
    ----------
    event : str
        The SSE event
    data : dictionary, optional
        The data to include
    """

    await sse_mgr.broadcast_to_all(build_sse_event(event, json_data))


async def redis_set(
    key: str,
    value: str | bytes | int | float,
    nx: bool = False,
    ex: int | None = None,
    custom_redis: Redis | None = None,
) -> Result[None, Report]:
    """Set the value at key `name` to `value`

    Parameters
    ----------
    name: str
        The key to set
    value: str | bytes | int | float
        The value to set
    nx : bool
        If set to True, set the value at `key` to `value` only
        if it does not exist.
    ex : int
        sets an expire flag on `key` for `ex` seconds.
    custom_redis: Redis | None
        The custom Redis instance to use.
        If None, the default Redis instance will be used.
    """
    logger.trace(f"redis_set(key={key}, value={value}, nx={nx}, ex={ex})")

    try:
        redis = None
        if custom_redis:
            redis = custom_redis
        else:
            redis = redis_plugin.redis
            if not isinstance(redis, Redis):
                return Err(
                    Report(
                        f"Redis not initialized, got a {type(redis)}",
                        error=RuntimeError(
                            f"Redis not initialized, got a {type(redis)}"
                        ),
                    )
                )

        result = await redis.set(name=key, value=value, nx=nx, ex=ex)
        if result is None:
            return Err(Report(message=f"SET operation failed for key {key}"))
        return Ok(None)
    except TypeError as e:
        return Err(Report(message=f"Invalid Redis value type: {e}", error=e))
    except ValueError as e:
        return Err(Report(message=f"Invalid Redis key: {e}", error=e))
    except RuntimeError as e:
        return Err(Report(message=f"Redis SET operation failed: {e}", error=e))
    except Exception as e:
        return Err(Report(message=f"Unexpected error setting key {key}: {e}", error=e))


# TODO: return type should be bytes | str | int | float
async def redis_get(key: str, custom_redis: Redis | None = None) -> Any:
    """Get the value at key `name`

    Parameters
    ----------
    name: str
        The key to get
    custom_redis: Redis | None
        The custom Redis instance to use.
        If None, the default Redis instance will be used.
    """

    redis = None
    if custom_redis:
        redis = custom_redis
    else:
        redis = redis_plugin.redis
        if not isinstance(redis, Redis):
            raise Exception("Redis not initialized, got a Sentinel")

    v = await redis.get(key)
    if not v:
        logstr = f"Key '{key}' not found in Redis DB."
        if "tor_web_addr" in key:
            logger.info(logstr)
        else:
            logger.warning(logstr)
        return ""

    try:
        return v.decode("utf-8")
    except AttributeError:
        return v


async def redis_get_raw(
    key: str, custom_redis: Redis | None = None
) -> Result[str | bytes | int | float | None, Report]:
    """Get the value at key `name` without decoding it

    Parameters
    ----------
    name: str
        The key to get
    custom_redis: Redis | None
        The custom Redis instance to use.
        If None, the default Redis instance will be used.
    """

    redis = None
    if custom_redis:
        redis = custom_redis
    else:
        redis = redis_plugin.redis
        if not isinstance(redis, Redis):
            raise Exception("Redis not initialized, got a Sentinel")

    try:
        data = await redis.get(key)
        return Ok(data)
    except Exception as e:
        return Err(
            Report(
                f"Error getting key {key}",
                error=e,
            )
        )


async def redis_delete(
    key: str, custom_redis: Redis | None = None
) -> Result[int, Report]:
    """Delete the value at key `name`

    Parameters
    ----------
    name: str
        The key to delete

    custom_redis: Redis | None
        The custom Redis instance to use.
        If None, the default Redis instance will be used.

    Returns
    -------
    Result[int, Report]
        Ok[int] if successful with the number of deleted keys
        Err[Report]
    """
    try:
        redis = None
        if custom_redis:
            redis = custom_redis
        else:
            redis = redis_plugin.redis
            if not isinstance(redis, Redis):
                return Err(
                    Report(
                        f"Redis not initialized, got a {type(redis)}",
                        error=RuntimeError(
                            f"Redis not initialized, got a {type(redis)}"
                        ),
                    )
                )

        result: int = await redis.delete(key)
        if not isinstance(result, int):
            return Err(
                Report(
                    f"Error deleting key {key}",
                    error=RuntimeError(f"Unexpected result type {type(result)}"),
                )
            )

        return Ok(result)

    except Exception as e:
        return Err(Report(f"Error deleting key {key}", error=e))


async def redis_exists(
    key: str, custom_redis: Redis | None = None
) -> Result[bool, Report]:
    """Check if a key exists in Redis

    Parameters
    ----------
    key: str
        The key to check
    custom_redis: Redis | None
        The custom Redis instance to use.
        If None, the default Redis instance will be used.
    """
    try:
        redis = None
        if custom_redis:
            redis = custom_redis
        else:
            redis = redis_plugin.redis
            if not isinstance(redis, Redis):
                return Err(
                    Report(
                        f"Redis not initialized, got a {type(redis)}",
                        error=RuntimeError(
                            f"Redis not initialized, got a {type(redis)}"
                        ),
                    )
                )

        res = await redis.exists(key)
        match res:
            case 0:
                return Ok(False)
            case 1:
                return Ok(True)
            case _:
                return Err(
                    Report(
                        f"Unexpected result type {type(res)} for key {key}",
                        error=RuntimeError(f"Unexpected result type {type(res)}"),
                    )
                )
    except Exception as e:
        return Err(Report(f"Error checking if key {key} exists", error=e))


async def redis_publish(
    channel: str, message: int | str | bytes | float, custom_redis: Redis | None = None
) -> Result[int, Report]:
    """Publish a message to a Redis channel

    Parameters
    ----------
    channel : str
        The name of the Redis channel
    message : int | str | bytes | float
        The message to publish

    Returns
    -------
    Result[int, Report]
        Ok[int]
            an integer representing active subscriber count
            zero indicates no active subscribers
        Err[Report]
    """
    try:
        redis = None
        if custom_redis:
            redis = custom_redis
        else:
            redis = redis_plugin.redis
            if not isinstance(redis, Redis):
                return Err(
                    Report(
                        f"Redis not initialized, got a {type(redis)}",
                        error=RuntimeError(
                            f"Redis not initialized, got a {type(redis)}"
                        ),
                    )
                )

        subscriber_count = await redis.publish(channel, message)
        return Ok(subscriber_count)
    except Exception as e:
        return Err(
            Report(f"Error publishing message to channel {channel}: {e}", error=e)
        )


# TODO
# idea is to have a second redis channel called system, that the API subscribes to.
# If for example the 'state' value gets changed by the _cache.sh script, it should
# publish this to this channel so the API can forward the change to thru the SSE to
# the WebUI


class SSE:
    SYSTEM_INFO = "system_info"
    SYSTEM_SHUTDOWN_NOTICE = "system_shutdown_initiated"
    SYSTEM_SHUTDOWN_ERROR = "system_shutdown_error"
    SYSTEM_STARTUP_INFO = "system_startup_info"
    SYSTEM_REBOOT_NOTICE = "system_reboot_initiated"
    SYSTEM_REBOOT_ERROR = "system_reboot_error"
    HARDWARE_INFO = "hardware_info"

    INSTALL_APP = "install"
    APP_MANAGE_MESSAGE = "app_manage_message"
    APP_STATE_MESSAGE = "app_state_update_message"

    BTC_NETWORK_STATUS = "btc_network_status"
    BTC_MEMPOOL_STATUS = "btc_mempool_status"
    BTC_NEW_BLOC = "btc_new_bloc"
    BTC_INFO = "btc_info"

    LN_INFO = "ln_info"
    LN_INVOICE_STATUS = "ln_invoice_status"
    LN_PAYMENT_STATUS = "ln_payment_status"
    LN_ONCHAIN_PAYMENT_STATUS = "ln_onchain_payment_status"
    LN_FEE_REVENUE = "ln_fee_revenue"
    LN_FORWARD_SUCCESSES = "ln_forward_successes"
    WALLET_BALANCE = "wallet_balance"


# https://gist.github.com/risent/4cab3878d995bec7d1c2
# https://firebase.blog/posts/2015/02/the-2120-ways-to-ensure-unique_68
# https://gist.github.com/mikelehen/3596a30bd69384624c11
class _PushID(object):
    # Modeled after base64 web-safe chars, but ordered by ASCII.
    PUSH_CHARS = "-0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ_abcdefghijklmnopqrstuvwxyz"

    def __init__(self):
        # Timestamp of last push, used to prevent local collisions if you
        # push twice in one ms.
        self.last_push_time = 0

        # We generate 72-bits of randomness which get turned into 12
        # characters and appended to the timestamp to prevent
        # collisions with other clients.  We store the last characters
        # we generated because in the event of a collision, we'll use
        # those same characters except "incremented" by one.
        self.last_rand_chars = array.array("i", [i for i in range(12)])

    def next_id(self):
        now = int(time.time() * 1000)
        duplicate_time = now == self.last_push_time
        self.last_push_time = now
        time_stamp_chars = array.array("u", "12345678")

        for i in range(7, -1, -1):
            time_stamp_chars[i] = self.PUSH_CHARS[now % 64]
            now = int(now / 64)

        if now != 0:
            raise ValueError("We should have converted the entire timestamp.")

        uid = "".join(time_stamp_chars)

        if not duplicate_time:
            for i in range(12):
                self.last_rand_chars[i] = int(random.random() * 64)
        else:
            # If the timestamp hasn't changed since last push, use the
            # same random number, except incremented by 1.
            for i in range(11, -1, -1):
                if self.last_rand_chars[i] == 63:
                    self.last_rand_chars[i] = 0
                else:
                    break
            self.last_rand_chars[i] += 1

        for i in range(12):
            uid += self.PUSH_CHARS[self.last_rand_chars[i]]

        if len(uid) != 20:
            raise ValueError("Length should be 20.")

        return uid


pid_gen = _PushID()


def next_push_id() -> str:
    """Generates a unique random 20 character long string id

    * They're based on timestamp so that they sort *after* any existing ids.
    * They contain 72-bits of random data after the timestamp so that IDs won't collide
    * with other clients' IDs. They sort *lexicographically* (so the timestamp is
    * converted to characters that will sort properly).
    * They're monotonically increasing.  Even if you generate more than one in the same
    * timestamp, the latter ones will sort after the former ones.  We do this by using
    * the previous random bits but "incrementing" them by 1 (only in the case of a
    * timestamp collision).
    """
    return pid_gen.next_id()


def config_get_hex_str(value: str, name: str = "") -> str:
    if value is None or len(value) == 0:
        raise ValueError(f"{name} cannot be null or empty")

    if _is_hex(value):
        return value

    if not os.path.exists(value):
        raise ValueError(f"{name} is not a valid path")

    with open(value, "rb") as f:
        m = f.read()
        m = m.hex()
        return m


def _is_hex(s):
    try:
        int(s, 16)
        return True
    except ValueError:
        return False


async def _terminate_process(proc, timeout=5) -> Result[bool, Report]:
    """
    Terminates a process and waits for it to finish.

    :param proc: The process to terminate.
    :param timeout: The maximum time in seconds to wait for the process to terminate.
    """
    try:
        proc.kill()
        await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except TimeoutError:
        logger.error(f"failed to terminate process {proc.pid} within {timeout} seconds")
        return Err(
            Report(
                f"failed to terminate process within {timeout} seconds",
                error=TimeoutError(),
            )
        )
    return Ok(True)


async def exec_bash_command(
    command: str,
    use_sudo: bool = False,
    timeout: float | None = 15.0,
    sensitive: bool = False,
) -> Result[ProcessResult, Report]:
    """
    Executes a bash command asynchronously.

    :param command: The bash command to execute.
    :param use_sudo: Whether to prepend 'sudo' to the command.
                     Defaults to False.
    :param timeout: The maximum time in seconds to wait for the command to
                    complete. Defaults to 10.0 seconds.
    :param sensitive: Whether to hide the command in the log.
    :return: A Result object containing either a ProcessResult on success or a
             Report on failure.
    """  # noqa: E501
    if sensitive:
        logger.debug(
            f"executing sensitive command with sudo: {use_sudo} and timeout: {timeout}"
        )
    else:
        logger.debug(
            f"executing command: {command} with sudo: {use_sudo} and timeout: {timeout}"
        )

    try:
        if command.startswith("sudo"):
            return Err(
                Report(
                    f"command '{command}' must not start with sudo", error=ValueError()
                )
            )

        cmd = f"{'sudo ' if use_sudo else ''}bash {command}"
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            return Ok(
                ProcessResult(
                    proc.returncode,
                    stdout.decode() if stdout else "",
                    stderr.decode() if stderr else "",
                )
            )
        except TimeoutError:
            logger.debug(f"{cmd} timed out after {timeout} seconds")
            res = await _terminate_process(proc)
            match res:
                case Ok(_):
                    return Err(
                        Report(
                            f"command '{command}' timed out after {timeout} seconds",
                            error=TimeoutError(),
                        ).attach(command, "command")
                    )
                case Err(report):
                    return Err(report)

    except Exception as e:
        report = Report(f"unable to execute the bash script {command}", error=e)
        report.attach(command, "command")

        return Err(report)


def parse_key_value_lines(lines: list) -> dict:
    Dict = {}
    for line in lines:
        line = line.strip()
        if len(line) == 0:
            continue
        if not re.match("^[a-zA-Z0-9]*=", line):
            continue
        key, value = line.strip().split("=", 1)
        Dict[key] = value.strip('"').strip("'")
    return Dict


def parse_key_value_text(text: str) -> dict:
    return parse_key_value_lines(text.splitlines())
