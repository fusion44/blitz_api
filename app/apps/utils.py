from fastapi import HTTPException, status

from app.api.error_report.report import Report
from app.apps.models import AppId
from app.external.result_type.src.result import Err, Ok, Result


def check_app_id(id: str) -> Result[AppId, Report]:
    """
    Checks if the given app ID is valid and exists.

    Args:
        id (str): The app ID to be checked.

    Returns:
        Result[AppId, Report]: Returns an Ok result with the AppId if valid,
        otherwise returns an Err result with a Report containing error details.
    """

    match AppId.from_str(id):
        case Ok(value):
            return Ok(value)
        case Err(_):
            return Err(
                Report(
                    f"app ID '{id}' not found",
                    error=HTTPException(
                        status.HTTP_404_NOT_FOUND,
                        detail=f"app ID '{id}' not found",
                    ),
                )
            )
