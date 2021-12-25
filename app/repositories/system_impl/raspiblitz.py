from app.constants import API_VERSION
from app.models.system import (
    APIPlatform,
    HealthMessage,
    HealthMessagePriority,
    HealthState,
    SystemInfo,
)
from app.repositories.lightning import get_ln_info
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
