# ruff: noqa: E722

import asyncio
import json
import os
import random
from typing import List

from fastapi import HTTPException, status
from fastapi.encoders import jsonable_encoder
from loguru import logger as logging

from app.api.config import config
from app.api.error_report.report import Report
from app.api.utils import SSE, broadcast_sse_msg, call_sudo_script, parse_key_value_text
from app.apps.impl.apps_base import AppsBase
from app.apps.models import (
    AppId,
    AppOnlineStatus,
    AppStatus,
    AppStatusQueryError,
    AppStatusQueryResult,
)
from app.apps.utils import check_app_id
from app.external.result_type.src.result import Err, Ok, Result
from app.lightning.models import LnNodeType

temp_path = config("BAPI_RB_SHELL_SCRIPT_PATH")
temp_node_type = config("BAPI_LN_NODE")
fail_setup = False
if not isinstance(temp_path, str):
    logging.critical(f"Provided script path '{temp_path}' is not a string")
    fail_setup = True
elif not os.path.exists(temp_path):
    logging.critical(f"Provided script path '{temp_path}' is does not exist")
    fail_setup = True

if not isinstance(temp_node_type, str):
    logging.critical(f"Provided node type '{temp_node_type}' is not a string")
    fail_setup = True
elif LnNodeType.from_string(str(temp_node_type)).is_err():
    logging.critical(
        f"Unsupported node type '{temp_node_type}'. "
        f"Options: {LnNodeType.values_as_list()}."
    )

SHELL_SCRIPT_PATH: str = str(temp_path)
NODE_TYPE: LnNodeType
match LnNodeType.from_string(str(temp_node_type)):
    case Ok(value):
        NODE_TYPE = value
    case Err(error):
        logging.critical(error.format_verbose())
        fail_setup = True

if fail_setup:
    raise RuntimeError("Error during apps system setup. Consult the logs.")


class RaspiBlitzApps(AppsBase):
    async def get_app_status_single(self, app_id: str) -> Result[AppStatus, Report]:
        match check_app_id(app_id):
            case Ok(value):
                app_id = value
            case Err(report):
                return Err(report)

        try:
            script_call = (
                os.path.join(
                    SHELL_SCRIPT_PATH, "config.scripts", f"bonus.{app_id.value}.sh"
                )
                + " status"
            )
        except Exception as e:
            exception_str = str(e)
            report = Report(
                "unable to join the scripts",
                error=HTTPException(
                    status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"{exception_str}"
                ),
            )

            return Err(report)

        try:
            result = await call_sudo_script(script_call)
        except Exception as e:
            # script had error or was not able to deliver all requested data fields
            exception_str = str(e)
            report = Report(
                "App status script execution failed.",
                error=HTTPException(
                    status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"{exception_str}"
                ),
            )
            report.attach(script_call, "script_name")

            return Err(report)

        try:
            data = parse_key_value_text(result)
        except Exception as e:
            exception_str = str(e)
            report = Report(
                "Unable to parse the output of the executed script.",
                error=HTTPException(
                    status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"{exception_str}"
                ),
            )
            report.attach(script_call, "script_name")
            report.attach(result, "script_output", sensitive=True)

            return Err(report)

        try:
            keys = data.keys()
            error = str(data["error"]) if "error" in keys else None
            if error is not None and error != "":
                # script ran without any execution error, but returned an error
                # treat is as an error
                return Err(
                    Report(
                        "Script execution resulted in an error.",
                        error=HTTPException(
                            status.HTTP_500_INTERNAL_SERVER_ERROR, detail=error
                        ),
                    )
                    .attach(script_call, "script_name")
                    .attach(result, "script_output", sensitive=True)
                )

            s = AppStatus(id=app_id)
            s.installed = False
            s.version = str(data["version"]) if "version" in keys else None
            s.status = AppOnlineStatus.OFFLINE
            if "installed" in keys and data["installed"] == "1":
                s.status = AppOnlineStatus.ONLINE
                s.installed = True

            if not s.installed:
                return Ok(s)

            s.configured = False
            if "configured" in keys and data["configured"] == "1":
                s.configured = True

            s.https_self_signed = False
            if "httpsSelfsigned" in keys and data["httpsSelfsigned"] == "1":
                s.https_self_signed = True

            s.local_ip = str(data["localIP"]) if "localIP" in keys else None
            s.http_port = str(data["httpPort"]) if "httpPort" in keys else None
            s.https_port = str(data["httpsPort"]) if "httpsPort" in keys else None
            s.https_forced = (
                data["httpsForced"] == "1" if "httpsForced" in keys else False
            )
            s.address = f"http://{s.local_ip}:{s.http_port}"
            if s.https_forced:
                s.address = f"https://{s.local_ip}:{s.https_port}"
            s.hidden_service = str(data["toraddress"]) if "toraddress" in keys else None
            s.auth_method = "none"
            if "authMethod" in data.keys():
                s.auth_method = str(data["authMethod"])

            # set details for certain apps
            if app_id == AppId.MEMPOOL or app_id == AppId.BTC_RPC_EXPLORER:
                s.details = {
                    "isIndexed": data["isIndexed"],
                    "indexInfo": data["indexInfo"],
                }

            return Ok(s)

        except Exception as e:
            exception_str = str(e)
            report = Report(
                "Unable to parse the output of the app script.",
                error=HTTPException(
                    status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"{exception_str}"
                ),
            )
            report.attach(script_call, "script_name")
            report.attach(result, "script_output", sensitive=True)

            return Err(report)

    async def get_app_status_advanced(self, app_id) -> Result[AppStatus, Report]:
        if app_id not in [AppId.ELECTRS]:
            report = Report(
                "Unable to parse the output of the app script.",
                error=HTTPException(
                    status.HTTP_404_NOT_FOUND,
                    detail="App id invalid. Available app ids for the advanced "
                    f"endpoint: {AppId.ELECTRS.value}",
                ),
            )

            return Err(report)

        return await _do_electrs_status_advanced()

    async def get_app_status(self) -> Result[AppStatusQueryResult, Report]:
        app_status_list: List[AppStatus] = []
        report_list: List[AppStatusQueryError] = []
        for app_id in AppId:
            # skip app based on the node type running
            if NODE_TYPE == LnNodeType.NONE:
                # These apps require lightning to work, skip them
                if app_id in {
                    AppId.RTL,
                    AppId.LNBITS,
                    AppId.THUNDERHUB,
                    AppId.ALBYHUB,
                }:
                    continue
            elif NODE_TYPE == LnNodeType.CLN_JRPC or NODE_TYPE == LnNodeType.CLN_GRPC:
                # These apps require LND to work, skip them
                if app_id in {
                    AppId.THUNDERHUB,
                    AppId.ALBYHUB,
                }:
                    continue

            # get status (installed, etc) and append
            match await self.get_app_status_single(app_id):
                case Ok(value):
                    app_status_list.append(value)
                case Err(report):
                    logging.error(report.format_verbose())
                    report_list.append(
                        AppStatusQueryError(id=app_id, error=report.format())
                    )

        return Ok(AppStatusQueryResult(data=app_status_list, errors=report_list))

    async def get_app_status_sub(self):
        switch = True
        while True:
            status = "online" if switch else "offline"
            app_list = [
                # Specter is deactivated for now because it uses its own self signed
                # HTTPS cert that makes trouble in Chrome on last test
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
        if app_id not in available_app_ids:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail=app_id + " install script does not exist / is not supported",
            )

        if NODE_TYPE == "cln_grpc" and (app_id == "thunderhub" or app_id == "albyhub"):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail=app_id + " not available for Core Lightning nodes",
            )

        await broadcast_sse_msg(
            SSE.INSTALL_APP,
            {"id": app_id, "mode": "on", "result": "running", "details": ""},
        )

        loop = asyncio.get_event_loop()
        loop.create_task(self.run_bonus_script(app_id, "on"))

        return jsonable_encoder({"id": app_id})

    async def uninstall_app_sub(self, app_id: str, delete_data: bool):
        if app_id not in available_app_ids:
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
        # to satisfy CodeQL: test again against predefined array and
        # don't use 'user value'
        tested_app_id = ""
        for id in AppId.as_str_list():
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
            logging.debug("NO [stdout]")
        if stderr:
            logging.debug(f"[stderr]\n{stderr.decode()}")
        else:
            logging.debug("NO [stderr]")

        # create log file
        logFileName = f"/var/cache/raspiblitz/temp/install.{app_id}.log"
        logging.info(f"WRITING LOG FILE: {logFileName}")
        with open(logFileName, "w", encoding="utf-8") as f:
            f.write(f"API triggered script: {cmd}\n")
            f.write("###### STDOUT #######\n")
            if stdout:
                f.write(stdout.decode())
            f.write("\n###### STDERR #######\n")
            if stderr:
                f.write(stderr.decode())

        # sending final feedback event
        logging.debug("SENDING RESULT EVENT ...")
        if stdout:
            stdoutData = parse_key_value_text(stdout.decode())
            logging.debug(f"PARSED STDOUT DATA: {stdoutData}")
            # when there is a defined error message (if multiple it will
            # be the last one)
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
            # when there is no result (e.g. result="OK") at the end of install script
            # stdout - consider also script had error
            elif "result" not in stdoutData:
                logging.error("NO `result=` returned by script:")
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
                if "error" in updatedAppData and updatedAppData["error"] != "":
                    logging.warning("Error Detected ...")
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


async def _do_electrs_status_advanced() -> Result[AppStatus, Report]:
    app_id = AppId.ELECTRS.value
    try:
        script_call_status = (
            os.path.join(SHELL_SCRIPT_PATH, "config.scripts", f"bonus.{app_id}.sh")
            + " status showAddress"
        )

        script_call_sync = (
            os.path.join(SHELL_SCRIPT_PATH, "config.scripts", f"bonus.{app_id}.sh")
            + " status-sync"
        )
    except Exception as e:
        exception_str = str(e)
        report = Report(
            "unable to join the electrs scripts",
            error=HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"{exception_str}"
            ),
        )

        return Err(report)

    try:
        result_status = await call_sudo_script(script_call_status)
        result_sync = await call_sudo_script(script_call_sync)
        result = result_status + result_sync
    except Exception as e:
        exception_str = str(e)
        report = Report(
            "electrs status script execution failed",
            error=HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"{exception_str}"
            ),
        )
        report.attach(script_call_status, "script_name")
        report.attach(script_call_sync, "script_name")

        return Err(report)

    try:
        data = parse_key_value_text(result)
    except Exception as e:
        exception_str = str(e)
        report = Report(
            "unable to parse the output of the executed scripts",
            error=HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"{exception_str}"
            ),
        )
        report.attach(script_call_status, "script_name")
        report.attach(script_call_sync, "script_name")
        report.attach(result, "script_output", sensitive=True)

        return Err(report)

    try:
        s = AppStatus(id=AppId.ELECTRS)
        s.version = data.get("version", "")
        if data.get("installed", "0") == "0":
            s.installed = False
            return Ok(s)

        if data.get("configured", "0") == "0":
            s.configured = False
            return Ok(s)

        if data.get("serviceRunning", "0") == "0":
            s.status = AppOnlineStatus.OFFLINE
            return Ok(s)

        if "initialSynced" not in data:
            return Err(
                Report(
                    f"The RaspiBlitz {script_call_sync} doesn't "
                    "return the required data (initialSynced).",
                    error=HTTPException(
                        status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"The Raspiblitz {script_call_sync} doesn't "
                        "return the required data (initialSynced).",
                    ),
                )
            )

        s.local_ip = data.get("localIP", "")
        s.address = data.get("publicIP", "")
        s.http_port = data.get("portTCP", "")
        s.https_port = data.get("portSSL", "")
        s.hidden_service = data.get("TORaddress", "")
        s.details = {
            "initial_sync_done": data.get("initialSynced", "0") == "1",
            "block_height": data.get("blockheight", ""),
            "blockheightPercent": data.get("blockheightPercent", ""),
            "info_sync": data.get("infoSync", ""),
            "electrum_responding": data.get("electrumResponding", ""),
        }

        return Ok(s)

    except Exception as e:
        exception_str = str(e)
        report = Report(
            "unable to process the output of the executed Electrs scripts",
            error=HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"{exception_str}"
            ),
        )
        report.attach(script_call_status, "script_name")
        report.attach(script_call_sync, "script_name")

        return Err(report)
