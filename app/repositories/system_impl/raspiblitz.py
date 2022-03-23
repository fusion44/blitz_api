import asyncio
import os

from app.constants import API_VERSION
from app.models.system import (
    APIPlatform,
    HealthMessage,
    HealthMessagePriority,
    HealthState,
    SystemInfo,
)
from app.repositories.lightning import get_ln_info
from app.repositories.system import SHELL_SCRIPT_PATH
from app.utils import redis_get


async def get_system_info_impl() -> SystemInfo:
    lninfo = await get_ln_info()
    lan = await redis_get("internet_localip")
    tor = await redis_get("tor_web_addr")

    return SystemInfo(
        alias=lninfo.alias,
        color=lninfo.color,
        platform=APIPlatform.RASPIBLITZ,
        platform_version=await redis_get("raspiBlitzVersion"),
        api_version=API_VERSION,
        health=HealthState.ATTENTION_REQUIRED,
        health_messages=[
            HealthMessage(
                id=25, level=HealthMessagePriority.WARNING, message="HDD 85% full"
            )
        ],
        tor_web_ui=tor,
        tor_api=f"{tor}/api",
        lan_web_ui=f"http://{lan}/",
        lan_api=f"http://{lan}/api",
        ssh_address=f"admin@{lan}",
        chain=lninfo.chains[0].network,
    )


async def shutdown(reboot: bool):
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

    print(f"[{cmd!r} exited with {proc.returncode}]")
    if stdout:
        print(f"[stdout]\n{stdout.decode()}")
    if stderr:
        print(f"[stderr]\n{stderr.decode()}")
