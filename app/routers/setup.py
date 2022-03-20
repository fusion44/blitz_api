import asyncio
import logging

from aioredis import Redis
from fastapi import APIRouter, HTTPException, status
from fastapi.params import Depends
from fastapi_plugins import depends_redis

from app.auth.auth_bearer import JWTBearer
from app.auth.auth_handler import signJWT
from app.utils import redis_get

router = APIRouter(prefix="/setup", tags=["Setup"])

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


@router.get("/setup_start_info")
async def setup_start_info():

    # first check that node is really in setup state
    setupPhase = await redis_get("setupPhase")
    state = await redis_get("state")
    if setupPhase != "done":
        logging.warning(
            f"/setup_start_info can only be called when nodes awaits setup (setupPhase)"
        )
        return HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE)
    if state != "waitsetup":
        logging.warning(
            f"/setup_start_info can only be called when nodes awaits setup (state)"
        )
        return HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE)

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


# With all this info the WebUi can run its own runs its dialogs and in the end makes a call to
@router.post("/setup_start_done")
async def setup_start_done(redis: Redis = Depends(depends_redis)):
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
    await redis.publish_json("default", {"data": "Starting setup"})
    await asyncio.sleep(1)
    return signJWT()


# WebUI now loops getting status until state=`waitfinal` then calls:
@router.get("/setup_final_info", dependencies=[Depends(JWTBearer())])
async def setup_final_info(redis: Redis = Depends(depends_redis)):
    # TODO: return info on setup final
    # during the process some data might be written to /var/cache/raspiblitz/temp/raspiblitz.setup
    # seedwordsNEW='${seedwords}
    # seedwords6x4NEW='${seedwords6x4}
    # syncProgressFull=[percent] = (later WebUi can offer sync from another RaspiBlitz)
    return HTTPException(status.HTTP_501_NOT_IMPLEMENTED)


# When WebUI displayed seed words & user confirmed write the calls:
@router.post("/setup_final_done", dependencies=[Depends(JWTBearer())])
async def setup_final_done(redis: Redis = Depends(depends_redis)):
    # TODO: like controlFinalDialog.sh Line 86 kicks off the AFTER FINAL TASKS and reboots
    return HTTPException(status.HTTP_501_NOT_IMPLEMENTED)
