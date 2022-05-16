import asyncio
import shutil
import sqlite3
import time
from argparse import ArgumentError
from typing import AsyncGenerator, List, Optional

import grpc
from decouple import config
from fastapi.exceptions import HTTPException
from starlette import status

import app.repositories.ln_impl.protos.cln.node_pb2 as ln
import app.repositories.ln_impl.protos.cln.primitives_pb2 as lnp
from app.models.lightning import (
    FeeRevenue,
    ForwardSuccessEvent,
    GenericTx,
    Invoice,
    InvoiceState,
    LnInfo,
    NewAddressInput,
    OnchainAddressType,
    OnChainTransaction,
    Payment,
    PaymentRequest,
    SendCoinsInput,
    SendCoinsResponse,
    TxCategory,
    TxStatus,
    TxType,
    WalletBalance,
)
from app.utils import bitcoin_rpc_async
from app.utils import lightning_config as lncfg
from app.utils import next_push_id


def get_implementation_name() -> str:
    return "CLN_GRPC"


async def get_wallet_balance_impl() -> WalletBalance:
    req = ln.ListfundsRequest()
    res = await lncfg.cln_stub.ListFunds(req)
    onchain_confirmed = onchain_unconfirmed = onchain_total = 0

    for o in res.outputs:
        sat = o.amount_msat.msat
        onchain_total += sat
        if o.status == 0:
            onchain_unconfirmed += sat
        elif o.status == 1:
            onchain_confirmed += sat
        # 2 is spent => ignore

    chan_local = chan_remote = chan_pending_local = chan_pending_remote = 0
    for c in res.channels:
        our_msat = c.our_amount_msat.msat
        their_msat = c.amount_msat.msat - our_msat

        if c.state == 2:  # ChanneldNormal
            chan_local += our_msat
            chan_remote += their_msat
        else:
            # treat everything else as pending for now
            chan_pending_local += our_msat
            chan_pending_remote += their_msat

    return WalletBalance(
        onchain_confirmed_balance=onchain_confirmed,
        onchain_total_balance=onchain_total,
        onchain_unconfirmed_balance=onchain_unconfirmed,
        channel_local_balance=chan_local,
        channel_remote_balance=chan_remote,
        # TODO: find out how to get these values with CLN
        channel_unsettled_local_balance=0,
        channel_unsettled_remote_balance=0,
        channel_pending_open_local_balance=chan_pending_local,
        channel_pending_open_remote_balance=chan_pending_remote,
    )


# Decoding the payment request take a long time,
# hence we build a simple cache here.
memo_cache = {}
block_cache = {}


async def _get_block_time(block_height: int) -> tuple:
    if block_height is None or block_height < 0:
        raise ArgumentError("block_height cannot be None or negative")

    if block_height in block_cache:
        return block_cache[block_height]

    res = await bitcoin_rpc_async("getblockstats", params=[block_height])
    hash = res["result"]["blockhash"]
    block = await bitcoin_rpc_async("getblock", params=[hash])
    block_cache[block_height] = (block["result"]["time"], block["result"]["mediantime"])
    return block_cache[block_height]


async def list_all_tx_impl(
    successfull_only: bool, index_offset: int, max_tx: int, reversed: bool
) -> List[GenericTx]:
    raise NotImplementedError("c-lightning not yet implemented")


async def list_invoices_impl(
    pending_only: bool, index_offset: int, num_max_invoices: int, reversed: bool
) -> List[Invoice]:
    req = ln.ListinvoicesRequest()
    res = await lncfg.cln_stub.ListInvoices(req)

    tx = []
    for i in res.invoices:
        if pending_only:
            if i.status == 0:
                tx.append(Invoice.from_cln_grpc(i))
        else:
            tx.append(Invoice.from_cln_grpc(i))

    if reversed:
        tx.reverse()

    if num_max_invoices == 0 or num_max_invoices == None:
        return tx

    return tx[index_offset : index_offset + num_max_invoices]


async def list_on_chain_tx_impl() -> List[OnChainTransaction]:
    # Make a temporary copy of the file to avoid locking the db.
    # CLN might want to write while we read.
    info = await get_ln_info_impl()

    # FIXME(#87): Once Core Lightnings accountability plugin is available
    src = "/home/admin/.lightning/testnet/lightningd.sqlite3"
    dest = "/tmp/lightningd.sqlite3"
    shutil.copyfile(src, dest)

    conn = sqlite3.connect(dest, uri=True)
    cur = conn.execute("select * from outputs")
    res = cur.fetchall()
    conn.close()

    txs = []
    for o in res:
        prev_out_tx = o[0].hex()
        amount = o[2]
        conf_block = o[9]
        spent_block = o[10]
        conf_time = (await _get_block_time(conf_block))[0]
        txs.append(
            OnChainTransaction(
                tx_hash=f"prev_out_tx {prev_out_tx}",
                amount=amount,
                num_confirmations=info.block_height - conf_block,
                block_height=conf_block,
                time_stamp=conf_time,
                total_fees=0,
            )
        )

        if spent_block is not None:
            spent_time = (await _get_block_time(spent_block))[0]
            txs.append(
                OnChainTransaction(
                    tx_hash=f"prev_out_tx {prev_out_tx}",
                    amount=-amount,
                    num_confirmations=info.block_height - spent_block,
                    block_height=spent_block,
                    time_stamp=spent_time,
                    total_fees=0,
                ),
            )

    return txs


async def list_payments_impl(
    include_incomplete: bool, index_offset: int, max_payments: int, reversed: bool
):
    req = ln.ListpaysRequest()
    res = await lncfg.cln_stub.ListPays(req)

    pays = []
    for p in res.pays:
        if p.status == 2:
            # always include completed payments
            pays.append(Payment.from_cln_grpc(p))
            continue

        if include_incomplete:
            pays.append(Payment.from_cln_grpc(p))

    if reversed:
        pays.reverse()

    if max_payments == 0 or max_payments == None:
        return pays

    return pays[index_offset : index_offset + max_payments]


async def add_invoice_impl(
    value_msat: int, memo: str = "", expiry: int = 3600, is_keysend: bool = False
) -> Invoice:
    if value_msat < 0:
        raise ArgumentError("value_msat cannot be negative")

    msat = None
    if value_msat == 0:
        msat = lnp.AmountOrAny(any=True)
    elif value_msat > 0:
        msat = lnp.AmountOrAny(amount=lnp.Amount(msat=value_msat))

    id = next_push_id()
    req = ln.InvoiceRequest(
        msatoshi=msat,
        description=memo,
        label=id,
        expiry=expiry,
    )

    res = await lncfg.cln_stub.Invoice(req)

    return Invoice(
        payment_request=res.bolt11,
        memo=memo,
        value_msat=value_msat,
        expiry_date=res.expires_at,
        add_index=id,
        state=InvoiceState.OPEN,
    )


async def decode_pay_request_impl(pay_req: str) -> PaymentRequest:
    raise NotImplementedError("c-lightning not yet implemented")


async def get_fee_revenue_impl() -> FeeRevenue:
    # status 1 == "settled"
    req = ln.ListforwardsRequest(status=1)
    res = await lncfg.cln_stub.ListForwards(req)

    day = week = month = year = total = 0

    now = time.time()
    t_day = now - 86400.0  # 1 day
    t_week = now - 604800.0  # 1 week
    t_month = now - 2592000.0  # 1 month
    t_year = now - 31536000.0  # 1 year

    # TODO: performance: cache this in redis
    for f in res.forwards:
        received_time = f.received_time
        fee = f.fee_msat.msat
        total += fee

        if received_time > t_day:
            day += fee
            week += fee
            month += fee
            year += fee
        elif received_time > t_week:
            week += fee
            month += fee
            year += fee
        elif received_time > t_month:
            month += fee
            year += fee
        elif received_time > t_year:
            year += fee

    return FeeRevenue(day=day, week=week, month=month, year=year, total=total)


async def new_address_impl(input: NewAddressInput) -> str:
    if input.type == OnchainAddressType.P2WKH:
        req = ln.NewaddrRequest(addresstype=2)
        res = await lncfg.cln_stub.NewAddr(req)
        return res.bech32

    req = ln.NewaddrRequest(addresstype=1)
    res = await lncfg.cln_stub.NewAddr(req)
    return res.p2sh_segwit


async def send_coins_impl(input: SendCoinsInput) -> SendCoinsResponse:
    fee_rate: lnp.Feerate = None
    if input.sat_per_vbyte != None and input.sat_per_vbyte > 0:
        fee_rate = lnp.Feerate(perkw=input.sat_per_vbyte)
    elif input.target_conf != None and input.target_conf == 1:
        fee_rate = lnp.Feerate(urgent=True)
    elif input.target_conf != None and input.target_conf >= 2:
        fee_rate = lnp.Feerate(normal=True)
    elif input.target_conf != None and input.target_conf >= 10:
        fee_rate = lnp.Feerate(slow=True)

    try:
        funds = await lncfg.cln_stub.ListFunds(ln.ListfundsRequest())
        if len(funds.outputs) == 0:
            raise HTTPException(
                status.HTTP_412_PRECONDITION_FAILED,
                detail=f"Could not afford {input.amount}sat. No UTXOs available at all",
            )

        utxos = []
        max_amt = 0
        for o in funds.outputs:
            utxos.append(lnp.Outpoint(txid=o.txid, outnum=o.output))
            max_amt += o.amount_msat.msat

        if max_amt <= input.amount:
            raise HTTPException(
                status.HTTP_412_PRECONDITION_FAILED,
                detail=f"Could not afford {input.amount}sat. Not enough funds available",
            )

        req = ln.WithdrawRequest(
            destination=input.address,
            satoshi=lnp.AmountOrAll(amount=lnp.Amount(msat=input.amount), all=False),
            minconf=input.min_confs,
            feerate=fee_rate,
            utxos=utxos,
        )
        res = await lncfg.cln_stub.Withdraw(req)
        return SendCoinsResponse.from_cln_grpc(res, input)
    except grpc.aio._call.AioRpcError as error:
        details = error.details()
        if details and details.find("Could not parse destination address") > -1:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail="Could not parse destination address, destination should be a valid address.",
            )
        elif (
            details
            and details.find("UTXO") > -1
            and details.find("already reserved") > -1
        ):
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Server tried to use a reserved UTXO. Please submit an issue to the BlitzAPI repository.",
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
    amt = lnp.Amount(msat=amount_msat)
    fee_limit = lnp.Amount(msat=fee_limit_msat)
    req = ln.PayRequest(
        bolt11=pay_req,
        msatoshi=amt,
        maxfee=fee_limit,
        retry_for=timeout_seconds,
    )
    res = await lncfg.cln_stub.Pay(req)
    return Payment.from_cln_grpc(res)


async def get_ln_info_impl() -> LnInfo:
    req = ln.GetinfoRequest()
    res = await lncfg.cln_stub.Getinfo(req)
    return LnInfo.from_cln_grpc(get_implementation_name(), res)


async def unlock_wallet_impl(password: str) -> bool:
    # Core Lightning doesn't lock wallets,
    # so we don't need to do anything here
    return True


async def listen_invoices() -> AsyncGenerator[Invoice, None]:
    lastpay_index = 0
    invoices = await list_invoices_impl(
        pending_only=False,
        index_offset=0,
        num_max_invoices=9999999999999,
        reversed=False,
    )

    for i in invoices:  # type Invoice
        if i.state == InvoiceState.SETTLED and i.settle_index > lastpay_index:
            lastpay_index = i.settle_index

    while True:
        req = ln.WaitanyinvoiceRequest(lastpay_index=lastpay_index)
        i = await lncfg.cln_stub.WaitAnyInvoice(req)
        i = Invoice.from_cln_grpc(i)
        lastpay_index = i.settle_index
        yield i


async def listen_forward_events() -> ForwardSuccessEvent:
    # CLN has no subscription to forwarded events.
    # We must poll instead.

    interval = config("gather_ln_info_interval", default=2, cast=float)

    # make sure we know how many forewards we have
    # we need to calculate the difference between each iteration
    # status=1 == "settled"
    req = ln.ListforwardsRequest(status=1)
    res = await lncfg.cln_stub.ListForwards(req)
    num_fwd_last_poll = len(res.forwards)
    while True:
        res = await lncfg.cln_stub.ListForwards(req)
        if len(res.forwards) > num_fwd_last_poll:
            fwds = res.forwards[num_fwd_last_poll:]
            for fwd in fwds:
                yield ForwardSuccessEvent.from_cln_grpc(fwd)

            num_fwd_last_poll = len(res.forwards)
        await asyncio.sleep(interval - 0.1)
