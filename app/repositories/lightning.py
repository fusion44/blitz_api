import asyncio
from typing import List

from app.models.lightning import (
    Invoice,
    LightningInfoLite,
    LnInfo,
    OnChainTransaction,
    Payment,
    PaymentRequest,
    SendCoinsInput,
    SendCoinsResponse,
)
from app.utils import SSE, lightning_config, send_sse_message
from decouple import config

if lightning_config.ln_node == "lnd":
    from app.repositories.ln_impl.lnd import (
        add_invoice_impl,
        decode_pay_request_impl,
        get_implementation_name,
        get_ln_info_impl,
        get_wallet_balance_impl,
        list_invoices_impl,
        list_on_chain_tx_impl,
        listen_invoices,
        send_coins_impl,
        send_payment_impl,
    )
else:
    from app.repositories.ln_impl.clightning import (
        add_invoice_impl,
        decode_pay_request_impl,
        get_implementation_name,
        get_ln_info_impl,
        get_wallet_balance_impl,
        list_invoices_impl,
        list_on_chain_tx_impl,
        listen_invoices,
        send_coins_impl,
        send_payment_impl,
    )

GATHER_INFO_INTERVALL = config("gather_ln_info_interval", default=5, cast=float)

_CACHE = {"wallet_balance": None}


async def get_ln_info_lite() -> LightningInfoLite:
    ln_info = await get_ln_info_impl()
    name = get_implementation_name()
    return LightningInfoLite.from_grpc(name, ln_info)


async def get_wallet_balance():
    return await get_wallet_balance_impl()


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


async def add_invoice(
    value_msat: int, memo: str = "", expiry: int = 3600, is_keysend: bool = False
) -> Invoice:
    return await add_invoice_impl(memo, value_msat, expiry, is_keysend)


async def decode_pay_request(pay_req: str) -> PaymentRequest:
    return await decode_pay_request_impl(pay_req)


async def send_coins(input: SendCoinsInput) -> SendCoinsResponse:
    res = await send_coins_impl(input)
    _update_wallet_balance()
    return res


async def send_payment(
    pay_req: str, timeout_seconds: int, fee_limit_msat: int
) -> Payment:
    res = await send_payment_impl(pay_req, timeout_seconds, fee_limit_msat)
    _update_wallet_balance()
    return res


async def get_ln_info() -> LnInfo:
    return await get_ln_info_impl()


async def register_lightning_listener():
    loop = asyncio.get_event_loop()
    loop.create_task(_handle_info_listener())
    loop.create_task(_handle_invoice_listener())


async def _handle_info_listener():
    last_info = None
    while True:
        info = await get_ln_info_impl()

        if last_info != info:
            info_lite = LightningInfoLite.from_grpc(get_implementation_name(), info)
            await send_sse_message(SSE.LN_INFO_LITE, info_lite.dict())
            last_info = info

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
