import asyncio
from os import error

import app.repositories.ln_impl.protos.router_pb2 as router
import app.repositories.ln_impl.protos.rpc_pb2 as ln
import grpc
from app.models.lightning import (Invoice, InvoiceState, LnInfo, Payment,
                                  WalletBalance, invoice_from_grpc,
                                  ln_info_from_grpc, payment_from_grpc,
                                  wallet_balance_from_grpc)
from app.utils import SSE
from app.utils import lightning_config as lncfg
from app.utils import send_sse_message
from decouple import config
from fastapi.exceptions import HTTPException
from starlette import status

GATHER_INFO_INTERVALL = config(
    "gather_ln_info_interval", default=5, cast=float)

_CACHE = {"wallet_balance": None}


async def get_wallet_balance_impl() -> WalletBalance:
    req = ln.WalletBalanceRequest()
    req = ln.ChannelBalanceRequest()
    onchain = await lncfg.lnd_stub.WalletBalance(req)
    channel = await lncfg.lnd_stub.ChannelBalance(req)

    return wallet_balance_from_grpc(onchain, channel)


async def add_invoice_impl(value_msat: int, memo: str = "", expiry: int = 3600, is_keysend: bool = False) -> Invoice:
    i = ln.Invoice(
        memo=memo,
        value_msat=value_msat,
        expiry=expiry,
        is_keysend=is_keysend,
    )

    response = await lncfg.lnd_stub.AddInvoice(i)

    # Can't use invoice_from_grpc() here because
    # the response is not a standard invoice
    invoice = Invoice(
        memo=memo,
        expiry=expiry,
        r_hash=response.r_hash.hex(),
        payment_request=response.payment_request,
        add_index=response.add_index,
        payment_addr=response.payment_addr.hex(),
        state=InvoiceState.open,
        is_keysend=is_keysend,
    )

    return invoice


async def send_payment_impl(pay_req: str, timeout_seconds: int, fee_limit_msat: int) -> Payment:
    try:
        r = router.SendPaymentRequest(
            payment_request=pay_req,
            timeout_seconds=timeout_seconds,
            fee_limit_msat=fee_limit_msat
        )

        p = None
        async for response in lncfg.router_stub.SendPaymentV2(r):
            p = payment_from_grpc(response)
            await send_sse_message(SSE.LN_PAYMENT_STATUS, p.dict())
        _update_wallet_balance()
        return p
    except grpc.aio._call.AioRpcError as error:
        if error.details() != None and error.details().find("invalid bech32 string") > -1:
            raise HTTPException(status.HTTP_400_BAD_REQUEST,
                                detail="Invalid payment request string")
        else:
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR,
                                detail=error.details())


async def get_ln_info_impl() -> LnInfo:
    req = ln.GetInfoRequest()
    response = await lncfg.lnd_stub.GetInfo(req)
    return ln_info_from_grpc(response)


async def register_lightning_listener_impl():
    loop = asyncio.get_event_loop()
    loop.create_task(_handle_invoice_listener())
    loop.create_task(_handle_get_info_gatherer_impl())


async def _handle_invoice_listener():
    request = ln.InvoiceSubscription()

    try:
        async for r in lncfg.lnd_stub.SubscribeInvoices(request):
            i = invoice_from_grpc(r)
            await send_sse_message(SSE.LN_INVOICE_STATUS, i.dict())
            if i.state == InvoiceState.settled:
                # Wallet balance was updated, send to connected clients
                _update_wallet_balance()
    except error:
        print(error)


async def _handle_get_info_gatherer_impl():
    last_info = None
    while True:
        info = await get_ln_info_impl()

        if last_info != info:
            await send_sse_message(SSE.LN_INFO, info.dict())
            last_info = info

        # LND doesn't provide a subscription for payment events
        # This means, if the user pays a via command line or another app
        # connected directly to LND, no event is fired to other clients.
        # As a workaround we'll poll the wallet balance regularly and send
        # it, if it's different. Related: https://github.com/lightningnetwork/lnd/pull/1962
        _update_wallet_balance()

        await asyncio.sleep(GATHER_INFO_INTERVALL)


def _update_wallet_balance():
    async def _perform_update():
        await asyncio.sleep(1.1)
        wb = await get_wallet_balance_impl()
        if _CACHE["wallet_balance"] != wb:
            await send_sse_message(SSE.WALLET_BALANCE, wb.dict())
            _CACHE["wallet_balance"] = wb

    loop = asyncio.get_event_loop()
    loop.create_task(_perform_update())
