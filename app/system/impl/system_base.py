from abc import abstractmethod
from typing import Dict

from app.system.models import (
    ConnectionInfo,
    LoginInput,
    RawDebugLogData,
    SystemHealthInfo,
    SystemInfo,
)


class SystemBase:
    @abstractmethod
    async def get_system_info(self) -> SystemInfo:
        raise NotImplementedError()

    @abstractmethod
    async def get_system_health(self, verbose: bool) -> SystemHealthInfo:
        raise NotImplementedError()

    @abstractmethod
    async def shutdown(self, reboot: bool) -> bool:
        raise NotImplementedError()

    @abstractmethod
    async def get_connection_info(self) -> ConnectionInfo:
        raise NotImplementedError()

    @abstractmethod
    async def login(self, i: LoginInput) -> Dict[str, str]:
        raise NotImplementedError()

    @abstractmethod
    async def change_password(self, type: str, old_password: str, new_password: str):
        raise NotImplementedError()

    @abstractmethod
    async def get_debug_logs_raw(self) -> RawDebugLogData:
        raise NotImplementedError()

    @abstractmethod
    async def get_hardware_info(self) -> map:
        raise NotImplementedError()

    @abstractmethod
    def get_hardware_info_yield_time(self) -> float:
        raise NotImplementedError()
