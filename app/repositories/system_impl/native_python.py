import logging

from decouple import config

from app.constants import API_VERSION
from app.models.system import APIPlatform, ConnectionInfo, SystemInfo
from app.repositories.lightning import get_ln_info


async def get_system_info_impl() -> SystemInfo:
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


async def shutdown_impl(reboot: bool) -> bool:
    logging.info("Shutdown / reboot not supported in native_python mode.")
    return False


async def get_connection_info_impl() -> ConnectionInfo:

    # return an empty connection info object for now
    return ConnectionInfo()
