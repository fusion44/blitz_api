import asyncio
import logging
import os

from decouple import config

from app.constants import API_VERSION
from app.models.system import (
    APIPlatform,
    HealthMessage,
    HealthMessagePriority,
    HealthState,
    SystemInfo,
)
from app.repositories.lightning import get_ln_info
from app.utils import SSE, redis_get, send_sse_message

SHELL_SCRIPT_PATH = config("shell_script_path")


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


async def shutdown_impl(reboot: bool) -> bool:
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
            await send_sse_message(SSE.SYSTEM_REBOOT_ERROR, {"error_message": err})
        else:
            await send_sse_message(SSE.SYSTEM_SHUTDOWN_ERROR, {"error_message": err})

        return False

    return True
