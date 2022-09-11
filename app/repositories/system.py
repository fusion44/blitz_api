import asyncio
import re
from typing import Dict

from decouple import config
from fastapi import HTTPException, Request, status

from app.auth.auth_handler import sign_jwt
from app.core_utils import SSE, broadcast_sse_msg
from app.models.system import (
    APIPlatform,
    ConnectionInfo,
    LoginInput,
    RawDebugLogData,
    SystemInfo,
)

PLATFORM = config("platform", default=APIPlatform.RASPIBLITZ)
if PLATFORM == APIPlatform.RASPIBLITZ:
    from app.core_utils import call_script, call_sudo_script, parse_key_value_text
    from app.repositories.hardware_impl.raspiblitz import (
        HW_INFO_YIELD_TIME,
        get_hardware_info_impl,
    )
    from app.repositories.system_impl.raspiblitz import (
        get_connection_info_impl,
        get_system_info_impl,
        match_password,
        shutdown_impl,
    )
elif PLATFORM == APIPlatform.NATIVE_PYTHON:
    from app.repositories.hardware_impl.native_python import (
        HW_INFO_YIELD_TIME,
        get_hardware_info_impl,
    )
    from app.repositories.system_impl.native_python import (
        get_connection_info_impl,
        get_system_info_impl,
        match_password,
        shutdown_impl,
    )
else:
    raise RuntimeError(f"Unknown platform {PLATFORM}")


def password_valid(password: str):
    # TODO: remove this once RaspiBlitz is fully refactored
    #       into its own implementation file

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


async def password_change(type: str, old_password: str, new_password: str):

    # check just allowed type values
    type = type.lower()
    if not type in ["a", "b", "c"]:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="unknown password type")

    # check password formatting
    if not password_valid(old_password):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail="old password format invalid"
        )
    if not password_valid(new_password):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail="new password format invalid"
        )

    if PLATFORM == APIPlatform.RASPIBLITZ:

        # first check if old password is correct
        result = await call_script(
            f'/home/admin/config.scripts/blitz.passwords.sh check {type} "{old_password}"'
        )
        data = parse_key_value_text(result)
        if not data["correct"] == "1":
            raise HTTPException(
                status.HTTP_406_NOT_ACCEPTABLE, detail="old password not correct"
            )

        # second set new password
        script_call = (
            f'/home/admin/config.scripts/blitz.passwords.sh set {type} "{new_password}"'
        )
        if type == "c":
            # will set password c of both lnd & core lightning if installed/activated
            script_call = f'/home/admin/config.scripts/blitz.passwords.sh set c "{old_password}" "{new_password}"'
        result = await call_sudo_script(script_call)
        data = parse_key_value_text(result)
        print(str(data))
        if "error" in data.keys() and len(data["error"]) > 0:
            raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, detail=data["error"])
        return

    else:
        raise HTTPException(
            status.HTTP_501_NOT_IMPLEMENTED,
            detail="endpoint just works on raspiblitz so far",
        )


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
        await broadcast_sse_msg(SSE.SYSTEM_REBOOT_NOTICE, {"reboot": True})
    else:
        await broadcast_sse_msg(SSE.SYSTEM_SHUTDOWN_NOTICE, {"shutdown": True})

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
            await broadcast_sse_msg(SSE.HARDWARE_INFO, info)
            last_info = info

        await asyncio.sleep(HW_INFO_YIELD_TIME)


async def register_hardware_info_gatherer():
    loop = asyncio.get_event_loop()
    loop.create_task(_handle_gather_hardware_info())


async def login(i: LoginInput) -> Dict[str, str]:
    matches = await match_password(i)
    if matches:
        return sign_jwt()

    raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Password is incorrect")
