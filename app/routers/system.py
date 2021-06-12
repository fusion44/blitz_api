from fastapi import APIRouter, HTTPException, status, Request
from fastapi.params import Depends
from sse_starlette.sse import EventSourceResponse

from app.auth.auth_handler import signJWT
from app.auth.auth_bearer import JWTBearer
from app.repositories.hardware_info import HW_INFO_YIELD_TIME, get_hardware_info, subscribe_hardware_info
from app.routers.system_docs import get_hw_info_json

router = APIRouter(
    prefix="/system",
    tags=["System"]
)


@router.post("/login", summary="Logs the user in with password A",
             response_description="JWT token for the current session.",
             status_code=status.HTTP_200_OK)
def login(password_a: str):
    if password_a == "123":
        return signJWT()

    raise HTTPException(status.HTTP_401_UNAUTHORIZED,
                        detail="Password is wrong")


@router.get("/hardware_info",
            summary="Get hardware status information.",
            response_description="Returns a JSON string with hardware information:\n" +
            get_hw_info_json,
            dependencies=[Depends(JWTBearer())],
            status_code=status.HTTP_200_OK)
def hw_info() -> map:
    return get_hardware_info()


@router.get("/hardware_info_sub",
            summary="Subscribe to hardware status information.",
            response_description=f"Yields a JSON string with hardware information every {HW_INFO_YIELD_TIME} seconds:\n" +
            get_hw_info_json,
            dependencies=[Depends(JWTBearer())],
            status_code=status.HTTP_200_OK)
async def hw_info_sub(request: Request):
    return EventSourceResponse(subscribe_hardware_info(request))


@ router.post("/reboot",
              summary="Reboots the system",
              dependencies=[Depends(JWTBearer())],
              status_code=status.HTTP_200_OK)
def reboot_system():
    return HTTPException(status.HTTP_501_NOT_IMPLEMENTED)


@ router.post("/shutdown",
              summary="Shuts the system down",
              dependencies=[Depends(JWTBearer())],
              status_code=status.HTTP_200_OK)
def reboot_system():
    return HTTPException(status.HTTP_501_NOT_IMPLEMENTED)
