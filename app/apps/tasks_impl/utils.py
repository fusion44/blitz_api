import json
from typing import Optional

from loguru import logger

from app.api.channel import BaseChannelNotifier
from app.api.error_report.report import Report
from app.api.models import ErrorMessage
from app.external.result_type.src.result.result import Err, Result


async def handle_task_error(
    channel_notifier: BaseChannelNotifier,
    key: str,
    action: str,
    error_message: str,
    error_code: str,
    report: Optional[Report] = None,
) -> Result[None, Report]:
    """Centralized error handling for tasks with channel notification

    Parameters
    ----------
    channel_notifier : BaseChannelNotifier
        The channel notifier to use for sending the error notification
    key : str
        The key to use for the notification
    action : str
        The action to use for the notification
    error_message : str
        The error message to include in the notification
    error_code : str
        The error code to include in the notification
    report : Optional[Report]
        The error report to include in the notification, if any

    Returns
    -------
    Result[None, Report]
        The result of the notification operation
    """
    try:
        error_payload = ErrorMessage(
            detail=error_message,
            error_code=error_code,
            report=report.format_verbose() if report else None,
        ).model_dump()

        return await channel_notifier.notify_key_change(
            key,
            action,
            None,
            json.dumps(error_payload),
        )
    except Exception as e:
        logger.exception(f"Error while handling task error: {e}")
        return Err(Report(f"Error while handling task error: {e}", error=e))
