import asyncio
import json
import os
import random
from typing import List

from decouple import config
from fastapi import HTTPException, status
from fastapi.encoders import jsonable_encoder
from loguru import logger as logging

from app.api.utils import SSE, broadcast_sse_msg, call_sudo_script, parse_key_value_text
from app.apps.impl.apps_base import AppsBase

available_app_ids = {
    "btc-rpc-explorer",
    "rtl",
    # Specter is deactivated for now because it uses its own self signed HTTPS cert that makes trouble in Chrome on last test
    # "specter",
    "btcpayserver",
    "lnbits",
    "mempool",
    "thunderhub",
    "jam",
}


SHELL_SCRIPT_PATH = config("shell_script_path")

node_type = config("ln_node")


class RaspiBlitzApps(AppsBase):
    async def get_app_status_single(self, app_id):
        if app_id not in available_app_ids:
            return {
                "id": f"{app_id}",
                "error": f"appID not in list",
            }
        script_call = (
            os.path.join(SHELL_SCRIPT_PATH, "config.scripts", f"bonus.{app_id}.sh")
            + " status"
        )

        try:
            result = await call_sudo_script(script_call)
        except:
            # script had error or was not able to deliver all requested data fields
            logging.warning(f"error on calling: {script_call}")
            return {
                "id": f"{app_id}",
                "error": f"script not working for api: {script_call}",
            }

        try:
            data = parse_key_value_text(result)
        except:
            logging.warning(f"error on parsing: {result}")
            return {
                "id": f"{app_id}",
                "error": f"script result parsing error: {script_call}",
            }

        try:
            error = ""
            if "error" in data.keys():
                error = data["error"]

            version = ""
            if "version" in data.keys():
                version = data["version"]

            if data["installed"] == "1":
                # get basic data
                status = "online"
                installed = data["installed"] == "1"
                localIP = data["localIP"]
                httpPort = data["httpPort"]
                httpsPort = data["httpsPort"]
                httpsForced = data["httpsForced"]
                httpsSelfsigned = data["httpsSelfsigned"]
                address = f"http://{localIP}:{httpPort}"
                if httpsForced == "1":
                    address = f"https://{localIP}:{httpsPort}"
                hiddenService = data["toraddress"]
                authMethod = "none"
                if "authMethod" in data.keys():
                    authMethod = data["authMethod"]
                details = {}

                # set details for certain apps
                if app_id == "mempool" or app_id == "btc-rpc-explorer":
                    details = {
                        "isIndexed": data["isIndexed"],
                        "indexInfo": data["indexInfo"],
                    }
                return {
                    "id": app_id,
                    "version": version,
                    "installed": installed,
                    "status": status,
                    "address": address,
                    "httpsForced": httpsForced,
                    "httpsSelfsigned": httpsSelfsigned,
                    "hiddenService": hiddenService,
                    "authMethod": authMethod,
                    "details": details,
                    "error": error,
                }
            else:
                return {
                    "id": app_id,
                    "version": version,
                    "installed": False,
                    "status": "offline",
                    "error": error,
                }
        except:
            logging.warning(f"error on repackage data: {result}")
            return {
                "id": f"{app_id}",
                "error": f"script result processing error: {script_call}",
            }

    async def get_app_status(self):
        appStatusList: List = []
        for appID in available_app_ids:
            # skip app based on node running
            if node_type == "" or node_type == "none":
                if appID == "rtl":
                    continue
                if appID == "lnbits":
                    continue
                if appID == "thunderhub":
                    continue
            elif node_type == "cln_grpc":
                if appID == "thunderhub":
                    continue
            # elif node_type="lnd_grpc":

            # get status (installed, etc) and append
            appStatusList.append(await self.get_app_status_single(appID))

        return appStatusList

    async def get_app_status_sub(self):
        switch = True
        while True:
            status = "online" if switch else "offline"
            app_list = [
                # Specter is deactivated for now because it uses its own self signed HTTPS cert that makes trouble in Chrome on last test
                # also see: app/constants.py where specter is deactivated
                # {"id": "specter", "name": "Specter Desktop", "status": status},
                {"id": "sphinx", "name": "Sphinx Chat", "status": status},
                {"id": "btc-pay", "name": "BTCPay Server", "status": status},
                {"id": "rtl", "name": "Ride the Lightning", "status": status},
                {"id": "bos", "name": "Balance of Satoshis", "status": status},
            ]
            i = random.randint(1, len(app_list))
            yield json.dumps(app_list[i - 1])
            await asyncio.sleep(4)
            switch = not switch

    async def install_app_sub(self, app_id: str):
        if not app_id in available_app_ids:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail=app_id + "install script does not exist / is not supported",
            )

        await broadcast_sse_msg(
            SSE.INSTALL_APP,
            {"id": app_id, "mode": "on", "result": "running", "details": ""},
        )

        loop = asyncio.get_event_loop()
        loop.create_task(self.run_bonus_script(app_id, "on"))

        return jsonable_encoder({"id": app_id})

    async def uninstall_app_sub(self, app_id: str, delete_data: bool):
        if not app_id in available_app_ids:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, detail="script not exist/supported"
            )

        await broadcast_sse_msg(
            SSE.INSTALL_APP,
            {"id": app_id, "mode": "off", "result": "running", "details": ""},
        )

        deleteDataFlag = " --keep-data"
        if delete_data:
            deleteDataFlag = " --delete-data"
        loop = asyncio.get_event_loop()
        loop.create_task(self.run_bonus_script(app_id, f"off{deleteDataFlag}"))

        return jsonable_encoder({"id": app_id})

    async def run_bonus_script(self, app_id: str, params: str):
        # to satisfy CodeQL: test again against predefined array and don't use 'user value'
        tested_app_id = ""
        for id in available_app_ids:
            if id == app_id:
                tested_app_id = id

        # run script and get results
        script_path = f"{SHELL_SCRIPT_PATH}/config.scripts/bonus.{tested_app_id}.sh"
        cmd = f"bash {script_path} {params}"
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        # extracting mode from params
        mode = params.split()[0]

        # logging to console
        if stdout:
            logging.debug(f"[stdout]\n{stdout.decode()}")
        else:
            logging.debug(f"NO [stdout]")
        if stderr:
            logging.debug(f"[stderr]\n{stderr.decode()}")
        else:
            logging.debug(f"NO [stderr]")

        # create log file
        logFileName = f"/var/cache/raspiblitz/temp/install.{app_id}.log"
        logging.info(f"WRITING LOG FILE: {logFileName}")
        with open(logFileName, "w", encoding="utf-8") as f:
            f.write(f"API triggered script: {cmd}\n")
            f.write(f"###### STDOUT #######\n")
            if stdout:
                f.write(stdout.decode())
            f.write(f"\n###### STDERR #######\n")
            if stderr:
                f.write(stderr.decode())

        # sending final feedback event
        logging.debug(f"SENDING RESULT EVENT ...")
        if stdout:
            stdoutData = parse_key_value_text(stdout.decode())
            logging.debug(f"PARSED STDOUT DATA: {stdoutData}")
            # when there is a defined error message (if multiple it wil lbe the last one)
            if "error" in stdoutData:
                logging.error(
                    f"FOUND `error=` returned by script: {stdoutData['error']}"
                )
                await broadcast_sse_msg(
                    SSE.INSTALL_APP,
                    {
                        "id": app_id,
                        "mode": mode,
                        "result": "fail",
                        "details": stdoutData["error"],
                    },
                )
            # when there is no result (e.g. result="OK") at the end of install script stdout - consider also script had error
            elif not "result" in stdoutData:
                logging.error(f"NO `result=` returned by script:")
                await broadcast_sse_msg(
                    SSE.INSTALL_APP,
                    {
                        "id": app_id,
                        "mode": mode,
                        "result": "fail",
                        "details": "install script threw an error",
                    },
                )
            # nothing above consider success
            else:
                # check if script was effective
                updatedAppData = await self.get_app_status_single(app_id)

                # in case of script error
                if updatedAppData["error"] != "":
                    logging.warning(f"Error Detected ...")
                    logging.warning(f"updatedAppData: {updatedAppData}")
                    await broadcast_sse_msg(
                        SSE.INSTALL_APP,
                        {
                            "id": app_id,
                            "mode": mode,
                            "result": "fail",
                            "details": updatedAppData["error"],
                        },
                    )

                # if install was running
                elif mode == "on":
                    if updatedAppData["installed"]:
                        logging.info(f"WIN - install of {app_id} was effective")
                        await broadcast_sse_msg(
                            SSE.INSTALL_APP,
                            {
                                "id": app_id,
                                "mode": mode,
                                "result": "win",
                                "httpsForced": updatedAppData["httpsForced"],
                                "httpsSelfsigned": updatedAppData["httpsSelfsigned"],
                                "details": stdoutData["result"],
                            },
                        )
                        await broadcast_sse_msg(
                            SSE.INSTALLED_APP_STATUS, [updatedAppData]
                        )
                    else:
                        logging.error(f"FAIL - {app_id} was not installed")
                        logging.debug(f"updatedAppData: {updatedAppData}")
                        logging.debug(f"params: {params}")
                        await broadcast_sse_msg(
                            SSE.INSTALL_APP,
                            {
                                "id": app_id,
                                "mode": mode,
                                "result": "fail",
                                "details": "install was not effective",
                            },
                        )
                        await broadcast_sse_msg(
                            SSE.INSTALLED_APP_STATUS, [updatedAppData]
                        )

                elif mode == "off":
                    await broadcast_sse_msg(
                        SSE.INSTALL_APP,
                        {"id": app_id, "mode": mode, "result": "win"},
                    )
                    await broadcast_sse_msg(SSE.INSTALLED_APP_STATUS, [updatedAppData])

                    if not updatedAppData["installed"]:
                        logging.info(f"WIN - uninstall of {app_id} was effective")
                        return

                    logging.error(f"FAIL - {app_id} was not uninstalled")
                    logging.debug(f"updatedAppData: {updatedAppData}")
                    logging.debug(f"params: {params}")
                    return
