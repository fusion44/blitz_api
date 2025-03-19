from fastapi import APIRouter, HTTPException, Path
from fastapi.params import Depends
from loguru import logger

import app.apps.docs as docs
import app.apps.service as service
from app.apps.models import AppId, AppStatus, AppStatusQueryResult, UninstallData
from app.auth.auth_bearer import JWTBearer

_PREFIX = "apps"

router = APIRouter(prefix=f"/{_PREFIX}", tags=["Apps"])


@router.get(
    "/status",
    name=f"{_PREFIX}/status",
    summary="Get the status of all available apps.",
    response_description=docs.get_app_status_response_docs,
    dependencies=[Depends(JWTBearer())],
)
@logger.catch(exclude=(HTTPException,))
async def get_status() -> AppStatusQueryResult:
    return await service.get_app_status()


@router.get(
    "/status/{id}",
    name=f"{_PREFIX}/status",
    summary="Get the status of a single app by id.",
    dependencies=[Depends(JWTBearer())],
    responses={404: {"description": ("If no or an invalid app id is given.")}},
)
@logger.catch(exclude=(HTTPException,))
async def get_single_status(id) -> AppStatus:
    return await service.get_app_status_single(id)


@router.get(
    "/status_advanced/{id}",
    name=f"{_PREFIX}/status_advanced",
    summary="Get the advanced status of a single app by id.",
    description=f"""Some apps might give status information that is computationally
    to expensive to include in the normal status endpoint.

    Available app ids for this endpoint:
    - {AppId.ELECTRS.value}

> ℹ️  _This endpoint is not implemented on all platforms_
    """,
    dependencies=[Depends(JWTBearer())],
    responses={404: {"description": ("If no or an invalid app id is given.")}},
)
@logger.catch(exclude=(HTTPException,))
async def get_single_status_advanced(id: str = Path(..., required=True)):
    return await service.get_app_status_advanced(id)


@router.post(
    "/install/{name}",
    name=f"{_PREFIX}/install",
    summary="Install app",
    dependencies=[Depends(JWTBearer())],
)
@logger.catch(exclude=(HTTPException,))
async def install_app(name: str):
    return await service.install_app_sub(name)


@router.post(
    "/uninstall/{name}",
    name=f"{_PREFIX}/install",
    summary="Uninstall app",
    dependencies=[Depends(JWTBearer())],
)
@logger.catch(exclude=(HTTPException,))
async def uninstall_app(name: str, data: UninstallData):
    return await service.uninstall_app_sub(name, data.keepData)
