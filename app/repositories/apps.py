import asyncio
import json
import random

from app.constants import available_app_ids
from app.utils import SSE, send_sse_message
from decouple import config
from fastapi import HTTPException, status
from fastapi.encoders import jsonable_encoder

SHELL_SCRIPT_PATH = config("shell_script_path")


def get_app_status():
    return [
        {"id": "specter", "status": "online",
            "address": "http://192.168.0.1", "hiddenService": "blablablabla.onion"},
        {"id": "btc-pay", "status": "offline",
            "address": "http://192.168.0.1", "hiddenService": "blablablabla.onion"},
        {"id": "rtl", "status": "online",
            "address": "http://192.168.0.1", "hiddenService": "blablablabla.onion"},
        {"id": "lnbits", "status": "online",
         "address": "http://192.168.0.1", "hiddenService": "blablablabla.onion"},
    ]


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
    if(not app_id in available_app_ids):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail="script does not exist"
        )

    await send_sse_message(SSE.INSTALL_APP, {"id": app_id})
    loop = asyncio.get_event_loop()
    loop.create_task(run_bonus_script(app_id, "on"))

    return jsonable_encoder({"id": app_id})


async def uninstall_app_sub(app_id: str):
    if(not app_id in available_app_ids):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail="script does not exist"
        )

    await send_sse_message(SSE.INSTALL_APP, {"id": app_id})
    loop = asyncio.get_event_loop()
    loop.create_task(run_bonus_script(app_id, "off"))

    return jsonable_encoder({"id": app_id})


async def run_bonus_script(app_id: str, params: str):
    script_path = f"{SHELL_SCRIPT_PATH}config.scripts/bonus.{app_id}.sh"
    print(script_path)
    cmd = f"bash {script_path} {params}"

    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    stdout, stderr = await proc.communicate()

    print(f'[{cmd!r} exited with {proc.returncode}]')
    if stdout:
        print(f'[stdout]\n{stdout.decode()}')
    if stderr:
        print(f'[stderr]\n{stderr.decode()}')

    await send_sse_message(SSE.INSTALL_APP, {"id": None})
    # TODO: send installed_app_status to update the installed apps in frontend
