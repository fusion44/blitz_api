import app.repositories.apps as repo
import app.routers.apps_docs as docs
from app.auth.auth_bearer import JWTBearer
from app.sse_starlette import EventSourceResponse
from fastapi import APIRouter, HTTPException, status
from fastapi.params import Depends

_PREFIX = "apps"

router = APIRouter(prefix=f"/{_PREFIX}", tags=["Apps"])


@router.get(
    "/status",
    name=f"{_PREFIX}/status",
    summary="Get the status of currently installed apps.",
    response_description=docs.get_app_status_response_docs,
    dependencies=[Depends(JWTBearer())],
)
def get_status():
    try:
        return repo.get_app_status()
    except:
        return HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Unknown error"
        )


@router.get(
    "/status-sub",
    name=f"{_PREFIX}/status-sub",
    summary="Subscribe to status changes of currently installed apps.",
    response_description=docs.get_app_status_sub_response_docs,
    dependencies=[Depends(JWTBearer())],
)
async def get_status():
    try:
        return EventSourceResponse(repo.get_app_status_sub())
    except:
        return HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Unknown error"
        )
