import logging

from fastapi import APIRouter, HTTPException, status
from fastapi.params import Depends
from pydantic import BaseModel

from app.auth.auth_bearer import JWTBearer
from app.auth.auth_handler import sign_jwt
from app.core_utils import call_script, parse_key_value_lines, redis_get
from app.repositories.system_impl.raspiblitz import RaspiBlitzSystem
from app.repositories.utils.raspiblitz import name_valid, password_valid

router = APIRouter(prefix="/setup", tags=["RaspiBlitz Setup"])

setupFilePath = "/var/cache/raspiblitz/temp/raspiblitz.setup"
configFilePath = "/mnt/hdd/raspiblitz.conf"

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
        except:
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
# We can do the "MIGRATION" option later - because it would need an additional step after formatting hdd
# People that need to migrate can do for now by SSH option


@router.get("/setup-start-info")
async def setup_start_info():

    # first check that node is really in setup state
    setupPhase = await redis_get("setupPhase")
    state = await redis_get("state")
    if state != "waitsetup":
        logging.warning(f"/setup-start-info can only be called when nodes awaits setup")
        return HTTPException(status.status.HTTP_405_METHOD_NOT_ALLOWED)

    # get all the additional info needed to do setup dialog
    hddGotMigrationData = await redis_get("hddGotMigrationData")
    hddGotBlockchain = await redis_get("hddBlocksBitcoin")
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
    with open(filename, "w", encoding="utf-8") as f:
        f.write("\n".join(arrayOfLines))


class StartDoneData(BaseModel):
    hostname: str = ""
    forceFreshSetup: bool = False
    keepBlockchain: bool = True
    lightning: str = ""
    passwordA: str = ""
    passwordB: str = ""
    passwordC: str = ""


# With all this info the WebUi can run its own runs its dialogs and in the end makes a call to
@router.post("/setup-start-done")
async def setup_start_done(data: StartDoneData):

    # first check that node is really in setup state
    setupPhase = await redis_get("setupPhase")
    state = await redis_get("state")
    hddGotBlockchain = await redis_get("hddBlocksBitcoin")

    if state != "waitsetup":
        logging.warning(f"/setup-start-done can only be called when nodes awaits setup")
        return HTTPException(status.HTTP_405_METHOD_NOT_ALLOWED)

    # check if a fresh setup is forced
    if data.forceFreshSetup:
        logging.warning(f"forcing node to fresh setup")
        setupPhase = "setup"

    #### SETUP ####
    if setupPhase == "setup":
        if name_valid(data.hostname) == False:
            logging.warning(f"hostname is not valid")
            return HTTPException(status.HTTP_400_BAD_REQUEST)
        if (
            data.lightning != "lnd"
            and data.lightning != "cl"
            and data.lightning != "none"
        ):
            logging.warning(f"lightning is not valid")
        if password_valid(data.passwordA) == False:
            logging.warning(f"passwordA is not valid")
            return HTTPException(status.HTTP_400_BAD_REQUEST)
        if password_valid(data.passwordB) == False:
            logging.warning(f"passwordB is not valid")
            return HTTPException(status.HTTP_400_BAD_REQUEST)
        if data.lightning != "none" and password_valid(data.passwordC) == False:
            logging.warning(f"passwordC is not valid")
            return HTTPException(status.HTTP_400_BAD_REQUEST)
        if hddGotBlockchain != "1" and data.keepBlockchain:
            logging.warning(f"cannot keep blockchain that does not exists")
            return HTTPException(status.HTTP_400_BAD_REQUEST)
        if data.keepBlockchain:
            formatHDD = 0
            cleanHDD = 1
        else:
            formatHDD = 1
            cleanHDD = 0
        write_text_file(
            setupFilePath,
            [
                f"formatHDD={formatHDD}",
                f"cleanHDD={cleanHDD}",
                "network=bitcoin",
                "chain=main",
                f"lightning={data.lightning}",
                f"hostname={data.hostname}",
                "setPasswordA=1",
                "setPasswordB=1",
                "setPasswordC=1",
                f"passwordA='{data.passwordA}'",
                f"passwordB='{data.passwordB}'",
                f"passwordC='{data.passwordC}'",
                "",
            ],
        )

    #### RECOVERY ####
    elif setupPhase == "recovery" or setupPhase == "update":
        logging.warning(f"check recovery data")
        if password_valid(data.passwordA) == False:
            logging.warning(f"passwordA is not valid")
            return HTTPException(status.HTTP_400_BAD_REQUEST)
        write_text_file(
            setupFilePath, ["setPasswordA=1", f"passwordA='{data.passwordA}'"]
        )

    #### MIGRATION ####
    elif setupPhase == "migration":
        logging.warning(f"check migration data")
        hddGotMigrationData = await redis_get("hddGotMigrationData")
        if hddGotMigrationData == "":
            logging.warning(f"hddGotMigrationData is not available")
            return HTTPException(status.HTTP_400_BAD_REQUEST)
        if password_valid(data.passwordA) == False:
            logging.warning(f"passwordA is not valid")
            return HTTPException(status.HTTP_400_BAD_REQUEST)
        if password_valid(data.passwordB) == False:
            logging.warning(f"passwordB is not valid")
            return HTTPException(status.HTTP_400_BAD_REQUEST)
        if password_valid(data.passwordC) == False:
            logging.warning(f"passwordC is not valid")
            return HTTPException(status.HTTP_400_BAD_REQUEST)
        write_text_file(
            setupFilePath,
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
        return HTTPException(status.HTTP_405_METHOD_NOT_ALLOWED)

    await call_script("/home/admin/_cache.sh set state waitprovision")

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
    # those values get stored in: /var/cache/raspiblitz/temp/raspiblitz.setup
    # also a skeleton raspiblitz.conf gets created (see controlSetupDialog.sh Line 318)
    # and then API sets state to `waitprovision` to kick-off provision

    return sign_jwt()


# WebUI now loops getting status until state=`waitfinal` then calls:
@router.get("/setup-final-info", dependencies=[Depends(JWTBearer())])
async def setup_final_info():
    # TODO: return info on setup final
    # during the process some data might be written to /var/cache/raspiblitz/temp/raspiblitz.setup
    # seedwordsNEW='${seedwords}
    # seedwords6x4NEW='${seedwords6x4}
    # syncProgressFull=[percent] = (later WebUi can offer sync from another RaspiBlitz)

    # first check that node is really in setup state
    setupPhase = await redis_get("setupPhase")
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
    except:
        seedwordsNEW = ""

    return {"seedwordsNEW": seedwordsNEW}


# When WebUI displayed seed words & user confirmed write the calls:
@router.post("/setup-final-done", dependencies=[Depends(JWTBearer())])
async def setup_final_done():

    # first check that node is really in setup state
    setupPhase = await redis_get("setupPhase")
    state = await redis_get("state")
    if state != "waitfinal":
        logging.warning(f"/setup-final-done can only be called when nodes awaits final")
        return HTTPException(status.HTTP_405_METHOD_NOT_ALLOWED)

    await call_script("/home/admin/_cache.sh set state donefinal")
    return {"state": "donefinal"}


@router.get("/shutdown")
async def get_shutdown():

    # only allow unauthorized shutdowns during setup
    setupPhase = await redis_get("setupPhase")
    state = await redis_get("state")
    if setupPhase == "done":
        logging.warning(f"can only be called when the nodes is not finalized yet")
        return HTTPException(status.status.HTTP_405_METHOD_NOT_ALLOWED)
    if state != "waitsetup":
        logging.warning(f"can only be called when nodes awaits setup")
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
        logging.warning(f"sync info not available yet")
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
    except:
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
    except:
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
