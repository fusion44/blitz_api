import asyncio
import logging
import os
from typing import AsyncGenerator, List, Optional

import grpc
from decouple import config as dconfig
from fastapi.exceptions import HTTPException
from starlette import status

import app.repositories.ln_impl.protos.lnd.lightning_pb2 as ln
import app.repositories.ln_impl.protos.lnd.lightning_pb2_grpc as lnrpc
import app.repositories.ln_impl.protos.lnd.router_pb2 as router
import app.repositories.ln_impl.protos.lnd.router_pb2_grpc as routerrpc
import app.repositories.ln_impl.protos.lnd.walletunlocker_pb2 as unlocker
import app.repositories.ln_impl.protos.lnd.walletunlocker_pb2_grpc as unlockerrpc
from app.models.lightning import (
    Channel,
    FeeRevenue,
    ForwardSuccessEvent,
    GenericTx,
    InitLnRepoUpdate,
    Invoice,
    InvoiceState,
    LnInfo,
    LnInitState,
    NewAddressInput,
    OnchainAddressType,
    OnChainTransaction,
    Payment,
    PaymentRequest,
    SendCoinsInput,
    SendCoinsResponse,
    WalletBalance,
)
from app.utils import SSE, broadcast_sse_msg, config_get_hex_str

_lnd_connect_error_debug_msg = """
LND_GRPC: Unable to connect to LND. Possible reasons:
* Node is not reachable (ports, network down, ...)
* Macaroon is not correct
* IP is not included in LND tls certificate
    Add tlsextraip=192.168.1.xxx to lnd.conf and restart LND.
    This will recreate the TLS certificate. The .env must be adapted accordingly.
* TLS certificate is wrong. (settings changed, ...)

To Debug gRPC problems uncomment the following line in app.repositories.ln_impl.lnd_grpc.py
# os.environ["GRPC_VERBOSITY"] = "DEBUG"
This will show more debug information.
"""

_initialized = False

# Due to updated ECDSA generated tls.cert we need to let gprc know that
# we need to use that cipher suite otherwise there will be a handshake
# error when we communicate with the lnd rpc server.
os.environ["GRPC_SSL_CIPHER_SUITES"] = "HIGH+ECDSA"

# Uncomment to see full gRPC logs
# os.environ["GRPC_TRACE"] = "all"
# os.environ["GRPC_VERBOSITY"] = "DEBUG"


def _metadata_callback(context, callback):
    # for more info see grpc docs
    callback([("macaroon", _lnd_macaroon)], None)


_lnd_macaroon = config_get_hex_str(dconfig("lnd_macaroon"), name="lnd_macaroon")
_lnd_cert = bytes.fromhex(config_get_hex_str(dconfig("lnd_cert"), name="lnd_cert"))
_lnd_grpc_ip = dconfig("lnd_grpc_ip")
_lnd_grpc_port = dconfig("lnd_grpc_port")
_lnd_grpc_url = _lnd_grpc_ip + ":" + _lnd_grpc_port

_auth_creds = grpc.metadata_call_credentials(_metadata_callback)
_ssl_creds = grpc.ssl_channel_credentials(_lnd_cert)
_combined_creds = grpc.composite_channel_credentials(_ssl_creds, _auth_creds)
_channel = None
_lnd_stub = None
_router_stub = None
_wallet_unlocker = None


def _create_stubs() -> None:
    global _channel
    global _lnd_stub
    global _router_stub
    global _wallet_unlocker

    if _channel is not None:
        logging.warning("LND_GRPC: gRPC channel already created.")
        return

    _channel = grpc.aio.secure_channel(_lnd_grpc_url, _combined_creds)
    _lnd_stub = lnrpc.LightningStub(_channel)
    _router_stub = routerrpc.RouterStub(_channel)
    _wallet_unlocker = unlockerrpc.WalletUnlockerStub(_channel)

    logging.debug("LND_GRPC: Created LND gRPC stubs")


def get_implementation_name() -> str:
    return "LND_GRPC"


init_queue = asyncio.Queue()


async def _check_lnd_status(
    sleep_time: float = 2,
) -> AsyncGenerator[InitLnRepoUpdate, None]:
    logging.debug("LND_GRPC: _check_lnd_status() start")

    _lnd_connect_error_debug_msg_sent = False

    # Create a temporary channel which will be destroyed at each iteration
    # Reason is that gRPC seems to only try and connect every 5 seconds to
    # the node if it is not running. To avoid the delay we create a new
    # channel each iteration.

    global _channel
    global _lnd_stub

    channel = None
    lnd_stub = None
    while True:
        try:
            if channel is None:
                if _channel is not None:
                    channel = _channel
                    lnd_stub = _lnd_stub
                else:
                    channel = grpc.aio.secure_channel(_lnd_grpc_url, _combined_creds)
                    lnd_stub = lnrpc.LightningStub(channel)
            await lnd_stub.GetInfo(ln.GetInfoRequest())

            if _channel is None:
                _create_stubs()

            await init_queue.put(InitLnRepoUpdate(state=LnInitState.DONE))
            break
        except grpc.aio._call.AioRpcError as error:
            details = error.details()
            logging.debug(f"LND_GRPC: Waiting for LND daemon... Details {details}")

            if "failed to connect to all addresses" in details:
                await init_queue.put(
                    InitLnRepoUpdate(
                        state=LnInitState.OFFLINE,
                        msg="Unable to connect to LND daemon, waiting...",
                    )
                )

                if not _lnd_connect_error_debug_msg_sent:
                    logging.debug(_lnd_connect_error_debug_msg)
                    _lnd_connect_error_debug_msg_sent = True

                await channel.close()
                channel = None
            elif "waiting to start, RPC services not available" in details:
                await init_queue.put(
                    InitLnRepoUpdate(
                        state=LnInitState.BOOTSTRAPPING,
                        msg="Connected but waiting to start, RPC services not available",
                    )
                )
                await channel.close()
                channel = None
            elif "wallet locked, unlock it to enable full RPC access" in details:
                await init_queue.put(
                    InitLnRepoUpdate(
                        state=LnInitState.LOCKED,
                        msg="Wallet locked, unlock it to enable full RPC access",
                    )
                )
                if channel != _channel:
                    await channel.close()
                    channel = None
            elif (
                "the RPC server is in the process of starting up, but not yet ready to accept calls"
                in details
            ):
                # message from LND AFTER unlocking the wallet
                await init_queue.put(
                    InitLnRepoUpdate(
                        state=LnInitState.BOOTSTRAPPING_AFTER_UNLOCK,
                        msg="The RPC server is in the process of starting up, but not yet ready to accept calls",
                    )
                )
            else:
                logging.error(f"LND_GRPC: Unknown error: {details}")
                raise

            logging.debug(
                f"LND_GRPC: _check_lnd_status() sleeping {sleep_time} seconds..."
            )
            await asyncio.sleep(sleep_time)

    logging.debug("LND_GRPC: _check_lnd_status() done")


async def initialize_impl() -> AsyncGenerator[InitLnRepoUpdate, None]:
    logging.debug("LND_GRPC: Unable to connect to LND daemon, waiting...")
    global _initialized
    if _initialized:
        logging.warning(
            "LND_GRPC: Connection already initialized. This function must not be called twice."
        )
        yield InitLnRepoUpdate(state=LnInitState.DONE)

    logging.info("LND_GRPC: Unable to connect to LND daemon, waiting...")

    global _channel
    global _lnd_stub
    global _router_stub
    global _wallet_unlocker

    loop = asyncio.get_event_loop()
    task = loop.create_task(_check_lnd_status(sleep_time=2))

    while not _initialized:
        res = await init_queue.get()  # type: InitLnRepoUpdate

        if res.state == LnInitState.BOOTSTRAPPING_AFTER_UNLOCK and _channel is None:
            task.cancel()

            if _channel == None:
                # if res == _API_WALLET_UNLOCK_EVENT the endpoint function will have
                # created the channel for us.
                _create_stubs()

            task = loop.create_task(_check_lnd_status(sleep_time=0.5))
        elif res.state == LnInitState.DONE:
            _initialized = True
            if not task.cancelled():
                task.cancel()
        elif (
            res.state == LnInitState.OFFLINE
            or res.state == LnInitState.LOCKED
            or res.state == LnInitState.BOOTSTRAPPING_AFTER_UNLOCK
        ):
            pass  # do nothing here
        else:
            logging.warning(f"LND_GRPC: Unhandled initialization event: {res.dict()}")

        yield res

    logging.info("LND_GRPC: Initialization complete.")


async def get_wallet_balance_impl() -> WalletBalance:
    logging.debug("LND_GRPC: get_wallet_balance_impl() ")

    try:
        w_req = ln.WalletBalanceRequest()
        onchain = await _lnd_stub.WalletBalance(w_req)

        c_req = ln.ChannelBalanceRequest()
        channel = await _lnd_stub.ChannelBalance(c_req)

        return WalletBalance.from_lnd_grpc(onchain, channel)
    except grpc.aio._call.AioRpcError as error:
        _check_if_locked(error)
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, detail=error.details()
        )


# Decoding the payment request take a long time,
# hence we build a simple cache here.
memo_cache = {}


async def list_all_tx_impl(
    successful_only: bool, index_offset: int, max_tx: int, reversed: bool
) -> List[GenericTx]:
    logging.debug(
        f"LND_GRPC: list_all_tx_impl(successful_only={successful_only}, index_offset={index_offset}, max_tx={max_tx}, reversed={reversed})"
    )

    # TODO: find a better caching strategy
    list_invoice_req = ln.ListInvoiceRequest(
        pending_only=successful_only,
        index_offset=0,
        num_max_invoices=0,
        reversed=reversed,
    )

    get_tx_req = ln.GetTransactionsRequest()

    list_payments_req = ln.ListPaymentsRequest(
        include_incomplete=not successful_only,
        index_offset=0,
        max_payments=0,
        reversed=reversed,
    )

    try:
        res = await asyncio.gather(
            *[
                _lnd_stub.ListInvoices(list_invoice_req),
                _lnd_stub.GetTransactions(get_tx_req),
                _lnd_stub.ListPayments(list_payments_req),
            ]
        )

        tx = []
        for i in res[0].invoices:
            tx.append(GenericTx.from_lnd_grpc_invoice(i))
        for t in res[1].transactions:
            tx.append(GenericTx.from_lnd_grpc_onchain_tx(t))
        for p in res[2].payments:
            comment = ""
            if p.payment_request in memo_cache:
                comment = memo_cache[p.payment_request]
            else:
                if p.payment_request is not None and p.payment_request != "":
                    pr = await decode_pay_request_impl(p.payment_request)
                    comment = pr.description
                    memo_cache[p.payment_request] = pr.description
            tx.append(GenericTx.from_lnd_grpc_payment(p, comment))

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
    logging.debug("LND_GRPC: list_invoices_impl() ")

    try:
        req = ln.ListInvoiceRequest(
            pending_only=pending_only,
            index_offset=index_offset,
            num_max_invoices=num_max_invoices,
            reversed=reversed,
        )
        response = await _lnd_stub.ListInvoices(req)
        return [Invoice.from_lnd_grpc(i) for i in response.invoices]
    except grpc.aio._call.AioRpcError as error:
        _check_if_locked(error)
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, detail=error.details()
        )


async def list_on_chain_tx_impl() -> List[OnChainTransaction]:
    logging.debug("LND_GRPC: list_on_chain_tx_impl() ")

    try:
        req = ln.GetTransactionsRequest()
        response = await _lnd_stub.GetTransactions(req)
        return [OnChainTransaction.from_lnd_grpc(t) for t in response.transactions]
    except grpc.aio._call.AioRpcError as error:
        _check_if_locked(error)
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, detail=error.details()
        )


async def list_payments_impl(
    include_incomplete: bool, index_offset: int, max_payments: int, reversed: bool
):
    logging.debug(
        f"LND_GRPC: list_payments_impl(include_incomplete={include_incomplete}, index_offset{index_offset}, max_payments={max_payments}, reversed={reversed})"
    )

    try:
        req = ln.ListPaymentsRequest(
            include_incomplete=include_incomplete,
            index_offset=index_offset,
            max_payments=max_payments,
            reversed=reversed,
        )
        response = await _lnd_stub.ListPayments(req)
        return [Payment.from_lnd_grpc(p) for p in response.payments]
    except grpc.aio._call.AioRpcError as error:
        _check_if_locked(error)
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, detail=error.details()
        )


async def add_invoice_impl(
    value_msat: int, memo: str = "", expiry: int = 3600, is_keysend: bool = False
) -> Invoice:
    logging.debug(
        f"LND_GRPC: add_invoice_impl(value_msat={value_msat}, memo={memo}, expiry={expiry}, is_keysend={is_keysend})"
    )

    try:
        i = ln.Invoice(
            memo=memo,
            value_msat=value_msat,
            expiry=expiry,
            is_keysend=is_keysend,
        )

        response = await _lnd_stub.AddInvoice(i)

        # Can't use Invoice.from_lnd_grpc() here because
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
    logging.debug(f"LND_GRPC: decode_pay_request_impl(pay_req={pay_req})")

    try:
        req = ln.PayReqString(pay_req=pay_req)
        res = await _lnd_stub.DecodePayReq(req)
        return PaymentRequest.from_lnd_grpc(res)
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
    logging.debug(f"LND_GRPC: get_fee_revenue_impl()")

    req = ln.FeeReportRequest()
    res = await _lnd_stub.FeeReport(req)
    return FeeRevenue.from_lnd_grpc(res)


async def new_address_impl(input: NewAddressInput) -> str:
    logging.debug(f"LND_GRPC: new_address_impl(input={input})")

    t = 1 if input.type == OnchainAddressType.NP2WKH else 2
    try:
        req = ln.NewAddressRequest(type=t)
        response = await _lnd_stub.NewAddress(req)
        return response.address
    except grpc.aio._call.AioRpcError as error:
        _check_if_locked(error)
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, detail=error.details()
        )


async def send_coins_impl(input: SendCoinsInput) -> SendCoinsResponse:
    logging.debug(f"LND_GRPC: send_coins_impl(input={input})")

    try:
        r = ln.SendCoinsRequest(
            addr=input.address,
            amount=input.amount,
            target_conf=input.target_conf,
            sat_per_vbyte=input.sat_per_vbyte,
            min_confs=input.min_confs,
            label=input.label,
        )

        response = await _lnd_stub.SendCoins(r)
        r = SendCoinsResponse.from_lnd_grpc(response, input)
        await broadcast_sse_msg(SSE.LN_ONCHAIN_PAYMENT_STATUS, r.dict())
        return r
    except grpc.aio._call.AioRpcError as error:
        _check_if_locked()
        details = error.details()
        if details and details.find("invalid bech32 string") > -1:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail="Could not parse destination address, destination should be a valid address.",
            )
        elif details and details.find("insufficient funds available") > -1:
            raise HTTPException(status.HTTP_412_PRECONDITION_FAILED, detail=details)
        else:
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail=details)


async def send_payment_impl(
    pay_req: str,
    timeout_seconds: int,
    fee_limit_msat: int,
    amount_msat: Optional[int] = None,
) -> Payment:
    logging.debug(
        f"LND_GRPC: send_payment_impl(pay_req={pay_req}, timeout_seconds={timeout_seconds}, fee_limit_msat={fee_limit_msat}, amount_msat={amount_msat})"
    )

    try:
        r = router.SendPaymentRequest(
            payment_request=pay_req,
            timeout_seconds=timeout_seconds,
            fee_limit_msat=fee_limit_msat,
            amt_msat=amount_msat,
        )

        p = None
        async for response in _router_stub.SendPaymentV2(r):
            p = Payment.from_lnd_grpc(response)
            await broadcast_sse_msg(SSE.LN_PAYMENT_STATUS, p.dict())
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
            and error.details().find("OPENSSL_internal:CERTIFICATE_VERIFY_FAILED.") > -1
        ):
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Invalid LND credentials. SSL certificate verify failed.",
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
    logging.debug(f"LND_GRPC: get_ln_info_impl()")

    if not _initialized:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, detail="LND not fully initialized"
        )

    try:
        req = ln.GetInfoRequest()
        response = await _lnd_stub.GetInfo(req)
        return LnInfo.from_lnd_grpc(get_implementation_name(), response)
    except grpc.aio._call.AioRpcError as error:
        _check_if_locked(error)
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, detail=error.details()
        )


async def _wait_wallet_fully_ready():
    logging.debug(f"LND_GRPC: _wait_wallet_fully_ready()")

    # This must only be called after unlocking the wallet.

    while True:
        try:
            info = await _lnd_stub.GetInfo(ln.GetInfoRequest())

            if info != None:
                logging.debug(
                    f"LND_GRPC: _wait_wallet_fully_ready() breaking out of loop"
                )
                break
        except grpc.aio._call.AioRpcError as error:
            details = error.details()
            if (
                "the RPC server is in the process of starting up, but not yet ready to accept calls"
                in details
            ):
                # message from LND AFTER unlocking the wallet
                await init_queue.put(
                    InitLnRepoUpdate(
                        state=LnInitState.BOOTSTRAPPING_AFTER_UNLOCK,
                        msg="The RPC server is in the process of starting up, but not yet ready to accept calls",
                    )
                )
                await asyncio.sleep(0.1)
            else:
                logging.error(f"LND_GRPC: Unknown error: {details}")
                raise


async def unlock_wallet_impl(password: str) -> bool:
    logging.debug(f"LND_GRPC: unlock_wallet_impl(password=wedontlogpasswords)")

    try:
        if _channel is None:
            _create_stubs()

        req = unlocker.UnlockWalletRequest(wallet_password=bytes(password, "utf-8"))
        await _wallet_unlocker.UnlockWallet(req)
        await _wait_wallet_fully_ready()
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
    logging.debug(f"LND_GRPC: listen_invoices()")

    request = ln.InvoiceSubscription()
    try:
        async for r in _lnd_stub.SubscribeInvoices(request):
            yield Invoice.from_lnd_grpc(r)
    except grpc.aio._call.AioRpcError as error:
        _check_if_locked(error)
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, detail=error.details()
        )


async def listen_forward_events() -> ForwardSuccessEvent:
    logging.debug(f"LND_GRPC: listen_forward_events()")

    request = router.SubscribeHtlcEventsRequest()
    try:
        _fwd_cache = {}

        async for e in _router_stub.SubscribeHtlcEvents(request):
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
    logging.debug(f"LND_GRPC: _check_if_locked()")

    if error.details() != None and error.details().find("wallet locked") > -1:
        raise HTTPException(
            status.HTTP_423_LOCKED,
            detail="Wallet is locked. Unlock via /lightning/unlock-wallet",
        )


async def channel_open_impl(
    local_funding_amount: int, node_URI: str, target_confs: int
) -> str:
    logging.debug(
        f"LND_GRPC: channel_open_impl(local_funding_amount={local_funding_amount}, node_URI={node_URI}, target_confs={target_confs})"
    )

    try:

        pubkey = node_URI.split("@")[0]
        host = node_URI.split("@")[1]

        # make sure to be connected to peer
        r = ln.ConnectPeerRequest(
            addr=ln.LightningAddress(pubkey=pubkey, host=host),
            perm=False,
            timeout=10,
        )
        try:
            await _lnd_stub.ConnectPeer(r)
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
            target_conf=target_confs,
        )
        async for response in _lnd_stub.OpenChannel(r):
            # TODO: this is still some bytestring that needs correct conversion to a string txid (ok OK for now)
            return str(response.chan_pending.txid.hex())

    except grpc.aio._call.AioRpcError as error:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, detail=error.details()
        )


async def peer_resolve_alias(node_pub: str) -> str:
    logging.debug(f"LND_GRPC: peer_resolve_alias(node_pub={node_pub})")

    # get fresh list of peers and their aliases
    try:

        request = ln.NodeInfoRequest(pub_key=node_pub, include_channels=False)
        response = await _lnd_stub.GetNodeInfo(request)
        return str(response.node.alias)

    except grpc.aio._call.AioRpcError as error:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, detail=error.details()
        )


async def channel_list_impl() -> List[Channel]:
    logging.debug(f"LND_GRPC: channel_list_impl()")

    try:

        request = ln.ListChannelsRequest()
        response = await _lnd_stub.ListChannels(request)

        channels = []
        for channel_grpc in response.channels:
            channel = Channel.from_lnd_grpc(channel_grpc)
            channel.peer_alias = await peer_resolve_alias(channel.peer_publickey)
            channels.append(channel)

        request = ln.PendingChannelsRequest()
        response = await _lnd_stub.PendingChannels(request)
        for channel_grpc in response.pending_open_channels:
            channel = Channel.from_lnd_grpc_pending(channel_grpc.channel)
            channel.peer_alias = await peer_resolve_alias(channel.peer_publickey)
            channels.append(channel)

        return channels

    except grpc.aio._call.AioRpcError as error:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, detail=error.details()
        )


async def channel_close_impl(channel_id: int, force_close: bool) -> str:
    logging.debug(
        f"LND_GRPC: channel_close_impl(channel_id={channel_id}, force_close={force_close})"
    )

    if not ":" in channel_id:
        raise ValueError("channel_id must contain : for lnd")

    try:

        funding_txid = channel_id.split(":")[0]
        output_index = channel_id.split(":")[1]

        request = ln.CloseChannelRequest(
            channel_point=ln.ChannelPoint(
                funding_txid_str=funding_txid, output_index=int(output_index)
            ),
            force=force_close,
            target_conf=6,
        )
        async for response in _lnd_stub.CloseChannel(request):
            # TODO: this is still some bytestring that needs correct conversion to a string txid (ok OK for now)
            return str(response.close_pending.txid.hex())

    except grpc.aio._call.AioRpcError as error:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, detail=error.details()
        )
