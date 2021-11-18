import secrets

from app.auth.auth_bearer import JWTBearer
from app.auth.auth_handler import signJWT
from app.external.sse_startlette import EventSourceResponse
from app.models.system import LoginInput, RawDebugLogData, SystemInfo
from app.repositories.system import (
    HW_INFO_YIELD_TIME,
    get_debug_logs_raw,
    get_hardware_info,
    get_system_info,
    subscribe_hardware_info,
)
from app.routers.system_docs import (
    get_debug_logs_raw_desc,
    get_debug_logs_raw_resp_desc,
    get_debug_logs_raw_summary,
    get_hw_info_json,
)
from decouple import config
from fastapi import APIRouter, HTTPException, Request, status
from fastapi.params import Depends

_PREFIX = "system"

router = APIRouter(prefix=f"/{_PREFIX}", tags=["System"])


@router.post(
    "/login",
    name=f"{_PREFIX}.login",
    summary="Logs the user in with the current password",
    response_description="JWT token for the current session.",
    status_code=status.HTTP_200_OK,
)
def login(i: LoginInput):
    match = secrets.compare_digest(i.password, config("login_password", cast=str))
    if match:
        return signJWT()

    raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Password is wrong")


@router.get(
    "/get-system-info",
    name=f"{_PREFIX}.get-system-info",
    summary="Get system status information",
    dependencies=[Depends(JWTBearer())],
    response_model=SystemInfo,
)
async def get_system_info_path():
    return await get_system_info()


@router.get(
    "/hardware-info",
    name=f"{_PREFIX}.hardware-info",
    summary="Get hardware status information.",
    response_description="Returns a JSON string with hardware information:\n"
    + get_hw_info_json,
    dependencies=[Depends(JWTBearer())],
    status_code=status.HTTP_200_OK,
)
def hw_info() -> map:
    return get_hardware_info()


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
    dependencies=[Depends(JWTBearer())],
)
def reboot_system():
    return HTTPException(status.HTTP_501_NOT_IMPLEMENTED)


@router.post(
    "/shutdown",
    name=f"{_PREFIX}.shutdown",
    summary="Shuts the system down",
    dependencies=[Depends(JWTBearer())],
)
def reboot_system():
    return HTTPException(status.HTTP_501_NOT_IMPLEMENTED)
