import asyncio
from typing import List

from fastapi import HTTPException, status
from loguru import logger

from app.apps.service import get_app_status
from app.bitcoind.service import get_btc_info
from app.lightning.service import (
    get_fee_revenue,
    get_ln_info,
    get_ln_info_lite,
    get_wallet_balance,
)
from app.system.service import get_hardware_info, get_system_info


@logger.catch(exclude=(HTTPException,))
async def get_bitcoin_client_warmup_data() -> List:
    """Get the reduced data set needed when the lightning client is not yet ready."""
    res = await asyncio.gather(
        *[
            get_btc_info(),
            get_hardware_info(),
        ]
    )
    return [*res]


@logger.catch(exclude=(HTTPException,))
async def get_full_client_warmup_data() -> List:
    """Get the full data set needed when the lightning client is not yet ready."""

    res = await asyncio.gather(
        *[
            get_system_info(),
            get_btc_info(),
            get_ln_info(),
            get_ln_info_lite(),
            get_fee_revenue(),
            get_wallet_balance(),
            get_app_status(),
            get_hardware_info(),
        ],
        return_exceptions=True,
    )

    for i, r in enumerate(res):
        if isinstance(r, HTTPException):
            if r.status_code == status.HTTP_501_NOT_IMPLEMENTED:
                logger.trace(f"Not implemented Error in warmup data {i}: {r.detail}")
            # TODO: find a better way to handle this, client receives an error but disguised
            # as a valid response. For example:
            # event: installed_app_status
            # data: {"status_code": 501, "detail": "Not available in native python mode.", "headers": null}
            res[i] = r
        elif isinstance(r, Exception):
            logger.error(f"Error in warmup data {i}: {r}")
            res[i] = HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return [*res]


@logger.catch(exclude=(HTTPException,))
async def get_full_client_warmup_data_bitcoinonly() -> List:
    """Get the full data set needed without Lightning available"""

    res = await asyncio.gather(
        *[
            get_system_info(),
            get_btc_info(),
            get_app_status(),
            get_hardware_info(),
        ]
    )
    return [*res]
