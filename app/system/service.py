import asyncio
from typing import Dict, Optional

from decouple import config
from fastapi import HTTPException, Request, status

from app.api.utils import SSE, broadcast_sse_msg
from app.system.models import (
    APIPlatform,
    ConnectionInfo,
    LoginInput,
    RawDebugLogData,
    SystemHealthInfo,
    SystemInfo,
)

PLATFORM = config("platform", default=APIPlatform.RASPIBLITZ)
if PLATFORM == APIPlatform.RASPIBLITZ:
    from app.system.impl.raspiblitz import RaspiBlitzSystem as System
elif PLATFORM == APIPlatform.NATIVE_PYTHON:
    from app.system.impl.native_python import NativePythonSystem as System


system = System()

if system is None:
    raise RuntimeError(f"Unknown platform {PLATFORM}")

HW_INFO_YIELD_TIME = system.get_hardware_info_yield_time()


async def change_password(type: Optional[str], old_password: str, new_password: str):
    try:
        return await system.change_password(type, old_password, new_password)
    except HTTPException:
        raise
    except NotImplementedError as r:
        raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, detail=r.args[0])


async def get_system_info() -> SystemInfo:
    try:
        return await system.get_system_info()
    except HTTPException:
        raise
    except NotImplementedError as r:
        raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, detail=r.args[0])


async def system_health(verbose: bool) -> SystemHealthInfo:
    try:
        return await system.get_system_health(verbose)
    except HTTPException:
        raise
    except NotImplementedError as r:
        raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, detail=r.args[0])


async def get_hardware_info() -> map:
    try:
        return await system.get_hardware_info()
    except HTTPException:
        raise
    except NotImplementedError as r:
        raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, detail=r.args[0])


async def get_connection_info() -> ConnectionInfo:
    try:
        return await system.get_connection_info()
    except HTTPException:
        raise
    except NotImplementedError as r:
        raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, detail=r.args[0])


async def shutdown(reboot: bool) -> bool:
    if reboot:
        await broadcast_sse_msg(SSE.SYSTEM_REBOOT_NOTICE, {"reboot": True})
    else:
        await broadcast_sse_msg(SSE.SYSTEM_SHUTDOWN_NOTICE, {"shutdown": True})

    try:
        return await system.shutdown(reboot=reboot)
    except HTTPException:
        raise
    except NotImplementedError as r:
        raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, detail=r.args[0])


async def subscribe_hardware_info(request: Request):
    while True:
        if await request.is_disconnected():
            # stop if client disconnects
            break
        yield await get_hardware_info()
        await asyncio.sleep(HW_INFO_YIELD_TIME)


async def get_debug_logs_raw() -> RawDebugLogData:
    try:
        return await system.get_debug_logs_raw()
    except HTTPException:
        raise
    except NotImplementedError as r:
        raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, detail=r.args[0])


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
    try:
        return await system.login(i)
    except HTTPException:
        raise
    except NotImplementedError as r:
        raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, detail=r.args[0])
