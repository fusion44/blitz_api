import asyncio
import logging
import os
from typing import Dict

from decouple import config
from fastapi import HTTPException, status

from app.auth.auth_handler import sign_jwt
from app.constants import API_VERSION
from app.core_utils import (
    SSE,
    broadcast_sse_msg,
    call_script,
    call_sudo_script,
    parse_key_value_text,
    redis_get,
)
from app.models.system import (
    APIPlatform,
    ConnectionInfo,
    LoginInput,
    RawDebugLogData,
    SystemInfo,
)
from app.repositories.lightning import get_ln_info
from app.repositories.system_impl.system_base import SystemBase
from app.repositories.utils.raspiblitz import password_valid

SHELL_SCRIPT_PATH = config("shell_script_path")
GET_DEBUG_LOG_SCRIPT = os.path.join(
    SHELL_SCRIPT_PATH, "config.scripts", "blitz.debug.sh"
)


class RaspiBlitzSystem(SystemBase):
    def __init__(self) -> None:
        self._check_shell_scripts_status()
        super().__init__()

    async def get_system_info(self) -> SystemInfo:

        lightning = await redis_get("lightning")
        if lightning == "" or lightning == "none":
            data_chain = await redis_get("chain")
            data_chain = f"{data_chain}net"
            data_alias = await redis_get("hostname")
            data_color = "#FF9900"
        else:
            lninfo = await get_ln_info()
            data_chain = lninfo.chains[0].network
            data_alias = lninfo.alias
            data_color = lninfo.color

        lan = await redis_get("internet_localip")
        tor = await redis_get("tor_web_addr")

        return SystemInfo(
            alias=data_alias,
            color=data_color,
            platform=APIPlatform.RASPIBLITZ,
            platform_version=await redis_get("raspiBlitzVersion"),
            api_version=API_VERSION,
            tor_web_ui=tor,
            tor_api=f"{tor}/api",
            lan_web_ui=f"http://{lan}/",
            lan_api=f"http://{lan}/api",
            ssh_address=f"admin@{lan}",
            chain=data_chain,
        )

    async def shutdown(self, reboot: bool) -> bool:
        params = ""
        if reboot:
            params = "reboot"

        script = os.path.join(SHELL_SCRIPT_PATH, "config.scripts", "blitz.shutdown.sh")
        cmd = f"sudo bash {script} {params}"

        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await proc.communicate()

        logging.info(f"[{cmd!r} exited with {proc.returncode}]")
        if stdout:
            logging.info(f"[stdout]\n{stdout.decode()}")
        if stderr:
            logging.error(f"[stderr]\n{stderr.decode()}")

        if proc.returncode > 0:
            err = stderr.decode()
            if reboot:
                await broadcast_sse_msg(SSE.SYSTEM_REBOOT_ERROR, {"error_message": err})
            else:
                await broadcast_sse_msg(
                    SSE.SYSTEM_SHUTDOWN_ERROR, {"error_message": err}
                )

            return False

        return True

    async def get_connection_info(self) -> ConnectionInfo:

        lightning = await redis_get("lightning")

        # Bitcoin RPC
        # seems to be local network that also needs open ports
        # or tor that needs hidden service

        # LND MACAROONS & TLS
        data_lnd_rest_onion = ""
        data_lnd_admin_macaroon = ""
        data_lnd_invoice_macaroon = ""
        data_lnd_readonly_macaroon = ""
        data_lnd_tls_cert = ""

        if lightning == "lnd":
            key_value_text = await call_script(
                "/home/admin/config.scripts/lnd.export.sh hexstring key-value"
            )
            key_value = parse_key_value_text(key_value_text)
            if "adminMacaroon" in key_value.keys():
                data_lnd_admin_macaroon = key_value["adminMacaroon"]
            if "invoiceMacaroon" in key_value.keys():
                data_lnd_invoice_macaroon = key_value["invoiceMacaroon"]
            if "readonlyMacaroon" in key_value.keys():
                data_lnd_readonly_macaroon = key_value["readonlyMacaroon"]
            if "tlsCert" in key_value.keys():
                data_lnd_tls_cert = key_value["tlsCert"]
            if "restTor" in key_value.keys():
                data_lnd_rest_onion = key_value["restTor"]
            if "error" in key_value.keys():
                logging.warning(f"Error from script call: {key_value['error']}")

        # ZEUS-Wallet (LND)
        data_lnd_zeus_connection_string = ""
        if lightning == "lnd":
            key_value_text = await call_script(
                "/home/admin/config.scripts/bonus.lndconnect.sh zeus-android tor key-value"
            )
            key_value = parse_key_value_text(key_value_text)
            if "lndconnect" in key_value.keys():
                data_lnd_zeus_connection_string = key_value["lndconnect"]
            if "error" in key_value.keys():
                logging.warning(f"Error from script call: {key_value['error']}")

        # ZEUS-Wallet (Core Lightning)
        data_cl_rest_zeus_connection_string = ""
        data_cl_rest_macaroon = ""
        data_cl_rest_onion = ""
        if lightning == "cl":
            key_value_text = await call_sudo_script(
                "/home/admin/config.scripts/cl.rest.sh connect mainnet key-value"
            )
            key_value = parse_key_value_text(key_value_text)
            if "connectstring" in key_value.keys():
                data_cl_rest_zeus_connection_string = key_value["connectstring"]
            if "macaroon" in key_value.keys():
                data_cl_rest_macaroon = key_value["macaroon"]
            if "toraddress" in key_value.keys():
                data_cl_rest_onion = key_value["toraddress"]
            if "error" in key_value.keys():
                logging.warning(f"Error from script call: {key_value['error']}")

        # BTC PAY CONNECTION STRING
        data_lnd_btcpay_connection_string = ""
        if lightning == "lnd":
            key_value_text = await call_script(
                "/home/admin/config.scripts/lnd.export.sh btcpay key-value"
            )
            key_value = parse_key_value_text(key_value_text)
            if "connectionString" in key_value.keys():
                data_lnd_btcpay_connection_string = key_value["connectionString"]
            if "error" in key_value.keys():
                logging.warning(f"Error from script call: {key_value['error']}")

        return ConnectionInfo(
            lnd_admin_macaroon=data_lnd_admin_macaroon,
            lnd_invoice_macaroon=data_lnd_invoice_macaroon,
            lnd_readonly_macaroon=data_lnd_readonly_macaroon,
            lnd_rest_onion=data_lnd_rest_onion,
            lnd_tls_cert=data_lnd_tls_cert,
            lnd_zeus_connection_string=data_lnd_zeus_connection_string,
            lnd_btcpay_connection_string=data_lnd_btcpay_connection_string,
            cl_rest_zeus_connection_string=data_cl_rest_zeus_connection_string,
            cl_rest_macaroon=data_cl_rest_macaroon,
            cl_rest_onion=data_cl_rest_onion,
        )

    async def login(self, i: LoginInput) -> Dict[str, str]:
        matches = await self._match_password(i)
        if matches:
            return sign_jwt()

        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, detail="Password is incorrect"
        )

    async def change_password(self, type: str, old_password: str, new_password: str):

        # check just allowed type values
        type = type.lower()
        if not type in ["a", "b", "c"]:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, detail=f"unknown password type: {type}"
            )

        # check password formatting
        if not password_valid(old_password):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, detail="old password format invalid"
            )
        if not password_valid(new_password):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, detail="new password format invalid"
            )

        # first check if old password is correct
        result = await call_script(
            f'/home/admin/config.scripts/blitz.passwords.sh check {type} "{old_password}"'
        )
        data = parse_key_value_text(result)
        if not data["correct"] == "1":
            raise HTTPException(
                status.HTTP_406_NOT_ACCEPTABLE, detail="old password not correct"
            )

        # second set new password
        script_call = (
            f'/home/admin/config.scripts/blitz.passwords.sh set {type} "{new_password}"'
        )
        if type == "c":
            # will set password c of both lnd & core lightning if installed/activated
            script_call = f'/home/admin/config.scripts/blitz.passwords.sh set c "{old_password}" "{new_password}"'
        result = await call_sudo_script(script_call)
        data = parse_key_value_text(result)

        if "error" in data.keys() and len(data["error"]) > 0:
            raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, detail=data["error"])
        return

    async def _match_password(self, i: LoginInput) -> bool:
        if password_valid(i.password):
            result = await call_script(
                f'/home/admin/config.scripts/blitz.passwords.sh check a "{i.password}"'
            )
            data = parse_key_value_text(result)
            if data["correct"] == "1":
                return True

        return False

    def _check_shell_scripts_status(self):
        if not os.path.exists(SHELL_SCRIPT_PATH):
            raise Exception(f"invalid shell script path: {SHELL_SCRIPT_PATH}")

        if not os.path.isfile(GET_DEBUG_LOG_SCRIPT):
            raise Exception(f"Required file does not exist: {GET_DEBUG_LOG_SCRIPT}")

    async def get_debug_logs_raw(self) -> RawDebugLogData:
        cmd = f"bash {GET_DEBUG_LOG_SCRIPT}"
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await proc.communicate()

        if stderr:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"""
    f"[{cmd!r} exited with {proc.returncode}]"\n
    [stderr]\n{stderr.decode()}
            """,
            )

        if stdout:
            return RawDebugLogData(raw_data=f"[stdout]\n{stdout.decode()}")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"{cmd} returned no error and no output.",
        )
