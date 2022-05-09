import asyncio
from typing import List, Optional

import grpc
from fastapi.exceptions import HTTPException
from starlette import status

import app.repositories.ln_impl.protos.lightning_pb2 as ln
import app.repositories.ln_impl.protos.router_pb2 as router
import app.repositories.ln_impl.protos.walletunlocker_pb2 as unlocker

from app.models.lightning import (
    FeeRevenue,
    ForwardSuccessEvent,
    GenericTx,
    Invoice,
    Channel,
    InvoiceState,
    LnInfo,
    NewAddressInput,
    OnchainAddressType,
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


def get_implementation_name() -> str:
    return "LND"


async def get_wallet_balance_impl() -> WalletBalance:
    try:
        w_req = ln.WalletBalanceRequest()
        onchain = await lncfg.lnd_stub.WalletBalance(w_req)

        c_req = ln.ChannelBalanceRequest()
        channel = await lncfg.lnd_stub.ChannelBalance(c_req)

        return WalletBalance.from_grpc(onchain, channel)
    except grpc.aio._call.AioRpcError as error:
        _check_if_locked(error)
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, detail=error.details()
        )


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

    try:
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
    except grpc.aio._call.AioRpcError as error:
        _check_if_locked(error)
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, detail=error.details()
        )


async def list_invoices_impl(
    pending_only: bool, index_offset: int, num_max_invoices: int, reversed: bool
):
    try:
        req = ln.ListInvoiceRequest(
            pending_only=pending_only,
            index_offset=index_offset,
            num_max_invoices=num_max_invoices,
            reversed=reversed,
        )
        response = await lncfg.lnd_stub.ListInvoices(req)
        return [Invoice.from_grpc(i) for i in response.invoices]
    except grpc.aio._call.AioRpcError as error:
        _check_if_locked(error)
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, detail=error.details()
        )


async def list_on_chain_tx_impl() -> List[OnChainTransaction]:
    try:
        req = ln.GetTransactionsRequest()
        response = await lncfg.lnd_stub.GetTransactions(req)
        return [OnChainTransaction.from_grpc(t) for t in response.transactions]
    except grpc.aio._call.AioRpcError as error:
        _check_if_locked(error)
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, detail=error.details()
        )


async def list_payments_impl(
    include_incomplete: bool, index_offset: int, max_payments: int, reversed: bool
):
    try:
        req = ln.ListPaymentsRequest(
            include_incomplete=include_incomplete,
            index_offset=index_offset,
            max_payments=max_payments,
            reversed=reversed,
        )
        response = await lncfg.lnd_stub.ListPayments(req)
        return [Payment.from_grpc(p) for p in response.payments]
    except grpc.aio._call.AioRpcError as error:
        _check_if_locked(error)
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, detail=error.details()
        )


async def add_invoice_impl(
    value_msat: int, memo: str = "", expiry: int = 3600, is_keysend: bool = False
) -> Invoice:
    try:
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
    except grpc.aio._call.AioRpcError as error:
        _check_if_locked(error)
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, detail=error.details()
        )


async def decode_pay_request_impl(pay_req: str) -> PaymentRequest:
    try:
        req = ln.PayReqString(pay_req=pay_req)
        res = await lncfg.lnd_stub.DecodePayReq(req)
        return PaymentRequest.from_grpc(res)
    except grpc.aio._call.AioRpcError as error:
        _check_if_locked(error)
        if error.details() != None and error.details().find("checksum failed.") > -1:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, detail="Invalid payment request string"
            )
        else:
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR, detail=error.details()
            )


async def get_fee_revenue_impl() -> FeeRevenue:
    req = ln.FeeReportRequest()
    res = await lncfg.lnd_stub.FeeReport(req)
    return FeeRevenue.from_grpc(res)


async def new_address_impl(input: NewAddressInput) -> str:
    t = 1 if input.type == OnchainAddressType.NP2WKH else 2
    try:
        req = ln.NewAddressRequest(type=t)
        response = await lncfg.lnd_stub.NewAddress(req)
        return response.address
    except grpc.aio._call.AioRpcError as error:
        _check_if_locked(error)
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
        _check_if_locked()
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
    pay_req: str,
    timeout_seconds: int,
    fee_limit_msat: int,
    amount_msat: Optional[int] = None,
) -> Payment:
    try:
        r = router.SendPaymentRequest(
            payment_request=pay_req,
            timeout_seconds=timeout_seconds,
            fee_limit_msat=fee_limit_msat,
            amt_msat=amount_msat,
        )

        p = None
        async for response in lncfg.router_stub.SendPaymentV2(r):
            p = Payment.from_grpc(response)
            await send_sse_message(SSE.LN_PAYMENT_STATUS, p.dict())
        return p
    except grpc.aio._call.AioRpcError as error:
        _check_if_locked(error)
        if (
            error.details() != None
            and error.details().find("invalid bech32 string") > -1
        ):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, detail="Invalid payment request string"
            )
        elif (
            error.details() != None
            and error.details().find(
                "amount must be specified when paying a zero amount invoice"
            )
            > -1
        ):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail="amount must be specified when paying a zero amount invoice",
            )
        elif (
            error.details() != None
            and error.details().find(
                "amount must not be specified when paying a non-zero  amount invoice"
            )
            > -1
        ):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail="amount must not be specified when paying a non-zero amount invoice",
            )
        elif (
            error.details() != None
            and error.details().find("invoice is already paid") > -1
        ):
            raise HTTPException(
                status.HTTP_409_CONFLICT, detail="invoice is already paid"
            )
        else:
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR, detail=error.details()
            )


async def get_ln_info_impl() -> LnInfo:
    try:
        req = ln.GetInfoRequest()
        response = await lncfg.lnd_stub.GetInfo(req)
        return LnInfo.from_grpc(get_implementation_name(), response)
    except grpc.aio._call.AioRpcError as error:
        _check_if_locked(error)
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, detail=error.details()
        )


async def unlock_wallet_impl(password: str) -> bool:
    try:
        req = unlocker.UnlockWalletRequest(wallet_password=bytes(password, "utf-8"))
        await lncfg.wallet_unlocker.UnlockWallet(req)
        return True
    except grpc.aio._call.AioRpcError as error:
        if error.details().find("invalid passphrase") > -1:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail=error.details())
        elif error.details().find("wallet already unlocked") > -1:
            raise HTTPException(
                status.HTTP_412_PRECONDITION_FAILED, detail=error.details()
            )
        else:
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR, detail=error.details()
            )


async def listen_invoices() -> Invoice:
    request = ln.InvoiceSubscription()
    try:
        async for r in lncfg.lnd_stub.SubscribeInvoices(request):
            yield Invoice.from_grpc(r)
    except grpc.aio._call.AioRpcError as error:
        _check_if_locked(error)
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, detail=error.details()
        )


async def listen_forward_events() -> ForwardSuccessEvent:
    request = router.SubscribeHtlcEventsRequest()
    try:
        _fwd_cache = {}

        async for e in lncfg.router_stub.SubscribeHtlcEvents(request):
            if e.event_type != 3:
                continue

            evt = str(e)
            failed_event = "forward_fail_event" in evt or "link_fail_event" in evt
            if not e.incoming_htlc_id in _fwd_cache and not failed_event:
                _fwd_cache[e.incoming_htlc_id] = e
            elif e.incoming_htlc_id in _fwd_cache and not failed_event:
                if hasattr(e, "settle_event") and len(e.settle_event.preimage) > 0:
                    old_e = _fwd_cache[e.incoming_htlc_id]
                    del _fwd_cache[e.incoming_htlc_id]
                    amt_in_msat = old_e.forward_event.info.incoming_amt_msat
                    amt_out_msat = old_e.forward_event.info.outgoing_amt_msat
                    fee = amt_in_msat - amt_out_msat
                    yield ForwardSuccessEvent(
                        timestamp_ns=e.timestamp_ns,
                        chan_id_in=e.incoming_channel_id,
                        chan_id_out=e.outgoing_channel_id,
                        amt_in_msat=amt_in_msat,
                        amt_out_msat=amt_out_msat,
                        fee_msat=fee,
                    )
            elif failed_event and e.incoming_htlc_id in _fwd_cache:
                del _fwd_cache[e.incoming_htlc_id]

    except grpc.aio._call.AioRpcError as error:
        _check_if_locked(error)
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, detail=error.details()
        )


def _check_if_locked(error):
    if error.details() != None and error.details().find("wallet locked") > -1:
        raise HTTPException(
            status.HTTP_423_LOCKED,
            detail="Wallet is locked. Unlock via /lightning/unlock-wallet",
        )

async def channel_open_impl(local_funding_amount: int, node_URI: str, target_confs: int) -> str:

    try:

        pubkey=node_URI.split("@")[0]
        host=node_URI.split("@")[1]

        # make sure to be connected to peer
        r = ln.ConnectPeerRequest(
        addr=ln.LightningAddress(pubkey=pubkey, host=host),
        perm=False,
        timeout=10,
        )
        try:
            await lncfg.lnd_stub.ConnectPeer(r)
        except grpc.aio._call.AioRpcError as error:
            if (
            error.details() != None
            and error.details().find("already connected to peer") > -1
            ):
                print("ALREADY CONNECTED TO PEER")
                print(str(pubkey))

            else:
                raise error

        # open channel
        r = ln.OpenChannelRequest(
        node_pubkey=bytes.fromhex(pubkey),
        local_funding_amount=local_funding_amount,
        target_conf=target_confs
        )
        async for response in lncfg.lnd_stub.OpenChannel(r):
            # TODO: this is still some bytestring that needs correct convertion to a string txid (ok OK for now)
            return str(response.chan_pending.txid)

    except grpc.aio._call.AioRpcError as error:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, detail=error.details()
        )

async def peer_resolve_alias(nodepub: str) -> str:

    # get fresh list of peers and their aliases
    try:

        request = ln.NodeInfoRequest(
        pub_key=nodepub,
        include_channels=False
        )
        response = await lncfg.lnd_stub.GetNodeInfo(request)
        return str(response.node.alias)

    except grpc.aio._call.AioRpcError as error:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, detail=error.details()
        )

async def channel_list_impl() -> List[Channel]:

    try:

        request = ln.ListChannelsRequest()
        response = await lncfg.lnd_stub.ListChannels(request)

        channels=[]
        for channel_grpc in response.channels:
            channel = Channel.from_grpc(channel_grpc)
            channel.peer_alias= await peer_resolve_alias(channel.peer_publickey)
            channels.append(channel)
            
        request = ln.PendingChannelsRequest()
        response = await lncfg.lnd_stub.PendingChannels(request)
        for channel_grpc in response.pending_open_channels:
            channel = Channel.from_grpc_pending(channel_grpc.channel)
            channel.peer_alias= await peer_resolve_alias(channel.peer_publickey)
            channels.append(channel) 

        return channels

    except grpc.aio._call.AioRpcError as error:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, detail=error.details()
        )

async def channel_close_impl(channel_id: int, force_close: bool) -> str:

    if not ':' in channel_id:
        raise ValueError("channel_id must contain : for lnd")

    try:

        funding_txid=channel_id.split(":")[0]
        output_index=channel_id.split(":")[1]

        request = ln.CloseChannelRequest(
        channel_point=ln.ChannelPoint(funding_txid_str=funding_txid, output_index=int(output_index)),
        force=force_close,
        target_conf=6
        )
        async for response in lncfg.lnd_stub.CloseChannel(request):
            # TODO: this is still some bytestring that needs correct convertion to a string txid (ok OK for now)
            return str(response.close_pending.txid)

    except grpc.aio._call.AioRpcError as error:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, detail=error.details()
        )