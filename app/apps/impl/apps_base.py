from abc import abstractmethod

from app.api.error_report.report import Report
from app.apps.models import AppStatus, AppStatusQueryResult
from app.external.result_type.src.result import Result


class AppsBase:
    @abstractmethod
    async def get_app_status_single(self, app_id: str) -> Result[AppStatus, Report]:
        raise NotImplementedError()

    @abstractmethod
    async def get_app_status(self) -> Result[AppStatusQueryResult, Report]:
        raise NotImplementedError()

    @abstractmethod
    async def get_app_status_advanced(self, app_id: str) -> Result[AppStatus, Report]:
        raise NotImplementedError()

    @abstractmethod
    async def install_app_sub(self, app_id: str):
        raise NotImplementedError()

    @abstractmethod
    async def uninstall_app_sub(self, app_id: str, delete_data: bool):
        raise NotImplementedError()
