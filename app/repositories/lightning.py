import asyncio
import logging
from typing import List, Optional

from decouple import config
from fastapi import status
from fastapi.exceptions import HTTPException

from app.models.lightning import (
    Channel,
    FeeRevenue,
    GenericTx,
    Invoice,
    LightningInfoLite,
    LnInfo,
    NewAddressInput,
    OnChainTransaction,
    Payment,
    PaymentRequest,
    SendCoinsInput,
    SendCoinsResponse,
)
from app.models.system import APIPlatform
from app.utils import SSE, lightning_config, redis_get, send_sse_message

if lightning_config.ln_node == "lnd":
    from app.repositories.ln_impl.lnd import (
        add_invoice_impl,
        channel_close_impl,
        channel_list_impl,
        channel_open_impl,
        decode_pay_request_impl,
        get_fee_revenue_impl,
        get_ln_info_impl,
        get_wallet_balance_impl,
        list_all_tx_impl,
        list_invoices_impl,
        list_on_chain_tx_impl,
        list_payments_impl,
        listen_forward_events,
        listen_invoices,
        new_address_impl,
        send_coins_impl,
        send_payment_impl,
        unlock_wallet_impl,
    )
else:
    from app.repositories.ln_impl.clightning import (
        add_invoice_impl,
        channel_close_impl,
        channel_list_impl,
        channel_open_impl,
        decode_pay_request_impl,
        get_fee_revenue_impl,
        get_ln_info_impl,
        get_wallet_balance_impl,
        list_all_tx_impl,
        list_invoices_impl,
        list_on_chain_tx_impl,
        list_payments_impl,
        listen_forward_events,
        listen_invoices,
        new_address_impl,
        send_coins_impl,
        send_payment_impl,
        unlock_wallet_impl,
    )

GATHER_INFO_INTERVALL = config("gather_ln_info_interval", default=2, cast=float)

_CACHE = {"wallet_balance": None}
_WALLET_UNLOCK_LISTENERS = []

ENABLE_FWD_NOTIFICATIONS = config(
    "sse_notify_forward_successes", default=False, cast=bool
)

FWD_GATHER_INTERVAL = config("forwards_gather_interval", default=2.0, cast=float)

PLATFORM = config("platform", cast=str)

if FWD_GATHER_INTERVAL < 0.3:
    raise RuntimeError("forwards_gather_interval cannot be less than 0.3 seconds")


async def get_ln_info_lite() -> LightningInfoLite:
    ln_info = await get_ln_info_impl()
    return LightningInfoLite.from_grpc(ln_info)


async def get_wallet_balance():
    return await get_wallet_balance_impl()


async def list_all_tx(
    successfull_only: bool, index_offset: int, max_tx: int, reversed: bool
) -> List[GenericTx]:
    return await list_all_tx_impl(successfull_only, index_offset, max_tx, reversed)


async def list_invoices(
    pending_only: bool, index_offset: int, num_max_invoices: int, reversed: bool
) -> List[Invoice]:
    return await list_invoices_impl(
        pending_only,
        index_offset,
        num_max_invoices,
        reversed,
    )


async def list_on_chain_tx() -> List[OnChainTransaction]:
    return await list_on_chain_tx_impl()


async def list_payments(
    include_incomplete: bool, index_offset: int, max_payments: int, reversed: bool
) -> List[Payment]:
    return await list_payments_impl(
        include_incomplete, index_offset, max_payments, reversed
    )


async def add_invoice(
    value_msat: int, memo: str = "", expiry: int = 3600, is_keysend: bool = False
) -> Invoice:
    return await add_invoice_impl(memo, value_msat, expiry, is_keysend)


async def decode_pay_request(pay_req: str) -> PaymentRequest:
    return await decode_pay_request_impl(pay_req)


async def new_address(input: NewAddressInput) -> str:
    return await new_address_impl(input)


async def send_coins(input: SendCoinsInput) -> SendCoinsResponse:
    res = await send_coins_impl(input)
    _schedule_wallet_balance_update()
    return res


async def send_payment(
    pay_req: str,
    timeout_seconds: int,
    fee_limit_msat: int,
    amount_msat: Optional[int] = None,
) -> Payment:
    res = await send_payment_impl(pay_req, timeout_seconds, fee_limit_msat, amount_msat)
    _schedule_wallet_balance_update()
    return res


async def channel_open(
    local_funding_amount: int, node_URI: str, target_confs: int
) -> str:

    if local_funding_amount < 1:
        raise ValueError("funding amount needs to be positive")

    if target_confs < 1:
        raise ValueError("target confs needs to be positive")

    if len(node_URI) == 0:
        raise ValueError("node_URI cant be empty")

    if not "@" in node_URI:
        raise ValueError("node_URI must contain @ with node physical address")

    res = await channel_open_impl(local_funding_amount, node_URI, target_confs)
    return res


async def channel_list() -> List[Channel]:
    res = await channel_list_impl()
    return res


async def channel_close(channel_id: int, force_close: bool) -> str:
    res = await channel_close_impl(channel_id, force_close)
    return res


async def get_ln_info() -> LnInfo:
    ln_info = await get_ln_info_impl()
    if PLATFORM == APIPlatform.RASPIBLITZ:
        ln_info.identity_uri = await redis_get("ln_default_address")
    return ln_info


async def unlock_wallet(password: str) -> bool:
    res = await unlock_wallet_impl(password)
    if res:
        for l in _WALLET_UNLOCK_LISTENERS:
            await l.put("unlocked")
    return res


async def get_fee_revenue() -> FeeRevenue:
    return await get_fee_revenue_impl()


async def register_lightning_listener():
    """
    Registers all lightning listeners

    By calling get_ln_info_impl() once, we ensure that wallet is unlocked.
    Implementation will throw HTTPException with status_code 423_LOCKED if otherwise.
    It is the task of the caller to call register_lightning_listener() again
    """

    try:
        await get_ln_info_impl()

        loop = asyncio.get_event_loop()
        loop.create_task(_handle_info_listener())
        loop.create_task(_handle_invoice_listener())
        loop.create_task(_handle_forward_event_listener())
    except HTTPException as r:
        if r.detail == "failed to connect to all addresses":
            logging.error(
                """
Unable to connect to LND. Possible reasons:
* Node is not reachable (ports, network down, ...)
* Maccaroon is not correct
* IP is not included in LND tls certificate
    Add tlsextraip=192.168.1.xxx to lnd.conf and restart LND.
    This will recreate the TLS certificate. The .env must be adpted accordingly.
* TLS certificate is wrong. (settings changed, ...)

To Debug gRPC problems uncomment the following line in app.utils.LightningConfig._init():
# os.environ["GRPC_VERBOSITY"] = "DEBUG"
This will show more debug information.
"""
            )
            exit(1)
        else:
            raise
    except NotImplementedError as r:
        raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, detail=r.args[0])


async def _handle_info_listener():
    last_info = None
    last_info_lite = None
    while True:
        info = await get_ln_info_impl()

        if last_info != info:
            await send_sse_message(SSE.LN_INFO, info.dict())
            last_info = info

        info_lite = LightningInfoLite.from_grpc(info)

        if last_info_lite != info_lite:
            await send_sse_message(SSE.LN_INFO_LITE, info_lite.dict())
            last_info_lite = info_lite

        await asyncio.sleep(GATHER_INFO_INTERVALL)


async def _handle_invoice_listener():
    async for i in listen_invoices():
        await send_sse_message(SSE.LN_INVOICE_STATUS, i.dict())
        _schedule_wallet_balance_update()


_fwd_update_scheduled = False
_fwd_successes = []


async def _handle_forward_event_listener():
    async def _schedule_fwd_update():
        global _fwd_update_scheduled
        global _fwd_successes

        _fwd_update_scheduled = True

        await asyncio.sleep(FWD_GATHER_INTERVAL)

        if len(_fwd_successes) > 0:
            l = _fwd_successes
            _fwd_successes = []
            await send_sse_message(SSE.LN_FORWARD_SUCCESSES, l)

        _schedule_wallet_balance_update()
        rev = await get_fee_revenue()
        await send_sse_message(SSE.LN_FEE_REVENUE, rev.dict())

        _fwd_update_scheduled = False

    async for i in listen_forward_events():
        if ENABLE_FWD_NOTIFICATIONS:
            _fwd_successes.append(i.dict())

        if not _fwd_update_scheduled:
            loop = asyncio.get_event_loop()
            loop.create_task(_schedule_fwd_update())


_wallet_balance_update_scheduled = False


def _schedule_wallet_balance_update():
    async def _perform_update():
        global _wallet_balance_update_scheduled
        _wallet_balance_update_scheduled = True
        await asyncio.sleep(1.1)
        wb = await get_wallet_balance_impl()
        if _CACHE["wallet_balance"] != wb:
            await send_sse_message(SSE.WALLET_BALANCE, wb.dict())
            _CACHE["wallet_balance"] = wb

        _wallet_balance_update_scheduled = False

    global _wallet_balance_update_scheduled
    if not _wallet_balance_update_scheduled:
        loop = asyncio.get_event_loop()
        loop.create_task(_perform_update())


def register_wallet_unlock_listener(q: asyncio.Queue):
    if q not in _WALLET_UNLOCK_LISTENERS:
        _WALLET_UNLOCK_LISTENERS.append(q)


def unregister_wallet_unlock_listener(func):
    if func in _WALLET_UNLOCK_LISTENERS:
        _WALLET_UNLOCK_LISTENERS.remove(func)


rpc_startup_error_msg = (
    "RPC server is in the process of starting up, but not yet ready to accept calls"
)


def listen_for_ssh_unlock():
    async def _do_check_unlock():
        while True:
            try:
                _ = await get_ln_info_impl()
                for l in _WALLET_UNLOCK_LISTENERS:
                    await l.put("unlocked")
                break
            except HTTPException as r:
                if r.status_code == 423 or (
                    r.status_code == 500 and rpc_startup_error_msg in r.detail
                ):
                    await asyncio.sleep(3)
                else:
                    print(
                        f"Got {r.status_code} with message {r.detail} while watching for SSH wallet unlock. Stopping ..."
                    )
                    raise
            except NotImplementedError as r:
                raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, detail=r.args[0])

    loop = asyncio.get_event_loop()
    loop.create_task(_do_check_unlock())
