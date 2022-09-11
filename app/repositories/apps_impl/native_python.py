from app.repositories.apps_impl.apps_base import AppsBase


class NativePythonApps(AppsBase):
    async def get_app_status_single(self, app_id: str):
        raise NotImplementedError()

    async def get_app_status(self):
        raise NotImplementedError()

    async def get_app_status_sub(self):
        raise NotImplementedError()

    async def install_app_sub(self, app_id: str):
        raise NotImplementedError()

    async def uninstall_app_sub(self, app_id: str, delete_data: bool):
        raise NotImplementedError()
