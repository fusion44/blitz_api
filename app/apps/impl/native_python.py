from fastapi import HTTPException, status

from app.api.error_report.report import Report
from app.apps.impl.apps_base import AppManageResult, AppsBase
from app.apps.models import AppId, AppStatus, AppStatusQueryResult, AppUninstallInput
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

    def install_app(self, app_id: AppId) -> AppManageResult:
        raise NotImplementedError()

    def uninstall_app(self, input: AppUninstallInput) -> AppManageResult:
        raise NotImplementedError()
