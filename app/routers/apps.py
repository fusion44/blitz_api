from fastapi import APIRouter, HTTPException, status
from fastapi.params import Depends

import app.repositories.apps as repo
import app.routers.apps_docs as docs
from app.auth.auth_bearer import JWTBearer
from app.external.sse_starlette import EventSourceResponse

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
        raise HTTPException(
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
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Unknown error"
        )


@router.post(
    "/install/{name}",
    name=f"{_PREFIX}/install",
    summary="Install app",
    dependencies=[Depends(JWTBearer())],
)
async def install_app(name: str):
    return await repo.install_app_sub(name)


@router.post(
    "/uninstall/{name}",
    name=f"{_PREFIX}/install",
    summary="Uninstall app",
    dependencies=[Depends(JWTBearer())],
)
async def uninstall_app(name: str):
    return await repo.uninstall_app_sub(name)
