from fastapi import APIRouter, HTTPException, Path
from fastapi.params import Depends
from loguru import logger
from pydantic import BaseModel

import app.apps.docs as docs
import app.apps.service as repo
from app.auth.auth_bearer import JWTBearer
from app.external.sse_starlette import EventSourceResponse

_PREFIX = "apps"

router = APIRouter(prefix=f"/{_PREFIX}", tags=["Apps"])


@router.get(
    "/status",
    name=f"{_PREFIX}/status",
    summary="Get the status available apps.",
    response_description=docs.get_app_status_response_docs,
    dependencies=[Depends(JWTBearer())],
)
@logger.catch(exclude=(HTTPException,))
async def get_status():
    return await repo.get_app_status()


@router.get(
    "/status/{id}",
    name=f"{_PREFIX}/status",
    summary="Get the status of a single app by id.",
    dependencies=[Depends(JWTBearer())],
)
@logger.catch(exclude=(HTTPException,))
async def get_single_status(id):
    return await repo.get_app_status_single(id)


@router.get(
    "/status_advanced/{id}",
    name=f"{_PREFIX}/status_advanced",
    summary="Get the advanced status of a single app by id.",
    description="""Some apps might give status information that is computationally
    to expensive to include in the normal status endpoint.

> ℹ️ _This endpoint is not implemented on all platforms_
    """,
    dependencies=[Depends(JWTBearer())],
    responses={400: {"description": ("If no or invalid app id is given.")}},
)
@logger.catch(exclude=(HTTPException,))
async def get_single_status_advanced(id: str = Path(..., required=True)):
    return await repo.get_app_status_advanced(id)


@router.get(
    "/status-sub",
    name=f"{_PREFIX}/status-sub",
    summary="Subscribe to status changes of currently installed apps.",
    response_description=docs.get_app_status_sub_response_docs,
    dependencies=[Depends(JWTBearer())],
)
@logger.catch(exclude=(HTTPException,))
async def get_status_sub():
    return EventSourceResponse(repo.get_app_status_sub())


@router.post(
    "/install/{name}",
    name=f"{_PREFIX}/install",
    summary="Install app",
    dependencies=[Depends(JWTBearer())],
)
@logger.catch(exclude=(HTTPException,))
async def install_app(name: str):
    return await repo.install_app_sub(name)


class UninstallData(BaseModel):
    keepData: bool = True


@router.post(
    "/uninstall/{name}",
    name=f"{_PREFIX}/install",
    summary="Uninstall app",
    dependencies=[Depends(JWTBearer())],
)
@logger.catch(exclude=(HTTPException,))
async def uninstall_app(name: str, data: UninstallData):
    return await repo.uninstall_app_sub(name, data.keepData)
