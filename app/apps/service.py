import asyncio

from fastapi import HTTPException, status
from loguru import logger

from app.api.config import config
from app.api.error_report.report import Report
from app.api.models import ApiErrors, ErrorMessage
from app.api.task_utils import get_lock_status
from app.apps.cache import cache as app_cache
from app.apps.constants import AppsServiceKeys, InstallMode
from app.apps.models import AppId, AppStatus, AppStatusQueryResult, AppUninstallInput
from app.apps.tasks import manage_app_task, update_app_state_task
from app.external.result_type.src.result import Err, Ok
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


async def update_app_state_cache():
    """Starts an update task to the app status cache."""
    update_app_state_task.delay()  # type: ignore


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
    match await app_cache.get_cached_app_status():
        case Ok(values) if values:
            return values
        case Ok(_):
            # query executed, but no data was returned
            # This means the cache is empty or stale => trigger update
            update_app_state_task.delay()  # type: ignore
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Cached app status is empty. App status update task triggered.",
            )
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


async def install_app(app_id: AppId):
    res = await get_lock_status(AppsServiceKeys.APP_MANAGE_LOCK_KEY)
    match res:
        case Ok(value):
            if value:
                raise HTTPException(
                    status.HTTP_423_LOCKED,
                    detail="App install or uninstall task already running",
                )
        case Err(report):
            _handle_error(report)

    manage_app_task.delay(app_id, InstallMode.ON)  # type: ignore

    asyncio.create_task(_watcher(app_id, "install"))


async def uninstall_app(data: AppUninstallInput):
    res = await get_lock_status(AppsServiceKeys.APP_MANAGE_LOCK_KEY)
    match res:
        case Ok(value):
            if value:
                raise HTTPException(
                    status.HTTP_423_LOCKED,
                    detail="App install or uninstall task already running",
                )
        case Err(report):
            _handle_error(report)

    app_id = data.app_id

    manage_app_task.delay(app_id, InstallMode.OFF, data.keep_data)  # type: ignore

    asyncio.create_task(_watcher(app_id, "uninstall"))


async def _watcher(app_id: AppId, action: str):
    from app.apps.tasks_impl.listeners import AppManageListener

    logger.info(f"Starting app {action} listener for app {app_id}")
    listener = AppManageListener()
    await listener.connect()
    await listener.listen()
    logger.info(f"Closing app {action} listener for app {app_id}")
    logger.info("Triggering app state cache update")
    # TODO: Not sure if this is the right place to trigger the cache update
    #       or if it should be done by the API at all
    #       problem is that it's also triggered when no action was taken
    #       (e.g. when the app is already installed)
    await update_app_state_cache()


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
            ).model_dump(),
        )
