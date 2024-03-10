import logging
import secrets
from typing import Dict

import psutil
from decouple import config
from fastapi import HTTPException, status

from app.api.constants import API_VERSION
from app.auth.auth_handler import sign_jwt
from app.lightning.service import get_ln_info
from app.system.impl.system_base import SystemBase
from app.system.models import (
    APIPlatform,
    ConnectionInfo,
    LoginInput,
    RawDebugLogData,
    SystemHealthInfo,
    SystemInfo,
)

_SLEEP_TIME = config("gather_hw_info_interval", default=2, cast=float)
_CPU_AVG_PERIOD = config("cpu_usage_averaging_period", default=0.5, cast=float)
_HW_INFO_YIELD_TIME = _SLEEP_TIME + _CPU_AVG_PERIOD


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

    async def get_system_health(self, verbose: bool) -> SystemHealthInfo:
        return SystemHealthInfo(healthy=True)

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

    async def get_hardware_info(self) -> map:
        info = {}

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

        return info

    def get_hardware_info_yield_time(self) -> float:
        return _HW_INFO_YIELD_TIME
