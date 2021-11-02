import asyncio
import time
from os import error
from typing import List

import app.repositories.ln_impl.protos.router_pb2 as router
import app.repositories.ln_impl.protos.rpc_pb2 as ln
import grpc
from app.models.lightning import (
    GenericTx,
    Invoice,
    InvoiceState,
    LnInfo,
    OnChainTransaction,
    Payment,
    PaymentRequest,
    SendCoinsInput,
    SendCoinsResponse,
    WalletBalance,
)
from app.utils import SSE
from app.utils import lightning_config as lncfg
from app.utils import send_sse_message
from fastapi.exceptions import HTTPException
from starlette import status


def get_implementation_name() -> str:
    return "LND"


async def get_wallet_balance_impl() -> WalletBalance:
    req = ln.WalletBalanceRequest()
    req = ln.ChannelBalanceRequest()
    onchain = await lncfg.lnd_stub.WalletBalance(req)
    channel = await lncfg.lnd_stub.ChannelBalance(req)

    return WalletBalance.from_grpc(onchain, channel)


# Decoding the payment request take a long time,
# hence we build a simple cache here.
memo_cache = {}


async def list_all_tx_impl(
    successfull_only: bool, index_offset: int, max_tx: int, reversed: bool
) -> List[GenericTx]:
    # TODO: find a better caching strategy
    list_invoice_req = ln.ListInvoiceRequest(
        pending_only=successfull_only,
        index_offset=0,
        num_max_invoices=0,
        reversed=reversed,
    )

    get_tx_req = ln.GetTransactionsRequest()

    list_payments_req = ln.ListPaymentsRequest(
        include_incomplete=not successfull_only,
        index_offset=0,
        max_payments=0,
        reversed=reversed,
    )

    res = await asyncio.gather(
        *[
            lncfg.lnd_stub.ListInvoices(list_invoice_req),
            lncfg.lnd_stub.GetTransactions(get_tx_req),
            lncfg.lnd_stub.ListPayments(list_payments_req),
        ]
    )

    tx = []
    for i in res[0].invoices:
        tx.append(GenericTx.from_grpc_invoice(i))
    for t in res[1].transactions:
        tx.append(GenericTx.from_grpc_onchain_tx(t))
    for p in res[2].payments:
        comment = ""
        if p.payment_request in memo_cache:
            comment = memo_cache[p.payment_request]
        else:
            pr = await decode_pay_request_impl(p.payment_request)
            comment = pr.description
            memo_cache[p.payment_request] = pr.description
        tx.append(GenericTx.from_grpc_payment(p, comment))

    def sortKey(e: GenericTx):
        return e.time_stamp

    tx.sort(key=sortKey)

    if reversed:
        tx.reverse()

    l = len(tx)
    for i in range(l):
        tx[i].index = i

    if max_tx == 0:
        max_tx = l

    return tx[index_offset : index_offset + max_tx]


async def list_invoices_impl(
    pending_only: bool, index_offset: int, num_max_invoices: int, reversed: bool
):
    req = ln.ListInvoiceRequest(
        pending_only=pending_only,
        index_offset=index_offset,
        num_max_invoices=num_max_invoices,
        reversed=reversed,
    )
    response = await lncfg.lnd_stub.ListInvoices(req)
    return [Invoice.from_grpc(i) for i in response.invoices]


async def list_on_chain_tx_impl() -> List[OnChainTransaction]:
    req = ln.GetTransactionsRequest()
    response = await lncfg.lnd_stub.GetTransactions(req)
    return [OnChainTransaction.from_grpc(t) for t in response.transactions]


async def list_payments_impl(
    include_incomplete: bool, index_offset: int, max_payments: int, reversed: bool
):
    req = ln.ListPaymentsRequest(
        include_incomplete=include_incomplete,
        index_offset=index_offset,
        max_payments=max_payments,
        reversed=reversed,
    )
    response = await lncfg.lnd_stub.ListPayments(req)
    return [Payment.from_grpc(p) for p in response.payments]


async def add_invoice_impl(
    value_msat: int, memo: str = "", expiry: int = 3600, is_keysend: bool = False
) -> Invoice:
    i = ln.Invoice(
        memo=memo,
        value_msat=value_msat,
        expiry=expiry,
        is_keysend=is_keysend,
    )

    response = await lncfg.lnd_stub.AddInvoice(i)

    # Can't use Invoice.from_grpc() here because
    # the response is not a standard invoice
    invoice = Invoice(
        memo=memo,
        expiry=expiry,
        r_hash=response.r_hash.hex(),
        payment_request=response.payment_request,
        add_index=response.add_index,
        payment_addr=response.payment_addr.hex(),
        state=InvoiceState.OPEN,
        is_keysend=is_keysend,
    )

    return invoice


async def decode_pay_request_impl(pay_req: str) -> PaymentRequest:
    try:
        req = ln.PayReqString(pay_req=pay_req)
        res = await lncfg.lnd_stub.DecodePayReq(req)
        return PaymentRequest.from_grpc(res)
    except grpc.aio._call.AioRpcError as error:
        if error.details() != None and error.details().find("checksum failed.") > -1:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, detail="Invalid payment request string"
            )
        else:
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR, detail=error.details()
            )


async def send_coins_impl(input: SendCoinsInput) -> SendCoinsResponse:
    try:
        r = ln.SendCoinsRequest(
            addr=input.address,
            amount=input.amount,
            target_conf=input.target_conf,
            sat_per_vbyte=input.sat_per_vbyte,
            min_confs=input.min_confs,
            label=input.label,
        )

        response = await lncfg.lnd_stub.SendCoins(r)
        r = SendCoinsResponse.from_grpc(response, input)
        await send_sse_message(SSE.LN_ONCHAIN_PAYMENT_STATUS, r.dict())
        return r
    except grpc.aio._call.AioRpcError as error:
        details = error.details()
        if details and details.find("invalid bech32 string") > -1:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, detail="Invalid payment request string"
            )
        elif details and details.find("insufficient funds available") > -1:
            raise HTTPException(
                status.HTTP_412_PRECONDITION_FAILED, detail=error.details()
            )
        else:
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR, detail=error.details()
            )


async def send_payment_impl(
    pay_req: str, timeout_seconds: int, fee_limit_msat: int
) -> Payment:
    try:
        r = router.SendPaymentRequest(
            payment_request=pay_req,
            timeout_seconds=timeout_seconds,
            fee_limit_msat=fee_limit_msat,
        )

        p = None
        async for response in lncfg.router_stub.SendPaymentV2(r):
            p = Payment.from_grpc(response)
            await send_sse_message(SSE.LN_PAYMENT_STATUS, p.dict())
        return p
    except grpc.aio._call.AioRpcError as error:
        if (
            error.details() != None
            and error.details().find("invalid bech32 string") > -1
        ):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, detail="Invalid payment request string"
            )
        else:
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR, detail=error.details()
            )


async def get_ln_info_impl() -> LnInfo:
    req = ln.GetInfoRequest()
    response = await lncfg.lnd_stub.GetInfo(req)
    return LnInfo.from_grpc(response)


async def listen_invoices() -> Invoice:
    request = ln.InvoiceSubscription()
    try:
        async for r in lncfg.lnd_stub.SubscribeInvoices(request):
            yield Invoice.from_grpc(r)
    except error:
        print(error)
