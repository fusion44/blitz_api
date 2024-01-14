from abc import abstractmethod


class AppsBase:
    @abstractmethod
    async def get_app_status_single(self, app_id: str):
        raise NotImplementedError()

    @abstractmethod
    async def get_app_status(self):
        raise NotImplementedError()

    @abstractmethod
    async def get_app_status_advanced(self, app_id: str):
        raise NotImplementedError()

    @abstractmethod
    async def get_app_status_sub(self):
        raise NotImplementedError()

    @abstractmethod
    async def install_app_sub(self, app_id: str):
        raise NotImplementedError()

    @abstractmethod
    async def uninstall_app_sub(self, app_id: str, delete_data: bool):
        raise NotImplementedError()
