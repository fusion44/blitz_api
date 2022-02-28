import asyncio
import json
import random

from app.constants import available_app_ids
from decouple import config
from fastapi import HTTPException, status
from fastapi.encoders import jsonable_encoder

SHELL_SCRIPT_PATH = config("shell_script_path")


def get_app_status():
    return [
        {"id": "specter", "name": "Specter Desktop", "status": "online"},
        {"id": "sphinx", "name": "Sphinx Chat", "status": "online"},
        {"id": "btc-pay", "name": "BTCPay Server", "status": "offline"},
        {"id": "rtl", "name": "Ride the Lightning", "status": "online"},
        {"id": "bos", "name": "Balance of Satoshis", "status": "offline"},
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


async def install_app_sub(appId: str):
    if(not appId in available_app_ids):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail="script does not exist"
        )
    scriptPath = "%sconfig.scripts/bonus.%s.sh" % (
        SHELL_SCRIPT_PATH, appId)

    cmd = f"bash {scriptPath} on"
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
    yield jsonable_encoder({"event": "install", "data": json.dumps({"id": appId})})
