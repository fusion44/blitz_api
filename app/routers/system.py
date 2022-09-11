from typing import Optional

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.params import Depends, Query

from app.auth.auth_bearer import JWTBearer
from app.auth.auth_handler import sign_jwt
from app.core_utils import SSE
from app.external.sse_starlette import EventSourceResponse
from app.models.system import ConnectionInfo, LoginInput, RawDebugLogData, SystemInfo
from app.repositories.system import (
    HW_INFO_YIELD_TIME,
    change_password,
    get_connection_info,
    get_debug_logs_raw,
    get_hardware_info,
    get_system_info,
    login,
    shutdown,
    subscribe_hardware_info,
)
from app.routers.system_docs import (
    get_debug_logs_raw_desc,
    get_debug_logs_raw_resp_desc,
    get_debug_logs_raw_summary,
    get_hw_info_json,
)

_PREFIX = "system"

router = APIRouter(prefix=f"/{_PREFIX}", tags=["System"])


@router.post(
    "/login",
    name=f"{_PREFIX}.login",
    summary="Logs the user in with the current password",
    response_description="JWT token for the current session.",
    status_code=status.HTTP_200_OK,
)
async def login_path(i: LoginInput):
    try:
        return await login(i)
    except HTTPException as r:
        raise
    except NotImplementedError as r:
        raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, detail=r.args[0])


@router.post(
    "/refresh-token",
    name=f"{_PREFIX}.refresh-token",
    summary="Endpoint to refresh an authentication token",
    response_description="Returns a fresh JWT token.",
    dependencies=[Depends(JWTBearer())],
)
def refresh_token():
    return sign_jwt()


@router.post(
    "/change-password",
    name=f"{_PREFIX}.change-password",
    summary="Endpoint to change your password",
    response_description="if 200 OK - password change worked",
    dependencies=[Depends(JWTBearer())],
)
async def change_password(
    old_password: str,
    new_password: str,
    type: Optional[str] = Query(
        None,
        description=' ℹ️ Used in **RaspiBlitz only**. Password A, B or C. Must be one of `["a", "b", "c"]`',
    ),
):
    return await change_password(type, old_password, new_password)


@router.get(
    "/get-system-info",
    name=f"{_PREFIX}.get-system-info",
    summary="Get system status information",
    dependencies=[Depends(JWTBearer())],
    response_model=SystemInfo,
    responses={
        423: {"description": "Wallet is locked. Unlock via /lightning/unlock-wallet"}
    },
)
async def get_system_info_path():
    try:
        return await get_system_info()
    except HTTPException as r:
        raise
    except NotImplementedError as r:
        raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, detail=r.args[0])


@router.get(
    "/hardware-info",
    name=f"{_PREFIX}.hardware-info",
    summary="Get hardware status information.",
    response_description="Returns a JSON string with hardware information:\n"
    + get_hw_info_json,
    dependencies=[Depends(JWTBearer())],
    status_code=status.HTTP_200_OK,
)
async def hw_info() -> map:
    return await get_hardware_info()


@router.get(
    "/connection-info",
    name=f"{_PREFIX}.connection-info",
    summary="Get credential information to connect external apps.",
    response_description="Returns a JSON string with credential information.",
    response_model=ConnectionInfo,
    dependencies=[Depends(JWTBearer())],
    status_code=status.HTTP_200_OK,
)
async def connection_info() -> map:
    return await get_connection_info()


@router.get(
    "/get-debug-logs-raw",
    name=f"{_PREFIX}.get-debug-logs-raw",
    summary=get_debug_logs_raw_summary,
    description=get_debug_logs_raw_desc,
    response_description=get_debug_logs_raw_resp_desc,
    response_model=RawDebugLogData,
    dependencies=[Depends(JWTBearer())],
)
async def get_debug_logs_raw_route() -> RawDebugLogData:
    return await get_debug_logs_raw()


@router.get(
    "/hardware-info-sub",
    name=f"{_PREFIX}.hardware-info-sub",
    summary="Subscribe to hardware status information.",
    response_description=f"Yields a JSON string with hardware information every {HW_INFO_YIELD_TIME} seconds:\n"
    + get_hw_info_json,
    dependencies=[Depends(JWTBearer())],
)
async def hw_info_sub(request: Request):
    return EventSourceResponse(subscribe_hardware_info(request))


@router.post(
    "/reboot",
    name=f"{_PREFIX}.reboot",
    summary="Reboots the system",
    description=f"""Attempts to reboot the system.
    Will send a `{SSE.SYSTEM_REBOOT_NOTICE}` SSE message immediately to
    all connected clients.
    """,
    response_description=f"""True if successful. False on failure.
    A failure will also send an error message with id `{SSE.SYSTEM_REBOOT_ERROR}`
    to all connected clients.
    """,
    dependencies=[Depends(JWTBearer())],
)
async def reboot_system() -> bool:
    return await shutdown(reboot=True)


@router.post(
    "/shutdown",
    name=f"{_PREFIX}.shutdown",
    summary="Shuts the system down",
    description=f"""Attempts to shutdown the system.
    Will send a `{SSE.SYSTEM_SHUTDOWN_NOTICE}` SSE message immediately to all
    connected clients.
    """,
    response_description=f"""True if successful. False on failure.
    A failure will also send an error message with id {SSE.SYSTEM_SHUTDOWN_ERROR}
    to all connected clients.
    """,
    dependencies=[Depends(JWTBearer())],
)
async def shutdown_path() -> bool:
    return await shutdown(False)
