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
    ConnectionInfo,
)
from app.repositories.lightning import get_ln_info
from app.utils import SSE, redis_get, send_sse_message, call_script, parse_key_value_text

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

async def get_connection_info_impl() -> ConnectionInfo:

    lightning = await redis_get("lightning")

    # Bitcoin RPC
    # seems to be local network that also needs open ports
    # or tor that needs hidden service    

    # LND MACAROONS & TLS
    data_lnd_rest_onion=""
    data_lnd_admin_macaroon=""
    data_lnd_invoice_macaroon=""
    data_lnd_readonly_macaroon=""
    data_lnd_tls_cert=""

    if lightning == "lnd":
        key_value_text = await call_script("/home/admin/config.scripts/lnd.export.sh hexstring key-value")
        key_value = parse_key_value_text(key_value_text)
        if "adminMacaroon" in key_value.keys():
            data_lnd_admin_macaroon=key_value["adminMacaroon"]
        if "invoiceMacaroon" in key_value.keys():
            data_lnd_invoice_macaroon=key_value["invoiceMacaroon"]
        if "readonlyMacaroon" in key_value.keys():
            data_lnd_readonly_macaroon=key_value["readonlyMacaroon"]
        if "tlsCert" in key_value.keys():
            data_lnd_tls_cert=key_value["tlsCert"]
        if "restTor" in key_value.keys():
            data_lnd_rest_onion=key_value["restTor"]
        if "error" in key_value.keys():
            logging.warning(f"Error from script call: {key_value['error']}")

    # ZEUS-Wallet (LND)
    data_lnd_zeus_connection_string=""
    if lightning == "lnd":
        key_value_text = await call_script("/home/admin/config.scripts/bonus.lndconnect.sh zeus-android tor key-value")
        key_value = parse_key_value_text(key_value_text)
        if "lndconnect" in key_value.keys():
            data_lnd_zeus_connection_string=key_value["lndconnect"]
        if "error" in key_value.keys():
            logging.warning(f"Error from script call: {key_value['error']}")

    # ZEUS-Wallet (Core Lightning)
    data_cl_rest_zeus_connection_string=""
    data_cl_rest_macaroon=""
    data_cl_rest_onion=""
    if lightning == "cl":
        key_value_text = await call_script("/home/admin/config.scripts/cl.rest.sh connect mainnet key-value")
        key_value = parse_key_value_text(key_value_text)
        if "connectstring" in key_value.keys():
            data_cl_rest_zeus_connection_string=key_value["connectstring"]
        if "macaroon" in key_value.keys():
            data_cl_rest_macaroon=key_value["macaroon"]
        if "toraddress" in key_value.keys():
            data_cl_rest_onion=key_value["toraddress"]  
        if "error" in key_value.keys():
            logging.warning(f"Error from script call: {key_value['error']}")

    # BTC PAY CONNECTION STRING
    data_lnd_btcpay_connection_string=""
    if lightning == "lnd":
        key_value_text = await call_script("/home/admin/config.scripts/lnd.export.sh btcpay key-value")
        key_value = parse_key_value_text(key_value_text)
        if "connectionString" in key_value.keys():
            data_lnd_btcpay_connection_string=key_value["connectionString"]
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
        cl_rest_onion=data_cl_rest_onion
    )