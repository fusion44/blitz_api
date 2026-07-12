import asyncio
import logging
import os
import time
from typing import Dict

from fastapi import HTTPException, status
from loguru import logger

from app.api.config import config
from app.api.constants import API_VERSION
from app.api.error_report.report import Report
from app.api.utils import (
    Event,
    broadcast_msg,
    exec_bash_command,
    parse_key_value_text,
    redis_get,
)
from app.auth.auth_handler import sign_jwt
from app.external.result_type.src.result.result import Err, Ok, Result
from app.lightning.service import get_ln_info
from app.system.impl.raspiblitz_utils import password_valid
from app.system.impl.system_base import SystemBase
from app.system.models import (
    APIPlatform,
    ConnectionInfo,
    LoginInput,
    RawDebugLogData,
    SystemInfo,
)

_HW_INFO_YIELD_TIME = 2

SHELL_SCRIPT_PATH = config("BAPI_RB_SHELL_SCRIPT_PATH")

if not SHELL_SCRIPT_PATH:
    logger.critical("BAPI_RB_SHELL_SCRIPT_PATH is not set or is empty.")
    exit(1)

if type(SHELL_SCRIPT_PATH) is not str:
    logger.critical("BAPI_RB_SHELL_SCRIPT_PATH is not a string.")
    exit(1)

GET_DEBUG_LOG_SCRIPT = os.path.join(
    SHELL_SCRIPT_PATH, "config.scripts", "blitz.debug.sh"
)

GET_PASSWORD_CHECK_SCRIPT = os.path.join(
    SHELL_SCRIPT_PATH, "config.scripts", "blitz.passwords.sh"
)


os.environ["TERM"] = "xterm"


def _safe_int(value: str, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_float(value: str, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


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
            code_version=await redis_get("codeVersion"),
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
                await broadcast_msg(Event.SYSTEM_REBOOT_ERROR, {"error_message": err})
            else:
                await broadcast_msg(
                    Event.SYSTEM_SHUTDOWN_ERROR, {"error_message": err}
                )

            return False

        return True

    async def get_connection_info(self) -> Result[ConnectionInfo, Report]:
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
            result = await exec_bash_command(
                "/home/admin/config.scripts/lnd.export.sh hexstring key-value"
            )
            key_value = {}
            match result:
                case Ok(data):
                    key_value = parse_key_value_text(data.stdout)
                case Err(_):
                    return result

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
            result = await exec_bash_command(
                "/home/admin/config.scripts/bonus.lndconnect.sh zeus-android tor key-value"  # noqa: E501
            )
            key_value = {}
            match result:
                case Ok(data):
                    key_value = parse_key_value_text(data.stdout)
                case Err(_):
                    return result

            if "lndconnect" in key_value.keys():
                data_lnd_zeus_connection_string = key_value["lndconnect"]
            if "error" in key_value.keys():
                logging.warning(f"Error from script call: {key_value['error']}")

        # ZEUS-Wallet (Core Lightning)
        data_cl_rest_zeus_connection_string = ""
        data_cl_rest_macaroon = ""
        data_cl_rest_onion = ""
        if lightning == "cl":
            result = await exec_bash_command(
                "/home/admin/config.scripts/cl.rest.sh connect mainnet key-value"
            )
            key_value = {}
            match result:
                case Ok(data):
                    key_value = parse_key_value_text(data.stdout)
                case Err(_):
                    return result

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
            result = await exec_bash_command(
                "/home/admin/config.scripts/lnd.export.sh btcpay key-value"
            )
            key_value = {}
            match result:
                case Ok(data):
                    key_value = parse_key_value_text(data.stdout)
                case Err(_):
                    return result

            if "connectionString" in key_value.keys():
                data_lnd_btcpay_connection_string = key_value["connectionString"]
            if "error" in key_value.keys():
                logging.warning(f"Error from script call: {key_value['error']}")

        return Ok(
            ConnectionInfo(
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
        )

    async def login(self, i: LoginInput) -> Result[Dict[str, str], Report]:
        result = await self._match_password(i)
        match result:
            case Ok(matches):
                if matches:
                    return Ok(sign_jwt())
                else:
                    raise HTTPException(
                        status.HTTP_401_UNAUTHORIZED, detail="Password is incorrect"
                    )

            case Err(report):
                raise HTTPException(
                    status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=report.format_verbose(),
                )

    async def change_password(self, type: str, old_password: str, new_password: str):
        # check just allowed type values
        if not type or type.lower() not in ["a", "b", "c"]:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, detail=f"unknown password type: {type}"
            )
        type = type.lower()

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
        result = await exec_bash_command(
            f'/home/admin/config.scripts/blitz.passwords.sh check {type} "{old_password}"',  # noqa: E501
            sensitive=True,
        )
        data = {}
        match result:
            case Ok(in_data):
                data = parse_key_value_text(in_data.stdout)
            case Err(_):
                return result

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
            script_call = f'/home/admin/config.scripts/blitz.passwords.sh set c "{old_password}" "{new_password}"'  # noqa: E501
        result = await exec_bash_command(script_call, sensitive=True)
        data = {}
        match result:
            case Ok(in_data):
                data = parse_key_value_text(in_data.stdout)
            case Err(_):
                return result

        if "error" in data.keys() and len(data["error"]) > 0:
            raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, detail=data["error"])

        return

    async def _match_password(self, i: LoginInput) -> Result[bool, Report]:
        if password_valid(i.password):
            result = await exec_bash_command(
                f'{GET_PASSWORD_CHECK_SCRIPT} check a "{i.password}"', sensitive=True
            )

            match result:
                case Ok(data):
                    data = parse_key_value_text(data.stdout)
                    if data["correct"] == "1":
                        return Ok(True)
                case Err(_):
                    return result

        return Ok(False)

    def _check_shell_scripts_status(self):
        if not os.path.exists(SHELL_SCRIPT_PATH):
            logger.critical(f"invalid shell script path: {SHELL_SCRIPT_PATH}")
            exit(1)

        if not os.path.isfile(GET_DEBUG_LOG_SCRIPT):
            logger.critical(f"required file does not exist: {GET_DEBUG_LOG_SCRIPT}")
            exit(1)

        if not os.path.isfile(GET_PASSWORD_CHECK_SCRIPT):
            logger.critical(
                f"required file does not exist: {GET_PASSWORD_CHECK_SCRIPT}"
            )
            exit(1)

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

    async def get_hardware_info(self) -> map:
        info = {}

        # On VM setups (e.g. Proxmox) the RaspiBlitz monitor scripts may not
        # populate these keys, so redis returns empty strings. Fall back to
        # zero values instead of crashing the hardware-info gatherer.
        raw_load = await redis_get("system_cpu_load")
        loads = raw_load.split(",") if raw_load else []
        iloads = [_safe_float(load) for load in loads]
        info["cpu_overall_percent"] = (
            round(sum(iloads) / len(iloads), 2) if iloads else 0
        )
        info["cpu_per_cpu_percent"] = iloads

        info["vram_total_bytes"] = (
            _safe_int(await redis_get("system_ram_mb")) * 1000 * 1000
        )

        info["vram_available_bytes"] = (
            _safe_int(await redis_get("system_ram_available_mb")) * 1000 * 1000
        )

        info["vram_used_bytes"] = (
            info["vram_total_bytes"] - info["vram_available_bytes"]
        )
        info["vram_usage_percent"] = (
            round((100 / info["vram_total_bytes"]) * info["vram_used_bytes"], 2)
            if info["vram_total_bytes"]
            else 0
        )

        info["temperatures_celsius"] = {
            "system_temp": _safe_float(await redis_get("system_temp_celsius")),
            "coretemp": [],
        }

        now = time.time()
        boot = _safe_float(await redis_get("system_up"))
        info["boot_time_timestamp"] = now - boot

        info["networks"] = {
            "internet_online": await redis_get("internet_online"),
            "tor_web_addr": await redis_get("tor_web_addr"),
            "internet_localip": await redis_get("internet_localip"),
            "internet_localiprange": await redis_get("internet_localiprange"),
        }

        # the following is just available when setup is done
        setup_phase = await redis_get("setupPhase")
        info["disks"] = []
        if setup_phase == "done":
            res = await redis_get("hdd_capacity_bytes")
            total = int(res if len(res) > 0 else 0)
            res = await redis_get("hdd_free_bytes")
            free = int(res if len(res) > 0 else 0)
            info["disks"] = [
                {
                    "device": "/",
                    "mountpoint": "/",
                    "filesystem_type": "ext4",
                    "partition_total_bytes": total,
                    "partition_used_bytes": total - free,
                    "partition_free_bytes": free,
                    "partition_percent": (
                        0 if total == 0 else round((100 / total) * free, 2)
                    ),
                }
            ]

        return info

    def get_hardware_info_yield_time(self) -> float:
        return _HW_INFO_YIELD_TIME
