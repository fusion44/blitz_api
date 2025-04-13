# ruff: noqa: E722

import asyncio
import os
import time
from typing import AsyncGenerator, List

from fastapi import HTTPException, status
from loguru import logger as logging

from app.api.config import config
from app.api.error_report.report import Frame, Report
from app.api.models import ApiErrors, ErrorMessage
from app.api.utils import exec_bash_command, parse_key_value_text
from app.apps.impl.apps_base import AppManageResult, AppsBase
from app.apps.models import (
    AppId,
    AppManagementProcessState,
    AppManageTaskMessage,
    AppOnlineStatus,
    AppStatus,
    AppStatusQueryError,
    AppStatusQueryResult,
    AppUninstallInput,
    InstallMode,
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

        result = await exec_bash_command(script_call, use_sudo=True)
        match result:
            case Ok(value):
                if value.stderr is not None and value.stderr != "":
                    return Err(
                        Report(
                            "App status script execution failed.",
                            error=HTTPException(
                                status.HTTP_500_INTERNAL_SERVER_ERROR,
                                detail=f"stderr: {value.stderr}\n"
                                "----------------------------\n"
                                f"stdout: {value.stdout}",
                            ),
                        )
                        .attach(script_call, "script_name")
                        .attach(value.stdout, "script_output", sensitive=True)
                    )
                result = value.stdout
            case Err(report):
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

        return Ok(
            AppStatusQueryResult(
                data=app_status_list, errors=report_list, timestamp=int(time.time())
            )
        )

    async def install_app(self, app_id: AppId) -> AppManageResult:
        async for result in self._manage_app(app_id, InstallMode.ON):
            yield result

    async def uninstall_app(self, input: AppUninstallInput) -> AppManageResult:
        async for result in self._manage_app(input.app_id, InstallMode.OFF):
            yield result

    async def _manage_app(self, app_id: AppId, mode: InstallMode) -> AppManageResult:
        """
        Manages the installation or uninstallation process for a specified application.

        This function validates the application ID, checks the installation status,
        and manages the process by running the appropriate scripts.
        It yields progress updates and handles errors during the process.

        Args:
            app_id (AppId): The ID of the application to be managed.
            action (InstallMode): The action to perform

        Yields:
            AppManageResult: A generator yielding the status
            of the process, including any errors encountered.
        """
        installing = mode == InstallMode.ON
        action = "installing" if installing else "uninstalling"

        res = _validate_app_id(app_id)
        if isinstance(res, Err):
            yield Ok(
                AppManageTaskMessage(
                    id=app_id,
                    mode=mode,
                    state=AppManagementProcessState.FAILURE,
                    message=ErrorMessage(
                        error_code=ApiErrors.APP_INVALID_FOR_PLATFORM,
                        detail=res.err_value.format(),
                    ),
                )
            )
            return

        res = await self._valid_installed_status(app_id, installing=installing)
        if isinstance(res, Err):
            yield Ok(
                AppManageTaskMessage(
                    id=app_id,
                    mode=mode,
                    state=AppManagementProcessState.FAILURE,
                    message=ErrorMessage(
                        error_code=ApiErrors.APP_MANAGE_ON_IS_ALREADY_INSTALLED
                        if mode == InstallMode.ON
                        else ApiErrors.APP_MANAGE_OFF_IS_NOT_INSTALLED,
                        detail=res.err_value.format(),
                    ),
                )
            )
            return

        if NODE_TYPE == "cln_grpc" and app_id in {"thunderhub", "albyhub"}:
            yield Ok(
                AppManageTaskMessage(
                    id=app_id,
                    mode=mode,
                    state=AppManagementProcessState.FAILURE,
                    message=ErrorMessage(
                        error_code=ApiErrors.APP_INVALID_FOR_PLATFORM,
                        detail=f"{app_id} not available for Core Lightning nodes",
                    ),
                )
            )
            return

        try:
            async for data in self.run_bonus_script(
                app_id, "on" if installing else "off"
            ):
                if isinstance(data, str):
                    yield Ok(
                        AppManageTaskMessage(
                            id=app_id,
                            mode=mode,
                            state=AppManagementProcessState.RUNNING,
                            message=data,
                        ),
                    )
                elif isinstance(data, AppManageTaskMessage):
                    yield Ok(data)
                else:
                    logging.error(
                        f"Unexpected data type {type(data)} in async generator"
                    )

                await asyncio.sleep(0)  # Yield control back to event loop
        except Exception as e:
            logging.error(f"Error {action} app {app_id}: {e}")
            yield Err(Report(f"Error {action} app {app_id}: {e}", error=e))

    async def run_bonus_script(
        self, app_id: AppId, params: str
    ) -> AsyncGenerator[str | AppManageTaskMessage, None]:
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

        assert proc.stdout is not None, "Process stdout is unexpectedly None"

        mode = None
        try:
            mode = InstallMode.ON if params.split()[0] == "on" else InstallMode.OFF
        except IndexError:
            logging.error(
                "Failed to extract mode from params: params is empty or malformed"
            )
            return

        try:
            log_file_name = f"/var/cache/raspiblitz/temp/install.{app_id}.log"
            stdout_full = ""
            stderr_full = ""
            data = {}
            while True:
                stdout_line = stderr_line = None
                try:
                    if proc.stderr:
                        stderr_line = await asyncio.wait_for(
                            proc.stderr.readline(), timeout=0.5
                        )
                        if stderr_line:
                            decoded = stderr_line.decode()
                            stderr_full += f"{decoded}\n"
                            logging.debug(f"[stderr]\n{decoded}")
                            yield decoded.strip()
                        else:
                            break
                except TimeoutError:
                    pass

                try:
                    stdout_line = await asyncio.wait_for(
                        proc.stdout.readline(), timeout=0.5
                    )
                    if stdout_line:
                        decoded = stdout_line.decode()
                        stdout_full += f"{decoded}\n"
                        logging.debug(f"[stdout]\n{decoded}")
                        if len(decoded) == 0:
                            continue

                        yield decoded.strip()

                        if "=" not in decoded:
                            continue

                        key, value = decoded.split("=", 1)
                        data[key] = value.strip('"').strip("'")
                    else:
                        break
                except TimeoutError:
                    pass

            await proc.wait()

            logging.debug(f"PARSED STDOUT DATA: {data}")
            if "error" in data:
                logging.error(f"FOUND `error=` returned by script: {data['error']}")
                yield AppManageTaskMessage(
                    id=app_id,
                    mode=mode,
                    state=AppManagementProcessState.FAILURE,
                    message=data["error"],
                )

            logging.info(f"WRITING LOG FILE: {log_file_name}")
            try:
                with open(log_file_name, "w", encoding="utf-8") as f:
                    f.write(f"API triggered script: {cmd}\n")
                    f.write("###### STDOUT #######\n")
                    if len(stdout_full) > 0:
                        f.write(stdout_full)
                    f.write("\n###### STDERR #######\n")
                    if len(stderr_full) > 0:
                        f.write(stderr_full)
            except Exception as e:
                logging.error(f"Error while writing log file: {e}")
                yield AppManageTaskMessage(
                    id=app_id,
                    mode=mode,
                    state=AppManagementProcessState.RUNNING,
                    message=f"Installation completed successfully, but encountered an "
                    f"error while writing the log file: {e}.",
                )

        except asyncio.CancelledError:
            proc.terminate()
            raise
        finally:
            if proc.returncode is None:
                proc.terminate()

        return

    async def _valid_installed_status(
        self, app_id: AppId, installing: bool
    ) -> Result[None, Report]:
        res = await self.get_app_status_single(app_id)
        match res:
            case Ok(value):
                if installing and value.installed:
                    return Err(Report(f"Script {app_id} is already installed"))
                if not installing and not value.installed:
                    return Err(Report(f"Script {app_id} is not installed"))
            case Err(report):
                return Err(
                    report.attach_frame(
                        Frame(f"Error while checking app status: {report.format()}")
                    )
                )

        return Ok(None)


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

    result_status = await exec_bash_command(script_call_status)
    match result_status:
        case Ok(data):
            result_status = data.stdout
        case Err(report):
            return Err(report)

    result_sync = await exec_bash_command(script_call_sync)
    match result_sync:
        case Ok(data):
            result_sync = data.stdout
        case Err(report):
            return Err(report)

    try:
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


def _validate_app_id(app_id: AppId) -> Result[None, Report]:
    if app_id not in AppId.as_str_list():
        return Err(
            Report(
                f"Script {app_id} does not exist or is not "
                "supported for current platform",
                error=HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    detail=f"Script {app_id} does not exist or is not "
                    "supported for current platform",
                ),
            )
        )

    return Ok(None)
