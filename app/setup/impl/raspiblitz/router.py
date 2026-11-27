import asyncio
import fcntl
import logging
import os
import tempfile

from fastapi import APIRouter, HTTPException, status
from fastapi.params import Depends
from loguru import logger
from pydantic import BaseModel

from app.api.utils import parse_key_value_lines, redis_get
from app.auth.auth_bearer import JWTBearer
from app.auth.auth_handler import sign_jwt
from app.system.impl.raspiblitz import RaspiBlitzSystem
from app.system.impl.raspiblitz_utils import name_valid, password_valid

router = APIRouter(prefix="/setup", tags=["RaspiBlitz Setup"])

setupFilePath = "/run/raspiblitz-setup/raspiblitz.setup"
setupRequestPath = "/run/raspiblitz-setup/request/raspiblitz.setup"
configFilePath = "/mnt/hdd/raspiblitz.conf"


async def _call_script(scriptPath) -> str:
    cmd = f"bash {scriptPath}"
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if stdout:
        return stdout.decode()
    if stderr:
        logger.error(stderr.decode())
    return ""


# can always be called without credentials to check if
# the system needs or is in setup (setupPhase!="done")
# for example in the beginning setupPhase can be (see controlSetupDialog.sh)
# 1) recovery = same version on fresh sd card
# 2) update = updated version on fresh sd card
# 3) migration = hdd got data from another node project
# 4) setup = a fresh blitz to setup
@router.get("/status")
async def get_status():
    setupPhase = await redis_get("setupPhase")
    state = await redis_get("state")
    message = await redis_get("message")
    if setupPhase == "done":
        try:
            btc_default_sync_initial_done = await redis_get(
                "btc_default_sync_initial_done"
            )
            if btc_default_sync_initial_done == "1":
                initialsync = "done"
            else:
                initialsync = "running"
        except Exception:
            initialsync = ""
    else:
        initialsync = ""
    return {
        "setupPhase": setupPhase,
        "state": state,
        "message": message,
        "initialsync": initialsync,
    }


# if setupPhase!="done" && state="waitsetup" then
# 'setup/setup_start_info' should be called
# We can do the "MIGRATION" option later - because it would need an additional step
# after formatting hdd
# People that need to migrate can do for now by SSH option


@router.get("/setup-start-info")
async def setup_start_info():
    # first check that node is really in setup state
    setupPhase = await redis_get("setupPhase")
    state = await redis_get("state")
    if state != "waitsetup":
        logging.warning("/setup-start-info can only be called when nodes awaits setup")
        return HTTPException(status.status.HTTP_405_METHOD_NOT_ALLOWED)

    # get all the additional info needed to do setup dialog
    hddGotMigrationData = await redis_get("hddGotMigrationData")
    hddGotBlockchain = await redis_get("system_setup_storageHasReusableBlocks")
    migrationMode = await redis_get("migrationMode")
    lan = await redis_get("internet_localip")
    tor = await redis_get("tor_web_addr")
    # return info as JSON
    return {
        "setupPhase": setupPhase,
        "migrationMode": migrationMode,  # 'normal', 'outdatedLightning'
        "hddGotMigrationData": hddGotMigrationData,  # 'umbrel', 'mynode', 'citadel'
        "hddGotBlockchain": hddGotBlockchain,
        "ssh_login": f"ssh admin@{lan}",
        "tor_web_ui": tor,
    }


def write_text_file(filename: str, arrayOfLines):
    # A previous SSH setup may own the old record. Publish a complete,
    # private file from the API account before notifying the bootstrap.
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=os.path.dirname(filename), delete=False
    ) as f:
        try:
            f.write("\n".join(arrayOfLines))
            f.flush()
            # The bootstrap created this directory setgid admin. SSH and API
            # both need to read the record for the authenticated final dialog.
            os.fchmod(f.fileno(), 0o640)
            os.replace(f.name, filename)
        finally:
            if os.path.exists(f.name):
                os.unlink(f.name)


class StartDoneData(BaseModel):
    hostname: str = ""
    forceFreshSetup: bool = False
    keepBlockchain: bool = True
    lightning: str = ""
    passwordA: str = ""
    passwordB: str = ""
    passwordC: str = ""


# With all this info the WebUi can run its own runs its dialogs and in the end makes a
# call to
@router.post("/setup-start-done")
async def setup_start_done(data: StartDoneData):
    lock_path = os.path.join(os.path.dirname(setupFilePath), "submit.lock")
    try:
        lock_file = open(lock_path, "rb")
    except FileNotFoundError:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Use the running system's SSH setup or update the system and API together.",
        ) from None
    with lock_file:
        try:
            fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise HTTPException(status.HTTP_409_CONFLICT, "Another setup is in progress.") from None
        return await _complete_setup(data)


async def _complete_setup(data: StartDoneData):
    # first check that node is really in setup state
    setupPhase = await redis_get("setupPhase")
    state = await redis_get("state")
    hddGotBlockchain = await redis_get("system_setup_storageHasReusableBlocks")

    if state != "waitsetup":
        logging.warning("/setup-start-done can only be called when nodes awaits setup")
        raise HTTPException(status.HTTP_405_METHOD_NOT_ALLOWED)

    # check if a fresh setup is forced
    if data.forceFreshSetup:
        logging.warning("forcing node to fresh setup")
        setupPhase = "setup"

    #### SETUP ####
    if setupPhase == "setup":
        if "keepBlockchain" not in data.model_fields_set:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Confirm which drive data to keep.")
        if not name_valid(data.hostname):
            logging.warning("hostname is not valid")
            raise HTTPException(status.HTTP_400_BAD_REQUEST)
        if data.lightning not in ("lnd", "cl", "none"):
            logging.warning("lightning is not valid")
            raise HTTPException(status.HTTP_400_BAD_REQUEST)
        if not password_valid(data.passwordA):
            logging.warning("passwordA is not valid")
            raise HTTPException(status.HTTP_400_BAD_REQUEST)
        if not password_valid(data.passwordB):
            logging.warning("passwordB is not valid")
            raise HTTPException(status.HTTP_400_BAD_REQUEST)
        if data.lightning != "none" and not password_valid(data.passwordC):
            logging.warning("passwordC is not valid")
            raise HTTPException(status.HTTP_400_BAD_REQUEST)
        if hddGotBlockchain != "1" and data.keepBlockchain:
            logging.warning("cannot keep blockchain that does not exists")
            raise HTTPException(status.HTTP_400_BAD_REQUEST)
        if data.keepBlockchain:
            delete_data = "keepBlockchain"
            formatHDD = 0
            cleanHDD = 1
        else:
            delete_data = "all"
            formatHDD = 1
            cleanHDD = 0
        write_text_file(
            setupRequestPath,
            [
                "menuchoice=setup",
                "systemCopy=0",
                f"deleteData={delete_data}",
                # Older bootstraps read these two flags.
                f"formatHDD={formatHDD}",
                f"cleanHDD={cleanHDD}",
                "network=bitcoin",
                "chain=main",
                f"lightning={data.lightning}",
                f"hostname={data.hostname}",
                "setPasswordA=1",
                "setPasswordB=1",
                f"setPasswordC={int(data.lightning != 'none')}",
                f"passwordA='{data.passwordA}'",
                f"passwordB='{data.passwordB}'",
                f"passwordC='{data.passwordC}'" if data.lightning != "none" else "passwordC=''",
                "",
            ],
        )

    #### RECOVERY ####
    elif setupPhase == "recovery" or setupPhase == "update":
        logging.warning("check recovery data")
        if not password_valid(data.passwordA):
            logging.warning("passwordA is not valid")
            raise HTTPException(status.HTTP_400_BAD_REQUEST)
        write_text_file(
            setupRequestPath, ["setPasswordA=1", f"passwordA='{data.passwordA}'"]
        )

    #### MIGRATION ####
    elif setupPhase == "migration":
        logging.warning("check migration data")
        hddGotMigrationData = await redis_get("hddGotMigrationData")
        if hddGotMigrationData == "":
            logging.warning("hddGotMigrationData is not available")
            raise HTTPException(status.HTTP_400_BAD_REQUEST)
        if not password_valid(data.passwordA):
            logging.warning("passwordA is not valid")
            raise HTTPException(status.HTTP_400_BAD_REQUEST)
        if not password_valid(data.passwordB):
            logging.warning("passwordB is not valid")
            raise HTTPException(status.HTTP_400_BAD_REQUEST)
        if not password_valid(data.passwordC):
            logging.warning("passwordC is not valid")
            raise HTTPException(status.HTTP_400_BAD_REQUEST)
        write_text_file(
            setupRequestPath,
            [
                f"migrationOS={hddGotMigrationData}",
                "setPasswordA=1",
                "setPasswordB=1",
                "setPasswordC=1",
                f"passwordA='{data.passwordA}'",
                f"passwordB='{data.passwordB}'",
                f"passwordC='{data.passwordC}'",
            ],
        )

    else:
        logging.warning(f"not handled setupPhase state ({setupPhase})")
        raise HTTPException(status.HTTP_405_METHOD_NOT_ALLOWED)

    await _call_script("/home/admin/_cache.sh set state waitprovision")

    # TODO: Following input parameters:
    # lightning='lnd', 'cl' or 'none'
    # network=bitcoin
    # chain=main
    # hostname=[string]
    # passwordA=[string]
    # passwordB=[string]
    # passwordC=[string] (might be empty of no lightning was chosen)
    # lndrescue=[path] (might be used later if lnd rescue file upload is offered)
    # clrescue=[path] (might be used later if c-lightning rescue file upload is offered)
    # seedWords= (might be used later if we offer recover from seed words)
    # seedPassword= (might be used later if we offer recover from seed words)
    # migrationFile=[path] (might be used later if we offer raspiblitz migration)
    # those values get stored in: /run/raspiblitz-setup/raspiblitz.setup
    # also a skeleton raspiblitz.conf gets created (see controlSetupDialog.sh Line 318)
    # and then API sets state to `waitprovision` to kick-off provision

    return sign_jwt()


# WebUI now loops getting status until state=`waitfinal` then calls:
@router.get("/setup-final-info", dependencies=[Depends(JWTBearer())])
async def setup_final_info():
    # TODO: return info on setup final
    # during the process some data might be written to
    # /run/raspiblitz-setup/raspiblitz.setup
    # seedwordsNEW='${seedwords}
    # seedwords6x4NEW='${seedwords6x4}
    # syncProgressFull=[percent] = (later WebUi can offer sync from another RaspiBlitz)

    # first check that node is really in setup state
    await redis_get("setupPhase")
    state = await redis_get("state")
    if state != "waitfinal":
        logging.warning(
            f"/setup-final-info can only be called when nodes awaits final ({state})"
        )
        return HTTPException(status.HTTP_405_METHOD_NOT_ALLOWED)

    result_lines = []
    with open(setupFilePath, "r") as setup_file:
        result_lines = setup_file.readlines()
    data = parse_key_value_lines(result_lines)
    try:
        seedwordsNEW = data["seedwordsNEW"]
    except Exception:
        seedwordsNEW = ""

    return {"seedwordsNEW": seedwordsNEW}


# When WebUI displayed seed words & user confirmed write the calls:
@router.post("/setup-final-done", dependencies=[Depends(JWTBearer())])
async def setup_final_done():
    # first check that node is really in setup state
    await redis_get("setupPhase")
    state = await redis_get("state")
    if state != "waitfinal":
        logging.warning("/setup-final-done can only be called when nodes awaits final")
        return HTTPException(status.HTTP_405_METHOD_NOT_ALLOWED)

    await _call_script("/home/admin/_cache.sh set state donefinal")
    return {"state": "donefinal"}


@router.get("/shutdown")
async def get_shutdown():
    # only allow unauthorized shutdowns during setup
    setupPhase = await redis_get("setupPhase")
    state = await redis_get("state")
    if setupPhase == "done":
        logging.warning("can only be called when the nodes is not finalized yet")
        return HTTPException(status.status.HTTP_405_METHOD_NOT_ALLOWED)
    if state != "waitsetup":
        logging.warning("can only be called when nodes awaits setup")
        return HTTPException(status.status.HTTP_405_METHOD_NOT_ALLOWED)

    # do the shutdown
    system = RaspiBlitzSystem()
    return await system.shutdown(False)


# When WebUI displayed seed words & user confirmed write the calls:
@router.post("/setup-sync-info", dependencies=[Depends(JWTBearer())])
async def setup_sync_info():
    # first check that node is really in setup state
    setupPhase = await redis_get("setupPhase")
    if setupPhase != "done":
        logging.warning("sync info not available yet")
        return HTTPException(status.HTTP_405_METHOD_NOT_ALLOWED)

    try:
        blitz_sync_initial_done = await redis_get("blitz_sync_initial_done")
        if blitz_sync_initial_done == "1":
            initialsync = "done"
        else:
            initialsync = "running"
        btc_default_ready = await redis_get("btc_default_ready")
        btc_default_sync_percentage = await redis_get("btc_default_sync_percentage")
        btc_default_peers = await redis_get("btc_default_peers")
        system_count_start_blockchain = await redis_get("system_count_start_blockchain")
    except Exception:
        initialsync = ""
        btc_default_ready = ""
        btc_default_sync_percentage = ""
        btc_default_peers = ""
        system_count_start_blockchain = "0"
    try:
        ln_default = await redis_get("lightning")
        ln_default_ready = await redis_get("ln_default_ready")
        ln_default_locked = await redis_get("ln_default_locked")
        system_count_start_lightning = await redis_get("system_count_start_lightning")
    except Exception:
        ln_default = ""
        ln_default_ready = ""
        ln_default_locked = ""
        system_count_start_lightning = "0"
    return {
        "initialsync": initialsync,
        "btc_default": "bitcoin",
        "btc_default_ready": btc_default_ready,
        "btc_default_sync_percentage": btc_default_sync_percentage,
        "btc_default_peers": btc_default_peers,
        "system_count_start_blockchain": system_count_start_blockchain,
        "ln_default": ln_default,
        "ln_default_ready": ln_default_ready,
        "ln_default_locked": ln_default_locked,
        "system_count_start_lightning": system_count_start_lightning,
    }
