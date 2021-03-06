import asyncio
import logging
from typing import AsyncGenerator, List, Optional

from decouple import config
from fastapi.exceptions import HTTPException
from starlette import status

import app.repositories.ln_impl.cln_grpc as cln_main
from app.models.lightning import (
    Channel,
    FeeRevenue,
    ForwardSuccessEvent,
    GenericTx,
    InitLnRepoUpdate,
    Invoice,
    LnInfo,
    LnInitState,
    NewAddressInput,
    OnChainTransaction,
    Payment,
    PaymentRequest,
    SendCoinsInput,
    SendCoinsResponse,
    WalletBalance,
)
from app.utils import call_script2, redis_get

# RaspiBlitz implements a lock function on top of CLN, so we need to implement this on Blitz only.


_unlocked = False

_NETWORK = config("network", default="mainnet")


def get_implementation_name() -> str:
    return "CLN_GRPC_BLITZ"


async def initialize_impl() -> AsyncGenerator[InitLnRepoUpdate, None]:
    logging.debug("CLN_GRPC_BLITZ: RaspiBlitz is locked, waiting for unlock...")

    global _unlocked

    while not _unlocked:
        key = f"ln_cl_{_NETWORK}_locked"
        res = await redis_get(key)
        if res == "0":
            logging.debug(
                f"CLN_GRPC_BLITZ: Redis key {key} indicates that RaspiBlitz has been unlocked"
            )

            _unlocked = True
            yield InitLnRepoUpdate(state=LnInitState.BOOTSTRAPPING_AFTER_UNLOCK)
            break
        elif res == "1":
            logging.debug(
                f"CLN_GRPC_BLITZ: Redis key {key} indicates that RaspiBlitz is still locked"
            )

            yield InitLnRepoUpdate(
                state=LnInitState.LOCKED,
                msg="Wallet locked, unlock it to enable full RPC access",
            )
        else:
            logging.error(
                f"CLN_GRPC_BLITZ: Redis key {key} returns an unexpected value: {res}"
            )
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Unknown lock status: {res}",
            )

        await asyncio.sleep(2)

    async for u in cln_main.initialize_impl():
        yield u
        if u.state == LnInitState.DONE:
            break

    logging.info("CLN_GRPC_BLITZ: Initialization complete.")


async def get_wallet_balance_impl() -> WalletBalance:
    try:
        return await cln_main.get_wallet_balance_impl()
    except:
        _check_if_locked()
        raise


async def list_all_tx_impl(
    successful_only: bool, index_offset: int, max_tx: int, reversed: bool
) -> List[GenericTx]:
    try:
        return await cln_main.list_all_tx_impl(
            successful_only, index_offset, max_tx, reversed
        )
    except:
        _check_if_locked()
        raise


async def list_invoices_impl(
    pending_only: bool, index_offset: int, num_max_invoices: int, reversed: bool
) -> List[Invoice]:
    try:
        return await cln_main.list_invoices_impl(
            pending_only, index_offset, num_max_invoices, reversed
        )
    except:
        _check_if_locked()
        raise


async def list_on_chain_tx_impl() -> List[OnChainTransaction]:
    try:
        return await cln_main.list_on_chain_tx_impl()
    except:
        _check_if_locked()
        raise


async def list_payments_impl(
    include_incomplete: bool, index_offset: int, max_payments: int, reversed: bool
):
    try:
        return await cln_main.list_payments_impl(
            include_incomplete, index_offset, max_payments, reversed
        )
    except:
        _check_if_locked()
        raise


async def add_invoice_impl(
    value_msat: int, memo: str = "", expiry: int = 3600, is_keysend: bool = False
) -> Invoice:
    try:
        return await cln_main.add_invoice_impl(value_msat, memo, expiry, is_keysend)
    except:
        _check_if_locked()
        raise


async def decode_pay_request_impl(pay_req: str) -> PaymentRequest:
    try:
        return await cln_main.decode_pay_request_impl(pay_req)
    except:
        _check_if_locked()
        raise


async def get_fee_revenue_impl() -> FeeRevenue:
    try:
        return await cln_main.get_fee_revenue_impl()
    except:
        _check_if_locked()
        raise


async def new_address_impl(input: NewAddressInput) -> str:
    try:
        return await cln_main.new_address_impl(input)
    except:
        _check_if_locked()
        raise


async def send_coins_impl(input: SendCoinsInput) -> SendCoinsResponse:
    try:
        return await cln_main.send_coins_impl(input)
    except:
        _check_if_locked()
        raise


async def send_payment_impl(
    pay_req: str,
    timeout_seconds: int,
    fee_limit_msat: int,
    amount_msat: Optional[int] = None,
) -> Payment:
    try:
        return await cln_main.send_payment_impl(
            pay_req, timeout_seconds, fee_limit_msat, amount_msat
        )
    except:
        _check_if_locked()
        raise


async def get_ln_info_impl() -> LnInfo:
    try:
        # This will return "CLN_GRPC" and not "CLN_GRPC_BLITZ" to
        # not to complicate things further.
        # res.implementation = get_implementation_name()
        return await cln_main.get_ln_info_impl()
    except:
        _check_if_locked()
        raise


async def unlock_wallet_impl(password: str) -> bool:
    # RaspiBlitz implements a wallet lock functionality on top of CLN,
    # so we need to implement this on Blitz only

    # /home/admin/config.scripts/cl.hsmtool.sh unlock mainnet PASSWORD_C
    # cl.hsmtool.sh [unlock] <mainnet|testnet|signet> <password>

    global _unlocked
    key = f"ln_cl_{_NETWORK}_locked"
    res = await redis_get(key)
    if res == "0":
        raise HTTPException(
            status.HTTP_412_PRECONDITION_FAILED, detail="wallet already unlocked"
        )

    res = await call_script2(
        f"/home/admin/config.scripts/cl.hsmtool.sh unlock {_NETWORK} {password}"
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
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="invalid passphrase")
    elif res.return_code == 3:
        # fail to unlock after 1 minute + show logs: exit 3
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail=res)

    raise HTTPException(
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"Unknown error while trying to unlock.\n{res}",
    )


async def listen_invoices() -> AsyncGenerator[Invoice, None]:
    try:
        async for i in cln_main.listen_invoices():
            yield i
    except:
        _check_if_locked()
        raise


async def listen_forward_events() -> ForwardSuccessEvent:
    try:
        async for e in cln_main.listen_forward_events():
            yield e
    except:
        _check_if_locked()
        raise


async def connect_peer_impl(node_URI: str) -> bool:
    try:
        return await cln_main.connect_peer_impl(node_URI)
    except:
        _check_if_locked()
        raise


async def channel_open_impl(
    local_funding_amount: int, node_URI: str, target_confs: int
) -> str:
    try:
        return await cln_main.channel_open_impl(
            local_funding_amount, node_URI, target_confs
        )
    except:
        _check_if_locked()
        raise


async def channel_list_impl() -> List[Channel]:
    try:
        return await cln_main.channel_list_impl()
    except:
        _check_if_locked()
        raise


async def channel_close_impl(channel_id: int, force_close: bool) -> str:
    try:
        return await cln_main.channel_close_impl(channel_id, force_close)
    except:
        _check_if_locked()
        raise


def _check_if_locked():
    logging.debug(f"CLN_GRPC_BLITZ: _check_if_locked()")

    if not _unlocked:
        raise HTTPException(
            status.HTTP_423_LOCKED,
            detail="Wallet is locked. Unlock via /lightning/unlock-wallet",
        )
