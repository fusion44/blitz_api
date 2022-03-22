import asyncio
#from asyncio.windows_events import NULL
import logging
import re

from aioredis import Redis
from fastapi import APIRouter, HTTPException, status
from fastapi.params import Depends
from fastapi_plugins import depends_redis
from setuptools import setup

from app.repositories.system import (
    callScript,
    parseKeyValueLines,
    passwordValid
)

from app.auth.auth_bearer import JWTBearer
from app.auth.auth_handler import signJWT
from app.utils import redis_get

router = APIRouter(prefix="/setup", tags=["Setup"])

setupFilePath="/var/cache/raspiblitz/temp/raspiblitz.setup"
configFilePath="/mnt/hdd/raspiblitz.conf"

# can always be called without credentials to check if
# the system needs or is in setup (setupPhase!="done")
# for example in the beginning setupPhase can be (see controlSetupDialog.sh)
# 1) recovery = same version on fresh sd card
# 2) update = updated version on fresh sd card
# 3) migration = hdd got data from another node projcect
# 4) setup = a fresh blitz to setup
@router.get("/status")
async def get_status():
    setupPhase = await redis_get("setupPhase")
    state = await redis_get("state")
    message = await redis_get("message")
    return {"setupPhase": setupPhase, "state": state, "message": message}


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
        logging.warning(
            f"/setup-start-info can only be called when nodes awaits setup"
        )
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


def writeTextFile(filename: str, arrayOfLines):
    logging.warning(f"writing {filename}")
    with open(filename, 'w', encoding='utf-8') as f:
        f.write('\n'.join(arrayOfLines))

# With all this info the WebUi can run its own runs its dialogs and in the end makes a call to
@router.post("/setup-start-done")
async def setup_start_done(
    passwordA : str = ""
):
    logging.warning(f"START /setup-start-done") 

    # first check that node is really in setup state
    setupPhase = await redis_get("setupPhase")
    state = await redis_get("state")
    if state != "waitsetup":
        logging.warning(f"/setup-start-done can only be called when nodes awaits setup")
        return HTTPException(status.HTTP_405_METHOD_NOT_ALLOWED)

    if setupPhase == "recovery": 
        logging.warning(f"check recovery data")
        if passwordValid(passwordA) == False:
            logging.warning(f"passwordA is not valid")
            return HTTPException(status.HTTP_400_BAD_REQUEST)
        writeTextFile(setupFilePath,[
            f"setupType={setupPhase}",
            "setPasswordA=1",
            f"passwordA='{passwordA}'"
        ])
        logging.warning(f"kicking off recovery")
        await callScript("/home/admin/_cache.sh set state waitprovision")
    else:
        logging.warning(f"not handled setupPhase state ({setupPhase})")
        return HTTPException(status.HTTP_405_METHOD_NOT_ALLOWED)

    # TODO: Following input parameters:
    # lightning='lnd', 'cl' or 'none'
    # network=bitcoin
    # chain=main
    # hostname=[string]
    # passwordA=[string]
    # passwordB=[string]
    # passwordC=[string] (might be empty of no lightning was choosen)
    # lndrescue=[path] (might be used later if lnd rescue file upload is offered)
    # clrescue=[path] (might be used later if c-lightning rescue file upload is offered)
    # seedWords= (might be used later if we offer recover from seed words)
    # seedPassword= (might be used later if we offer recover from seed words)
    # migrationFile=[path] (might be used later if we offer raspiblitz migration)
    # those values get stored in: /var/cache/raspiblitz/temp/raspiblitz.setup
    # also a skeleton raspiblitz.conf gets created (see controlSetupDialog.sh Line 318)
    # and then API sets state to `waitprovision` to kick-off provision
    
    # await redis.publish_json("default", {"data": "Starting setup"})
    # await asyncio.sleep(1)
    return signJWT()


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
        logging.warning(f"/setup-final-info can only be called when nodes awaits final ({state})")
        return HTTPException(status.HTTP_405_METHOD_NOT_ALLOWED)

    resultlines=[]
    with open (setupFilePath, "r") as setupfile:
        resultlines=setupfile.readlines()
    data=parseKeyValueLines(resultlines)
    logging.warning(f"data({data})")
    try:
        setupType = data["setupType"]
    except:
        logging.warning("missing setupType in raspiblitz.setup")
        setupType=""
    if setupType == "setup":
        return {
            "setupType": setupType,
            "seedwordsNEW": data["seedwordsNEW"]
        }
    else:
        return {
            "setupType": setupType,
            "seedwordsNEW": ""
        }

# When WebUI displayed seed words & user confirmed write the calls:
@router.post("/setup-final-done", dependencies=[Depends(JWTBearer())])
async def setup_final_done():

    # first check that node is really in setup state
    setupPhase = await redis_get("setupPhase")
    state = await redis_get("state")
    if state != "waitfinal":
        logging.warning(f"/setup-final-done can only be called when nodes awaits final")
        return HTTPException(status.HTTP_405_METHOD_NOT_ALLOWED)

    await callScript("/home/admin/_cache.sh set state donefinal")
    return {
        "state": "donefinal"
    }
