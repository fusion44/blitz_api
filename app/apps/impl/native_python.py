from fastapi import HTTPException, status

from app.apps.impl.apps_base import AppsBase


class _NotImplemented(HTTPException):
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Not available in native python mode.",
        )


class NativePythonApps(AppsBase):
    async def get_app_status_single(self, app_id: str):
        raise _NotImplemented()

    async def get_app_status(self):
        raise _NotImplemented()

    async def get_app_status_sub(self):
        raise _NotImplemented()

    async def install_app_sub(self, app_id: str):
        raise _NotImplemented()

    async def uninstall_app_sub(self, app_id: str, delete_data: bool):
        raise _NotImplemented()
