import asyncio
from enum import Enum
from os import stat
from fastapi import APIRouter, HTTPException, status
from fastapi.params import Depends
from aioredis import Redis
from fastapi_plugins import depends_redis, redis_plugin
from app.auth.auth_bearer import JWTBearer
from app.auth.auth_handler import signJWT

router = APIRouter(prefix="/setup", tags=["Setup"])

def make_error(
    error_id: int, endpoint_url: str, err_description: str, description: str
):
    return {
        "error_id": error_id,
        "endpoint_url": endpoint_url,
        "error_description": err_description,
        "description": description,
    }


def set_status(status: int, endpoint_url: str, description: str):
    return {
        "status": status,
        "endpoint_url": endpoint_url,
        "description": description,
    }

# status normally is a tripple "setupPhase", "state" & "message" if we want to keep it similar with SSH process 
# can always be called without credentials
@router.get("/status")
def get_status():
    return set_status(2, "/setup/start_setup", "HDD needs setup (2)")

# for example in the beginning setupPhase can be (see controlSetupDialog.sh)
# 1) recovery = same version on fresh sd card
# 2) update = updated version on fresh sd card
# 3) migration = hdd got data from another node projcect
#   additional data fields:
#   hddGotMigrationData = 'umbrel', 'mynode', 'citadel'
#   migrationMode= 'normal' or 'outdatedLightning' (later means RaspiBlitz has an older lightning version - dont convert)
# 4) setup = a fresh blitz to setup
#   additional data fields:
#   existingBlockchain = 'BITCOIN' or empty (if not empty ask user to keep or delete blockchain data)

# We can do the "MIGRATION" option later - because it would need an additional step after formatting hdd
# People that need to migrate can do for now by SSH option

@router.get("/setup_start_info")
async def setup_start_info(redis: Redis = Depends(depends_redis)):
    # TODO: get additional infos needed to display 
    return set_status(2, "/setup/start_setup", "HDD needs setup (2)")

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
@router.get("/setup_final_info",dependencies=[Depends(JWTBearer())])
async def setup_final_info(redis: Redis = Depends(depends_redis)):
    # TODO: return info on setup final
    # during the process some data might be written to /var/cache/raspiblitz/temp/raspiblitz.setup
    # seedwordsNEW='${seedwords}
    # seedwords6x4NEW='${seedwords6x4}
    # syncProgressFull=[percent] = (later WebUi can offer sync from another RaspiBlitz)
    return HTTPException(status.HTTP_501_NOT_IMPLEMENTED)

# When WebUI displayed seed words & user confirmed write the calls: 
@router.post("/setup_final_done",dependencies=[Depends(JWTBearer())])
async def setup_final_done(redis: Redis = Depends(depends_redis)):
    # TODO: like controlFinalDialog.sh Line 86 kicks off the AFTER FINAL TASKS and reboots
    return HTTPException(status.HTTP_501_NOT_IMPLEMENTED)
