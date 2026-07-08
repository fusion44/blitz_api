import asyncio
from typing import Dict, Optional

from fastapi import HTTPException, Request, status
from loguru import logger

from app.api.config import config
from app.api.error_report.report import Frame
from app.api.utils import SSE, broadcast_sse_msg
from app.external.result_type.src.result.result import Err, Ok
from app.system.models import (
    APIPlatform,
    ConnectionInfo,
    LoginInput,
    RawDebugLogData,
    SystemHealthInfo,
    SystemInfo,
)

PLATFORM = config("BAPI_PLATFORM", default=APIPlatform.RASPIBLITZ)
if PLATFORM == APIPlatform.RASPIBLITZ:
    logger.info("using RaspiBlitz system implementation")
    from app.system.impl.raspiblitz import RaspiBlitzSystem as System
elif PLATFORM == APIPlatform.NATIVE_PYTHON:
    logger.info("using native python system implementation")
    from app.system.impl.native_python import NativePythonSystem as System
else:
    raise RuntimeError(
        f"Unsupported platform '{PLATFORM}'. Options: {APIPlatform.values_as_list()}"
    )


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
    result = await system.get_connection_info()
    match result:
        case Ok(data):
            return data
        case Err(report):
            e = report.last_error
            report.attach_frame(Frame("unable to get connection info"))
            if e is None:
                logger.error(report.format_verbose())
                raise HTTPException(
                    status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=report.format_verbose(),
                )
            if isinstance(e, HTTPException):
                raise e
            if isinstance(e, NotImplementedError):
                raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, detail=e)

    raise HTTPException(
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="unknown error getting connection info",
    )


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
        try:
            info = await get_hardware_info()
            if last_info != info:
                await broadcast_sse_msg(SSE.HARDWARE_INFO, info)
                last_info = info
        except Exception as e:
            # never let a single failure kill the gatherer task, otherwise
            # hardware SSE updates would stop until the API is restarted
            logger.error(f"Error gathering hardware info: {e}")

        await asyncio.sleep(HW_INFO_YIELD_TIME)


async def register_hardware_info_gatherer():
    asyncio.create_task(_handle_gather_hardware_info())


async def login(i: LoginInput) -> Dict[str, str]:
    result = await system.login(i)
    match result:
        case Ok(data):
            return data
        case Err(report):
            e = report.last_error
            report.attach_frame(Frame("error during login"))
            if e is None:
                logger.error("got report without error")
                logger.error(report.format_verbose())
                raise HTTPException(
                    status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=report.format_verbose(),
                )
            if (
                isinstance(e, HTTPException)
                and e.status_code == status.HTTP_401_UNAUTHORIZED
            ):
                logger.info("unauthorized login attempt")
                raise e
            if (
                isinstance(e, HTTPException)
                and e.status_code != status.HTTP_401_UNAUTHORIZED
            ):
                logger.error(report.format_verbose())
                raise e
            if isinstance(e, NotImplementedError):
                raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, detail=e)

    raise HTTPException(
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="unknown error",
    )
