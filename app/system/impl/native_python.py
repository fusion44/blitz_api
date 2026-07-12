import secrets
from typing import Dict

import psutil
from fastapi import HTTPException, status
from loguru import logger

from app.api.config import config
from app.api.constants import API_VERSION
from app.api.error_report.report import Report
from app.auth.auth_handler import sign_jwt
from app.external.result_type.src.result.result import Err, Ok, Result
from app.lightning.service import get_ln_info
from app.system.impl.system_base import SystemBase
from app.system.models import (
    APIPlatform,
    ConnectionInfo,
    LoginInput,
    RawDebugLogData,
    SystemInfo,
)

_SLEEP_TIME = config("BAPI_GATHER_HW_INFO_INTERVAL", default=2, cast=float)
_CPU_AVG_PERIOD = config("BAPI_CPU_USAGE_AVERAGING_PERIOD", default=0.5, cast=float)
_HW_INFO_YIELD_TIME = _SLEEP_TIME + _CPU_AVG_PERIOD


class NativePythonSystem(SystemBase):
    @logger.catch(exclude=(HTTPException,))
    async def get_system_info(self) -> SystemInfo:
        lninfo = await get_ln_info()

        version = config("BAPI_NP_VERSION", default="")

        tor_api = config("BAPI_NP_TOR_ADDRESS_API_ENDPOINT", default="")
        tor_api_docs = config("BAPI_NP_TOR_ADDRESS_API_DOCS", default="")

        lan_api = config("BAPI_NP_LOCAL_ADDRESS_API_ENDPOINT", default="")
        lan_api_docs = config("BAPI_NP_LOCAL_ADDRESS_API_DOCS", default="")

        ssh_address = config("BAPI_NP_SSH_ADDRESS", default="")

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

    @logger.catch(exclude=(HTTPException,))
    async def shutdown(self, reboot: bool) -> bool:
        logger.info("Shutdown / reboot not supported in native_python mode.")
        return False

    @logger.catch(exclude=(HTTPException,))
    async def get_connection_info(self) -> Result[ConnectionInfo, Report]:
        # return an empty connection info object for now
        return Ok(ConnectionInfo())

    @logger.catch(exclude=(HTTPException,), reraise=True)
    async def login(self, i: LoginInput) -> Result[Dict[str, str], Report]:
        # https://github.com/fusion44/blitz_api/issues/255
        pw = config("BAPI_NATIVE_LOGIN_PASSWORD", cast=str)
        if not isinstance(pw, str):
            return Err(
                Report(
                    "unable to convert the .env password to a string",
                    error=HTTPException(
                        status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Password is incorrect",
                    ),
                )
            )

        if len(pw) < 8:
            return Err(
                Report(
                    "given password is less than 8 characters",
                    error=HTTPException(
                        status.HTTP_401_UNAUTHORIZED,
                        detail="given password is less than 8 characters",
                    ),
                )
            )

        matches = secrets.compare_digest(i.password, pw)
        if matches:
            return Ok(sign_jwt())

        return Err(
            Report(
                "password is incorrect",
                error=HTTPException(
                    status.HTTP_401_UNAUTHORIZED, detail="password is incorrect"
                ),
            )
        )

    async def change_password(self, type: str, old_password: str, new_password: str):
        # no @logger.catch: NotImplementedError must propagate to the service
        # layer (which turns it into a 501), not be swallowed into a None return
        raise NotImplementedError()

    async def get_debug_logs_raw(self) -> RawDebugLogData:
        raise NotImplementedError()

    @logger.catch(exclude=(HTTPException,))
    async def get_hardware_info(self) -> map:
        info = {}

        try:
            info["cpu_overall_percent"] = psutil.cpu_percent(interval=_CPU_AVG_PERIOD)
            info["cpu_per_cpu_percent"] = psutil.cpu_percent(
                interval=_CPU_AVG_PERIOD, percpu=True
            )

            v = psutil.virtual_memory()
            info["vram_total_bytes"] = v.total
            info["vram_available_bytes"] = v.available
            info["vram_used_bytes"] = v.used
            info["vram_usage_percent"] = v.percent

            s = psutil.swap_memory()
            info["swap_ram_total_bytes"] = s.total
            info["swap_used_bytes"] = s.used
            info["swap_usage_bytes"] = s.percent

            info["temperatures_celsius"] = psutil.sensors_temperatures()
            info["boot_time_timestamp"] = psutil.boot_time()

            disk_io = psutil.disk_io_counters()
            info["disk_io_read_count"] = disk_io.read_count
            info["disk_io_write_count"] = disk_io.write_count
            info["disk_io_read_bytes"] = disk_io.read_bytes
            info["disk_io_write_bytes"] = disk_io.write_bytes

            disks = []
            partitions = psutil.disk_partitions()
            for partition in partitions:
                p = {}
                p["device"] = partition.device
                p["mountpoint"] = partition.mountpoint
                p["filesystem_type"] = partition.fstype

                try:
                    usage = psutil.disk_usage(partition.mountpoint)
                    p["partition_total_bytes"] = usage.total
                    p["partition_used_bytes"] = usage.used
                    p["partition_free_bytes"] = usage.free
                    p["partition_percent"] = usage.percent
                except PermissionError:
                    continue
                disks.append(p)
            info["disks"] = disks

            nets = []
            addresses = psutil.net_if_addrs()
            for name, address in addresses.items():
                net = {}
                nets.append(net)
                net["interface_name"] = name
                for a in address:
                    if str(a.family) == "AddressFamily.AF_INET":
                        net["address"] = a.address
                    elif str(a.family) == "AddressFamily.AF_PACKET":
                        net["mac_address"] = a.address

            net_io = psutil.net_io_counters()
            info["networks"] = nets
            info["networks_bytes_sent"] = net_io.bytes_sent
            info["networks_bytes_received"] = net_io.bytes_recv

        except FileNotFoundError:
            logger.warning("Unable to access /proc/stat to get CPU stats")
        except OSError as e:
            logger.warning(
                f"""Unable to query system: {e}
                Check if the system is hardened against such calls.
                For example in Nix you must not harden the following:
                    ProtectProc = "invisible"; // to get HW info
                    ProcSubset = "pid"; // to get HW info
                    RestrictAddressFamilies = "AF_UNIX AF_INET AF_INET6"; // to get network info
                """
            )

        return info

    def get_hardware_info_yield_time(self) -> float:
        return _HW_INFO_YIELD_TIME
