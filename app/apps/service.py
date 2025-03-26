from fastapi import HTTPException, status
from loguru import logger

from app.api.config import config
from app.api.error_report.report import Report
from app.api.models import ApiErrors
from app.apps.models import AppStatus, AppStatusQueryResult
from app.external.result_type.src.result import Err, Ok
from app.main import ErrorMessage
from app.system.models import APIPlatform

PLATFORM = config("BAPI_PLATFORM", default=APIPlatform.UNKNOWN)
if PLATFORM == APIPlatform.RASPIBLITZ:
    from app.apps.impl.raspiblitz import RaspiBlitzApps as Apps
elif PLATFORM == APIPlatform.NATIVE_PYTHON:
    from app.apps.impl.native_python import NativePythonApps as Apps
else:
    raise RuntimeError(
        f"Unsupported platform '{PLATFORM}'. Options: {APIPlatform.values_as_list()}."
    )


apps = Apps()

if apps is None:
    raise RuntimeError(f"Unknown platform {PLATFORM}")


async def get_app_status_single(id: str) -> AppStatus:
    match await apps.get_app_status_single(id):
        case Ok(value):
            return value
        case Err(report):
            # will throw for us
            _handle_error(report)

    # In theory we should never arrive to this point...
    raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Unknown error")


async def get_app_status() -> AppStatusQueryResult:
    match await apps.get_app_status():
        case Ok(values):
            return values
        case Err(report):
            _handle_error(report)

    raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Unknown error")


async def get_app_status_advanced(app_id: str) -> AppStatus:
    match await apps.get_app_status_advanced(app_id):
        case Ok(values):
            return values
        case Err(report):
            _handle_error(report)

    raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Unknown error")


async def install_app_sub(app_id: str):
    return await apps.install_app_sub(app_id)


async def uninstall_app_sub(app_id: str, delete_data: bool):
    return await apps.uninstall_app_sub(app_id, delete_data)


def _handle_error(report: Report):
    code = 0
    if isinstance(report.last_error, HTTPException):
        code = report.last_error.status_code
        if code >= 500:
            # internal error, log fully
            logger.error(report.format_verbose(include_sensitive=True))
        else:
            # user error, log only as debug
            logger.info(report.format_verbose())

        raise HTTPException(
            status_code=code,
            detail=ErrorMessage(
                detail=report.frames[0].message,
                error_code=ApiErrors.INVALID_REQUEST_INPUT,
                report=f"{report.format_verbose()}",
            ).model_dump(),
        )
    else:
        logger.error(
            f"Error report didn't contain a HTTPException as root_error: "
            f"{type(report.root_error)}\n"
            f"{report.format()}"
        )

        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorMessage(
                detail=f"{report.format()}",
            ),
        )
