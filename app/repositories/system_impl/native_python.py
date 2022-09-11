import logging
import secrets
from typing import Dict

from decouple import config
from fastapi import HTTPException, status

from app.auth.auth_handler import sign_jwt
from app.constants import API_VERSION
from app.models.system import (
    APIPlatform,
    ConnectionInfo,
    LoginInput,
    RawDebugLogData,
    SystemInfo,
)
from app.repositories.lightning import get_ln_info
from app.repositories.system_impl.system_base import SystemBase


class NativePythonSystem(SystemBase):
    async def get_system_info(self) -> SystemInfo:
        lninfo = await get_ln_info()

        version = config("np_version", default="")

        tor_api = config("np_tor_address_api_endpoint", default="")
        tor_api_docs = config("np_tor_address_api_docs", default="")

        lan_api = config("np_local_address_api_endpoint", default="")
        lan_api_docs = config("np_local_address_api_docs", default="")

        ssh_address = config("np_ssh_address", default="")

        return SystemInfo(
            alias=lninfo.alias,
            color=lninfo.color,
            platform=APIPlatform.NATIVE_PYTHON,
            platform_version=version,
            api_version=API_VERSION,
            tor_web_ui=tor_api_docs,
            tor_api=tor_api,
            lan_web_ui=lan_api_docs,
            lan_api=lan_api,
            ssh_address=ssh_address,
            chain=lninfo.chains[0].network,
        )

    async def shutdown(self, reboot: bool) -> bool:
        logging.info("Shutdown / reboot not supported in native_python mode.")
        return False

    async def get_connection_info(self) -> ConnectionInfo:
        # return an empty connection info object for now
        return ConnectionInfo()

    async def login(self, i: LoginInput) -> Dict[str, str]:
        matches = secrets.compare_digest(i.password, config("login_password", cast=str))
        if matches:
            return sign_jwt()

        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, detail="Password is incorrect"
        )

    async def change_password(self, type: str, old_password: str, new_password: str):
        raise NotImplementedError()

    async def get_debug_logs_raw(self) -> RawDebugLogData:
        raise NotImplementedError()
