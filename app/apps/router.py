import asyncio

from fastapi import APIRouter, HTTPException, Path
from fastapi.params import Depends
from loguru import logger

import app.apps.docs as docs
import app.apps.service as service
from app.apps.cache import watch_app_status_changes
from app.apps.models import AppId, AppStatus, AppStatusQueryResult, AppUninstallInput
from app.auth.auth_bearer import JWTBearer

_PREFIX = "apps"

router = APIRouter(prefix=f"/{_PREFIX}", tags=["Apps"])


async def register_app_status_update_handlers():
    # This handler watches for messages from the update app cache celery task
    # it is also responsible for notifying clients of the change
    loop = asyncio.get_event_loop()
    loop.create_task(watch_app_status_changes())


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


@router.post(
    "/update-cache",
    name=f"{_PREFIX}/update-cache",
    summary="Update the app status cache. Results will be broadcasted to SSE clients.",
    dependencies=[Depends(JWTBearer())],
)
@logger.catch(exclude=(HTTPException,))
async def update_cache():
    return await service.update_app_state_cache()


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
    "/install/{app_id}",
    name=f"{_PREFIX}/install",
    summary="Install an app",
    description="""Attempts to install an app. The installation process results are
    not returned on this endpoint. Instead, the results are communicated via the SSE
    channels. This call only verifies if the app is available for installation on the
    given platform.""",
    responses={
        400: {
            "description": "If the app is already installed "
            "or not available for the platform."
        },
        404: {"description": "If no or an invalid app id is given."},
        423: {"description": "If an app install task is already running."},
    },
    dependencies=[Depends(JWTBearer())],
)
@logger.catch(exclude=(HTTPException,))
async def install_app(app_id: AppId):
    await service.install_app(app_id)


@router.post(
    "/uninstall",
    name=f"{_PREFIX}/uninstall",
    summary="Uninstall app",
    description="""Attempts to uninstall an app. The uninstallation process results are
    not returned on this endpoint. Instead, the results are communicated via the SSE
    channels. This call only verifies if the app is available for uninstallation on the
    given platform.""",
    responses={
        400: {"description": ("If the app is already installed.")},
        404: {"description": ("If no or an invalid app id is given.")},
    },
    dependencies=[Depends(JWTBearer())],
)
@logger.catch(exclude=(HTTPException,))
async def uninstall_app(input: AppUninstallInput):
    await service.uninstall_app(input)
