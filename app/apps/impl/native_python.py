from fastapi import HTTPException, status

from app.api.error_report.report import Report
from app.apps.impl.apps_base import AppsBase
from app.apps.models import AppStatus, AppStatusQueryResult
from app.external.result_type.src.result import Result


class _NotImplemented(HTTPException):
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Not available in native python mode.",
        )


class NativePythonApps(AppsBase):
    async def get_app_status_single(self, app_id: str) -> Result[AppStatus, Report]:
        raise _NotImplemented()

    async def get_app_status(self) -> Result[AppStatusQueryResult, Report]:
        raise _NotImplemented()

    async def get_app_status_advanced(self, app_id: str) -> Result[AppStatus, Report]:
        raise _NotImplemented()

    async def get_app_status_sub(self):
        raise _NotImplemented()

    async def install_app_sub(self, app_id: str):
        raise _NotImplemented()

    async def uninstall_app_sub(self, app_id: str, delete_data: bool):
        raise _NotImplemented()
