import asyncio

from fastapi.exceptions import HTTPException
from starlette import status

from app.api.utils import call_script2, redis_get


async def blitz_cln_unlock(network: str, password: str) -> bool:
    # /home/admin/config.scripts/cl.hsmtool.sh unlock mainnet PASSWORD_C
    # cl.hsmtool.sh [unlock] <mainnet|testnet|signet> <password>

    key = f"ln_cl_{network}_locked"
    res = await redis_get(key)
    if res == "0":
        raise HTTPException(
            status.HTTP_412_PRECONDITION_FAILED, detail="wallet already unlocked"
        )

    res = await call_script2(
        f"/home/admin/config.scripts/cl.hsmtool.sh unlock {network} {password}"
    )

    if res.return_code == 0:
        logging.debug(
            f"CLN_GRPC_BLITZ: Unlock script successfully called via API. Waiting for Redis {key} to be set."
        )

        # success: exit 0
        INTERVAL = 1
        total_wait_time = 0
        while total_wait_time < 60:
            res = await redis_get(key)
            if res == "0":
                _unlocked = True
                return True

            await asyncio.sleep(INTERVAL)
            total_wait_time += INTERVAL

        logging.debug(
            f"CLN_GRPC_BLITZ: Unlock script called successfully but redis key {key} indicates that RaspiBlitz is still locked. Stopped watching after polling for 60s for an unlock signal."
        )

        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unknown error while trying to unlock.",
        )
    elif res.return_code == 1:
        logging.error("CLN_GRPC_BLITZ: Unknown error while trying to unlock.")
        logging.error(f"CLN_GRPC_BLITZ: {res.__str__()}")

        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unknown error while trying to unlock. See the API logs for more info.",
        )
    elif res.return_code == 2:
        # wrong password: exit 2
        logger.warning("Wrong password while trying to unlock.")
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="invalid passphrase")
    elif res.return_code == 3:
        # fail to unlock after 1 minute + show logs: exit 3
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail=res)

    raise HTTPException(
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"Unknown error while trying to unlock.\n{res}",
    )
