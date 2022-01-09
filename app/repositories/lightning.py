import asyncio
from typing import List, Optional

from app.models.lightning import (
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
from app.utils import SSE, lightning_config, send_sse_message
from decouple import config
from fastapi import status
from fastapi.exceptions import HTTPException

if lightning_config.ln_node == "lnd":
    from app.repositories.ln_impl.lnd import (
        add_invoice_impl,
        decode_pay_request_impl,
        get_ln_info_impl,
        get_wallet_balance_impl,
        list_all_tx_impl,
        list_invoices_impl,
        list_on_chain_tx_impl,
        list_payments_impl,
        listen_invoices,
        new_address_impl,
        send_coins_impl,
        send_payment_impl,
        unlock_wallet_impl,
    )
else:
    from app.repositories.ln_impl.clightning import (
        add_invoice_impl,
        decode_pay_request_impl,
        get_ln_info_impl,
        get_wallet_balance_impl,
        list_all_tx_impl,
        list_invoices_impl,
        list_on_chain_tx_impl,
        list_payments_impl,
        listen_invoices,
        new_address_impl,
        send_coins_impl,
        send_payment_impl,
        unlock_wallet_impl,
    )

GATHER_INFO_INTERVALL = config("gather_ln_info_interval", default=5, cast=float)

_CACHE = {"wallet_balance": None}
_WALLET_UNLOCK_LISTENERS = []


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
    _update_wallet_balance()
    return res


async def send_payment(
    pay_req: str,
    timeout_seconds: int,
    fee_limit_msat: int,
    amount_msat: Optional[int] = None,
) -> Payment:
    res = await send_payment_impl(pay_req, timeout_seconds, fee_limit_msat, amount_msat)
    _update_wallet_balance()
    return res


async def get_ln_info() -> LnInfo:
    return await get_ln_info_impl()


async def unlock_wallet(password: str) -> bool:
    res = await unlock_wallet_impl(password)
    if res:
        for l in _WALLET_UNLOCK_LISTENERS:
            await l.put("unlocked")
    return res


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
    except HTTPException as r:
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
        _update_wallet_balance()


def _update_wallet_balance():
    async def _perform_update():
        await asyncio.sleep(1.1)
        wb = await get_wallet_balance_impl()
        if _CACHE["wallet_balance"] != wb:
            await send_sse_message(SSE.WALLET_BALANCE, wb.dict())
            _CACHE["wallet_balance"] = wb

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
