import asyncio
import json
import random
import subprocess
from decouple import config
from os import path
from fastapi import HTTPException, status


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


def installApp(appName: str):
    scriptPath = "%sconfig.scripts/bonus.%s.sh on" % (SHELL_SCRIPT_PATH, appName)
    if(not path.exists(scriptPath)):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail="script does not exist"
        )
    installResult = subprocess.call([scriptPath])
    if(installResult != 0):
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Script exited with status %s" % str(
                installResult)
        )
