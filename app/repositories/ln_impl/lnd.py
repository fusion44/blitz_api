from os import error
from typing import List

import app.repositories.ln_impl.protos.router_pb2 as router
import app.repositories.ln_impl.protos.rpc_pb2 as ln
import grpc
from app.models.lightning import (
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
    req = ln.GetInfoRequest()
    response = await lncfg.lnd_stub.GetTransactions(req)
    return [OnChainTransaction.from_grpc(t) for t in response.transactions]


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
