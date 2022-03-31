import asyncio
import json
import logging
from multiprocessing.dummy import Array
import random

from decouple import config
from fastapi import HTTPException, status
from fastapi.encoders import jsonable_encoder

from app.constants import available_app_ids
from app.utils import SSE, send_sse_message
from app.repositories.system import call_script, parse_key_value_text

SHELL_SCRIPT_PATH = config("shell_script_path")

async def get_app_status():
    appStatusList:Array=[]
    for appID in available_app_ids:
        scriptCall=f"/home/admin/config.scripts/bonus.{appID}.sh status"
        try:
            result = await call_script(scriptCall)
            data = parse_key_value_text(result)
            if data["installed"] == "1":
                # get basic data
                status="online"
                installed=(data["installed"] == "1")
                localIP=data["localIP"]
                httpPort=data["httpPort"]
                httpsPort=data["httpsPort"]
                address=f"http://{localIP}:{httpPort}"
                hiddenService=data["toraddress"]
                details={}
                # mofify for some apps
                if appID=="specter" or appID=="lnbits" or appID=="btcpayserver":
                    address=f"https://{localIP}:{httpsPort}"
                if appID=="mempool" or appID=="btc-rpc-explorer":
                    details={
                        "isIndexed": data["isIndexed"],
                        "indexInfo": data["indexInfo"]
                    }
                appStatusList.append({
                "id": appID,
                "installed": installed,
                "status": status,
                "address": address,
                "hiddenService": hiddenService,
                "details": details
                })
            else:
                appStatusList.append({
                "id": f"{appID}",
                "installed": (data["installed"] == "1"),
                "status": "offline"
                })
        except:
            # script had error or was not able to deliver all requested data fields
            logging.warning(f"error on calling: {scriptCall}")
            appStatusList.append({
                "id": f"{appID}",
                "error": f"script not working for api: {scriptCall}",
            })
    return appStatusList


async def get_app_status_sub():
    switch = True
    while True:
        status = "online" if switch else "offline"
        app_list = [
            {"id": "specter", "name": "Specter Desktop", "status": status},
            {"id": "sphinx", "name": "Sphinx Chat", "status": status},
            {"id": "btc-pay", "name": "BTCPay Server", "status": status},
            {"id": "rtl", "name": "Ride the Lightning", "status": status},
            {"id": "bos", "name": "Balance of Satoshis", "status": status},
        ]
        i = random.randint(1, len(app_list))
        yield json.dumps(app_list[i - 1])
        await asyncio.sleep(4)
        switch = not switch


async def install_app_sub(app_id: str):
    if not app_id in available_app_ids:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail=app_id + "install script not exist/supported"
        )

    await send_sse_message(SSE.INSTALL_APP, {"id": app_id})
    loop = asyncio.get_event_loop()
    loop.create_task(run_bonus_script(app_id, "on"))

    return jsonable_encoder({"id": app_id})


async def uninstall_app_sub(app_id: str):
    if not app_id in available_app_ids:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="script not exist/supported")

    await send_sse_message(SSE.INSTALL_APP, {"id": app_id})
    loop = asyncio.get_event_loop()
    loop.create_task(run_bonus_script(app_id, "off"))

    return jsonable_encoder({"id": app_id})


async def run_bonus_script(app_id: str, params: str):
    script_path = f"{SHELL_SCRIPT_PATH}config.scripts/bonus.{app_id}.sh"
    cmd = f"bash {script_path} {params}"

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

    await send_sse_message(SSE.INSTALL_APP, {"id": None})
    # TODO: send installed_app_status to update the installed apps in frontend
