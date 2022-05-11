import asyncio
import re
from os import path

from decouple import config
from fastapi import HTTPException, Request, status

from app.models.system import APIPlatform, RawDebugLogData, SystemInfo, ConnectionInfo
from app.utils import SSE, send_sse_message

PLATFORM = config("platform", default=APIPlatform.RASPIBLITZ)
if PLATFORM == APIPlatform.RASPIBLITZ:
    from app.repositories.hardware_impl.raspiblitz import (
        HW_INFO_YIELD_TIME,
        get_hardware_info_impl,
    )
    from app.repositories.system_impl.raspiblitz import (
        get_system_info_impl,
        shutdown_impl,
        get_connection_info_impl,
    )
elif PLATFORM == APIPlatform.NATIVE_PYTHON:
    from app.repositories.hardware_impl.native_python import (
        HW_INFO_YIELD_TIME,
        get_hardware_info_impl,
    )
    from app.repositories.system_impl.native_python import (
        get_system_info_impl,
        shutdown_impl,
        get_connection_info_impl,
    )
else:
    raise RuntimeError(f"Unknown platform {PLATFORM}")

SHELL_SCRIPT_PATH = config("shell_script_path")
GET_DEBUG_LOG_SCRIPT = path.join(SHELL_SCRIPT_PATH, "config.scripts", "blitz.debug.sh")


def _check_shell_scripts_status():
    if not path.exists(SHELL_SCRIPT_PATH):
        raise Exception(f"invalid shell script path: {SHELL_SCRIPT_PATH}")

    if not path.isfile(GET_DEBUG_LOG_SCRIPT):
        raise Exception(f"Required file does not exist: {GET_DEBUG_LOG_SCRIPT}")


_check_shell_scripts_status()


def password_valid(password: str):
    if len(password) < 8:
        return False
    if password.find(" ") >= 0:
        return False
    return re.match("^[a-zA-Z0-9]*$", password)


def name_valid(password: str):
    if len(password) < 3:
        return False
    if password.find(" ") >= 0:
        return False
    return re.match("^[\.a-zA-Z0-9-_]*$", password)


async def get_system_info() -> SystemInfo:
    try:
        return await get_system_info_impl()
    except HTTPException as r:
        raise
    except NotImplementedError as r:
        raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, detail=r.args[0])


async def get_hardware_info() -> map:
    return await get_hardware_info_impl()

async def get_connection_info() -> ConnectionInfo:
    return await get_connection_info_impl()

async def shutdown(reboot: bool) -> bool:
    if reboot:
        await send_sse_message(SSE.SYSTEM_REBOOT_NOTICE, {"reboot": True})
    else:
        await send_sse_message(SSE.SYSTEM_SHUTDOWN_NOTICE, {"shutdown": True})

    return await shutdown_impl(reboot=reboot)


async def subscribe_hardware_info(request: Request):
    while True:
        if await request.is_disconnected():
            # stop if client disconnects
            break
        yield await get_hardware_info()
        await asyncio.sleep(HW_INFO_YIELD_TIME)


async def get_debug_logs_raw() -> RawDebugLogData:
    cmd = f"bash {GET_DEBUG_LOG_SCRIPT}"
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    stdout, stderr = await proc.communicate()

    if stderr:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"""
f"[{cmd!r} exited with {proc.returncode}]"\n
[stderr]\n{stderr.decode()}
        """,
        )

    if stdout:
        return RawDebugLogData(raw_data=f"[stdout]\n{stdout.decode()}")

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"{cmd} returned no error and no output.",
    )


async def _handle_gather_hardware_info():
    last_info = {}
    while True:
        info = await get_hardware_info()
        if last_info != info:
            await send_sse_message(SSE.HARDWARE_INFO, info)
            last_info = info

        await asyncio.sleep(HW_INFO_YIELD_TIME)


async def register_hardware_info_gatherer():
    loop = asyncio.get_event_loop()
    loop.create_task(_handle_gather_hardware_info())
