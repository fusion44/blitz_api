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
from app.repositories.system import get_system_info


async def get_client_warmup_data() -> List:
    res = await asyncio.gather(
        *[
            get_system_info(),
            get_btc_info(),
            get_ln_info(),
            get_ln_info_lite(),
            get_fee_revenue(),
            get_wallet_balance(),
        ]
    )
    return [*res, get_app_status()]


available_app_ids = {
    "bos",
    "btc-rpc-explorer",
    "btcpayserver",
    "chantools",
    "circuitbreaker",
    "electrs",
    "faraday",
    "fullynoded",
    "joinmarket",
    "kindle-display",
    "lit",
    "lnbits",
    "lndconnect",
    "lndmanage",
    "loop",
    "mempool",
    "pool",
    "pyblock",
    "rtl",
    "specter",
    "sphinxrelay",
    "stacking-sats-kraken",
    "suez",
    "telegraf",
    "thunderhub",
    "whitepaper",
    "zerotier"
};