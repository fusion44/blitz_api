import asyncio
import json
import logging
from multiprocessing.dummy import Array
import random
from sqlite3 import paramstyle

from decouple import config
from fastapi import HTTPException, status
from fastapi.encoders import jsonable_encoder

from app.constants import available_app_ids
from app.utils import SSE, send_sse_message
from app.repositories.system import call_script, parse_key_value_text

SHELL_SCRIPT_PATH = config("shell_script_path")

async def get_app_status_single(app_iD):
    if app_iD not in available_app_ids:
        return {
            "id": f"{app_iD}",
            "error": f"appID not in list",
        }
    script_call=f"/home/admin/config.scripts/bonus.{app_iD}.sh status"
    try:
        result = await call_script(script_call)
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
            if app_iD=="specter" or app_iD=="lnbits" or app_iD=="btcpayserver":
                address=f"https://{localIP}:{httpsPort}"
            if app_iD=="mempool" or app_iD=="btc-rpc-explorer":
                details={
                    "isIndexed": data["isIndexed"],
                    "indexInfo": data["indexInfo"]
                }
            return {
            "id": app_iD,
            "installed": installed,
            "status": status,
            "address": address,
            "hiddenService": hiddenService,
            "details": details
            }
        else:
            return {
            "id": f"{app_iD}",
            "installed": (data["installed"] == "1"),
            "status": "offline"
            }
    except:
        # script had error or was not able to deliver all requested data fields
        logging.warning(f"error on calling: {script_call}")
        return {
            "id": f"{app_iD}",
            "error": f"script not working for api: {script_call}",
        }

async def get_app_status():
    appStatusList:Array=[]
    for appID in available_app_ids:
        appStatusList.append(await get_app_status_single(appID))
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

    await send_sse_message(SSE.INSTALL_APP, {"id": app_id, "mode": "on", "result": "running", "details": ""})

    loop = asyncio.get_event_loop()
    loop.create_task(run_bonus_script(app_id, "on"))

    return jsonable_encoder({"id": app_id})


async def uninstall_app_sub(app_id: str, delete_data: bool):
    if not app_id in available_app_ids:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="script not exist/supported")

    await send_sse_message(SSE.INSTALL_APP, {"id": app_id, "mode": "off", "result": "running", "details": ""})

    deleteDataFlag=" --keep-data"
    if delete_data: deleteDataFlag=" --delete-data"
    loop = asyncio.get_event_loop()
    loop.create_task(run_bonus_script(app_id, f"off{deleteDataFlag}"))

    return jsonable_encoder({"id": app_id})

async def run_bonus_script(app_id: str, params: str):

    # run script and get results
    script_path = f"{SHELL_SCRIPT_PATH}/config.scripts/bonus.{app_id}.sh"
    cmd = f"bash {script_path} {params}"
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    logging.info(f"[{cmd!r} exited with {proc.returncode}]")

    # logging to console
    logging.warning(f"INSTALL RESULT: cmd({id}) params:{params}")
    if stdout:
        logging.info(f"[stdout]\n{stdout.decode()}")
    else:
        logging.error(f"NO [stdout]")   
    if stderr:
        logging.error(f"[stderr]\n{stderr.decode()}")
    else:
        logging.error(f"NO [stderr]")   

    # create log file
    logFileName=f"/var/cache/raspiblitz/temp/install.{app_id}.log"
    with open(logFileName, "w", encoding="utf-8") as f:
        f.write(f"API triggred script: {cmd}\n")
        f.write(f"###### STDOUT #######\n")
        if stdout:
            f.write(stdout.decode())
        f.write(f"\n###### STDERR #######\n")
        if stderr:
            f.write(stderr.decode())

    # sending final feedback event
    if stdout:
        stdoutData=parse_key_value_text(stdout.decode())
        # when there is a defined error message (if multiple it wil lbe the last one)
        if "error" in stdoutData:
            await send_sse_message(SSE.INSTALL_APP, {"id": app_id, "mode": params, "result": "fail", "details": stdoutData["error"]})
        # when there is no result (e.g. result="OK") at the end of install script stdout - consider also script had error
        elif not "result" in stdoutData:
            await send_sse_message(SSE.INSTALL_APP, {"id": app_id, "mode": params, "result": "fail", "details": "install script did not ran thru"})
        # nothing above consider success
        else:

            # check if script was effective
            updatedAppData = await get_app_status_single(app_id)
            if updatedAppData["installed"] and params=="on":
                await send_sse_message(SSE.INSTALL_APP, {"id": app_id, "mode": "on", "result": "win", "details": stdoutData["result"]})
            elif not updatedAppData["installed"] and params=="off":
                await send_sse_message(SSE.INSTALL_APP, {"id": app_id, "mode": "off", "result": "win", "details": stdoutData["result"]})
            else:
                await send_sse_message(SSE.INSTALL_APP, {"id": app_id, "mode": "off", "result": "fail", "details": "script ran thru but was not effective"})
            
            # send an updated state if that app
            await send_sse_message(SSE.INSTALLED_APP_STATUS, [updatedAppData])
    else:
        logging.warning(f"Install Feedback Event: fail no stdout")
        await send_sse_message(SSE.INSTALL_APP, {"id": app_id, "mode": params, "result": "fail", "details": "no stdout"})