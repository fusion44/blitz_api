from abc import abstractmethod
from typing import AsyncGenerator, TypeAlias

from app.api.error_report.report import Report
from app.apps.models import (
    AppId,
    AppManageTaskMessage,
    AppStatus,
    AppStatusQueryResult,
    AppUninstallInput,
)
from app.external.result_type.src.result import Result

AppManageResult: TypeAlias = AsyncGenerator[Result[AppManageTaskMessage, Report], None]


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
    def install_app(self, app_id: AppId) -> AppManageResult:
        raise NotImplementedError()

    @abstractmethod
    def uninstall_app(self, input: AppUninstallInput) -> AppManageResult:
        raise NotImplementedError()
