import asyncio
from typing import List

from app.repositories.apps import get_app_status
from app.repositories.bitcoin import get_btc_info
from app.repositories.lightning import (
    get_fee_revenue,
    get_ln_info,
    get_ln_info_lite,
    get_wallet_balance,
)
from app.repositories.system import get_hardware_info, get_system_info


async def get_bitcoin_client_warmup_data() -> List:
    """Get the reduced data set needed when the lightning client is not yet ready."""
    res = await asyncio.gather(
        *[
            get_btc_info(),
            get_hardware_info(),
        ]
    )
    return [*res]


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
            # get_app_status(),
            get_hardware_info(),
        ]
    )
    return [*res]


async def get_full_client_warmup_data_bitcoinonly() -> List:
    """Get the full data set needed without Lightning available"""

    res = await asyncio.gather(
        *[
            get_system_info(),
            get_btc_info(),
            # get_app_status(),
            get_hardware_info(),
        ]
    )
    return [*res]
