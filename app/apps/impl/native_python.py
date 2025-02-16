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
        # TODO: revert me before merge to main
        return [
            {
                "id": "btcpayserver",
                "version": "v1.12.5",
                "installed": False,
                "status": "offline",
                "error": "",
            },
            {
                "id": "lnbits",
                "version": "0.11.3",
                "installed": False,
                "status": "offline",
                "error": "",
            },
            {
                "id": "rtl",
                "version": "v0.14.1",
                "installed": False,
                "status": "offline",
                "error": "",
            },
            {
                "id": "electrs",
                "installed": True,
                "configured": False,
                "status": "online",
                "localIP": "",
                "httpPort": "",
                "httpsPort": "",
                "httpsForced": False,
                "httpsSelfsigned": False,
                "hiddenService": "",
                "address": "http://:",
                "authMethod": "none",
                "details": {},
            },
            {
                "id": "btc-rpc-explorer",
                "version": "v3.4.0",
                "installed": False,
                "status": "offline",
                "error": "",
            },
            {
                "id": "mempool",
                "version": "v2.5.0",
                "installed": False,
                "status": "offline",
                "error": "",
            },
            {
                "id": "jam",
                "version": "0.2.0",
                "installed": False,
                "status": "offline",
                "error": "",
            },
            {
                "id": "thunderhub",
                "version": "v0.13.30",
                "installed": False,
                "status": "offline",
                "error": "",
            },
        ]

    async def get_app_status_advanced(self, app_id: str):
        raise _NotImplemented()

    async def get_app_status_sub(self):
        raise _NotImplemented()

    async def install_app_sub(self, app_id: str):
        raise _NotImplemented()

    async def uninstall_app_sub(self, app_id: str, delete_data: bool):
        raise _NotImplemented()
