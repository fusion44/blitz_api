"""
This module defines the task implementation for installing applications.
It handles the process of installing an app, including the Redis communication
and event notifications.
"""

from loguru import logger
from redis.asyncio import Redis
from redis.asyncio import from_url as redis_from_url

from app.api.channel import BaseChannelNotifier
from app.api.config import config
from app.api.error_report.report import Report
from app.api.models import ApiErrors, ErrorMessage
from app.api.task_utils import acquire_lock, release_update_lock
from app.apps.constants import AppsServiceKeys
from app.apps.models import (
    AppId,
    AppManagementProcessState,
    AppManageTaskMessage,
    AppUninstallInput,
    InstallMode,
)
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

LOCK_TTL_SECONDS = int(config("BAPI_LOCK_TTL_SECONDS", default=5 * 60))
if not isinstance(LOCK_TTL_SECONDS, int):
    raise TypeError("BAPI_LOCK_TTL_SECONDS must be an integer")


def _log_notify_listeners_error(action: str, id: AppId, message: Report):
    logger.error(
        f"Failed to notify Redis channel {action} task "
        f"is started for {id}: {message.format()}"
    )


async def app_manage_task_impl(
    redis_url: str, id: AppId, mode: InstallMode, keep_data: bool
):
    """
    Implementation of the install app task.

    Args:
        redis_url: The Redis connection URL
        id: The ID of the app to install
        mode: The mode of installation
        keep_data: A flag indicating whether to keep existing data after uninstallation
    """
    redis_client = None
    try:
        redis_client = redis_from_url(redis_url, decode_responses=True)
    except:
        # nothing we can do here, let the task fail
        raise

    if not isinstance(redis_client, Redis):
        raise Exception("Redis not properly initialized, got a Sentinel")

    notifier = BaseChannelNotifier(
        AppsServiceKeys.APP_MANAGE_CHANNEL_KEY, redis_url=redis_url
    )
    action = "installing" if mode == InstallMode.ON else "uninstalling"
    try:
        message = await notifier.connect()
        match message:
            case Ok(_):
                logger.info(f"App install redis channel connected for {action} of {id}")
            case Err(message):
                _log_notify_listeners_error(action, id, message)
                return await redis_client.close()

        res = await notifier.notify_key_change(
            key=AppsServiceKeys.APP_MANAGE_MESSAGE_KEY,
            new_value=AppManageTaskMessage(
                id=id,
                mode=mode,
                state=AppManagementProcessState.INITIATED,
                message="",
            ).model_dump_json(),
        )
        match res:
            case Err(message):
                _log_notify_listeners_error(action, id, message)
                return await redis_client.close()

        alock_res = await acquire_lock(
            key=AppsServiceKeys.APP_INSTALL_LOCK_KEY,
            lock_ttl=LOCK_TTL_SECONDS,
            redis=redis_client,
        )
        match alock_res:
            case Ok(acquired) if not acquired:
                logger.warning(f"{action} app lock already held. Skipping task run.")
                res = await notifier.notify_key_change(
                    key=AppsServiceKeys.APP_MANAGE_MESSAGE_KEY,
                    new_value=AppManageTaskMessage(
                        id=id,
                        mode=mode,
                        state=AppManagementProcessState.FAILURE,
                        message=ErrorMessage(
                            error_code=ApiErrors.APP_MANAGE_LOCK_HELD,
                            detail=f"App {action} task already running",
                        ),
                    ).model_dump_json(),
                )
                match res:
                    case Err(message):
                        _log_notify_listeners_error(action, id, message)

                return
            case Err(message):
                logger.error(
                    f"Failed to acquire {action} app lock: {message.format_verbose()}"
                )
                return

        logger.info(f"App {action} lock acquired for {action}ing app {id}")
        apps_impl = Apps()
        res = (
            apps_impl.install_app(app_id=id)
            if mode == InstallMode.ON
            else apps_impl.uninstall_app(
                input=AppUninstallInput(app_id=id, keep_data=keep_data)
            )
        )
        async for message in res:
            match message:
                case Ok(message) if isinstance(message, AppManageTaskMessage):
                    # OK(AppManageTaskMessage) is used to send the message to the client
                    # regardless of whether the message is an error or not
                    res = await notifier.notify_key_change(
                        key=AppsServiceKeys.APP_MANAGE_MESSAGE_KEY,
                        new_value=message.model_dump_json(),
                    )
                    match res:
                        case Err(err_message):
                            _log_notify_listeners_error(action, id, err_message)
                case Err(report) if isinstance(report, Report):
                    # This means an unknown error occurred, notify the client
                    logger.error(
                        f"Unknown error while {action}ing {id}: {report.format()}"
                    )
                    res = await notifier.notify_key_change(
                        key=AppsServiceKeys.APP_MANAGE_MESSAGE_KEY,
                        new_value=AppManageTaskMessage(
                            id=id,
                            mode=mode,
                            state=AppManagementProcessState.FAILURE,
                            message=ErrorMessage(
                                error_code=ApiErrors.UNKNOWN,
                                detail=f"An unknown error occurred during {action}ing"
                                f" of {id}. See the report for more details.",
                                report=report.format(),
                            ),
                        ).model_dump_json(),
                    )
                    match res:
                        case Err(message):
                            _log_notify_listeners_error(action, id, message)
                case data:
                    logger.error(
                        f"Unexpected data type {type(data)} in async generator"
                    )

    except Exception as e:
        logger.exception(f"Error while handling task error: {e}")
        error_report = Report(
            f"Unexpected error during app {action}: {str(e)}", error=e
        )
        res = await notifier.notify_key_change(
            key=AppsServiceKeys.APP_MANAGE_MESSAGE_KEY,
            new_value=AppManageTaskMessage(
                id=id,
                mode=mode,
                state=AppManagementProcessState.FAILURE,
                message=error_report.format(),
            ).model_dump_json(),
        )
        match res:
            case Err(report):
                _log_notify_listeners_error(action, id, report)
    finally:
        res = await release_update_lock(
            key=AppsServiceKeys.APP_INSTALL_LOCK_KEY, redis=redis_client
        )
        match res:
            case Ok(_):
                logger.info(f"App {action} lock released.")
            case Err(message):
                logger.error(f"Failed to release app {action} lock: {message.format()}")
                res = await notifier.notify_key_change(
                    key=AppsServiceKeys.APP_MANAGE_MESSAGE_KEY,
                    new_value=AppManageTaskMessage(
                        id=id,
                        mode=mode,
                        state=AppManagementProcessState.FAILURE,
                        message=f"Failed to release app {action} lock:"
                        f" {message.frames[0].message}",
                    ).model_dump_json(),
                )
                match res:
                    case Err(report):
                        _log_notify_listeners_error(action, id, report)

        await _send_finish_message(id, mode, notifier)
        if redis_client:
            await redis_client.close()


async def _send_finish_message(
    app_id: AppId, mode: InstallMode, notifier: BaseChannelNotifier
):
    message = AppManageTaskMessage(
        id=app_id,
        mode=mode,
        state=AppManagementProcessState.FINISHED,
        message="",
    )
    res = await notifier.notify_key_change(
        key=AppsServiceKeys.APP_MANAGE_MESSAGE_KEY,
        new_value=message.model_dump_json(),
    )
    match res:
        case Err(message):
            action = "installing" if mode == InstallMode.ON else "uninstalling"
            _log_notify_listeners_error(action, app_id, message)
