import asyncio
import functools
import shutil
import sqlite3
import time
from argparse import ArgumentError
from typing import AsyncGenerator, List, Optional
from unicodedata import category

from decouple import config
from fastapi.exceptions import HTTPException
from starlette import status

from app.models.lightning import (
    FeeRevenue,
    ForwardSuccessEvent,
    GenericTx,
    Invoice,
    InvoiceState,
    LnInfo,
    NewAddressInput,
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
from app.utils import bitcoin_rpc
from app.utils import lightning_config as lncfg


# https://gist.github.com/phizaz/20c36c6734878c6ec053245a477572ec
# pyln does not yet support asyncio, so we need to force wrap them
# with an async function.
def force_async(fn):
    """
    turns a sync function to async function using threads
    """
    import asyncio
    from concurrent.futures import ThreadPoolExecutor

    pool = ThreadPoolExecutor()

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        future = pool.submit(fn, *args, **kwargs)
        return asyncio.wrap_future(future)  # make it awaitable

    return wrapper


def get_implementation_name() -> str:
    return "CLN_UNIX_SOCKET"


async def get_wallet_balance_impl():
    @force_async
    def _list_funds() -> WalletBalance:
        res = lncfg.cln_sock.listfunds()
        onchain_confirmed = onchain_unconfirmed = onchain_total = 0

        for o in res["outputs"]:
            sat = o["value"]
            onchain_total += sat
            if o["status"] == "confirmed":
                onchain_confirmed += sat
            else:
                onchain_unconfirmed += sat

        chan_local = chan_remote = chan_pending_local = chan_pending_remote = 0
        for c in res["channels"]:
            our_msat = c["our_amount_msat"].millisatoshis
            their_msat = c["amount_msat"].millisatoshis - our_msat

            if c["state"] == "CHANNELD_NORMAL":
                chan_local += our_msat
                chan_remote += their_msat
            else:
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

    return await _list_funds()


# Decoding the payment request take a long time,
# hence we build a simple cache here.
memo_cache = {}
block_cache = {}


class CLNOutput:
    prev_out_tx: str
    prev_out_index: int
    value: int
    type: int
    status: int
    keyindex: int
    channel_id: int
    peer_id: str
    commitment_point: str
    confirmation_height: int
    spend_height: int
    scriptpubkey: str
    reserved_til: int
    option_anchor_output: int
    csv_lock: int

    @classmethod
    def from_db_entry(cls, entry):
        pass


def _get_block_time(block_height: int) -> tuple:
    if block_height is None or block_height < 0:
        raise ArgumentError("block_height cannot be None or negative")

    if block_height in block_cache:
        print("cache hit")
        return block_cache[block_height]

    res = bitcoin_rpc("getblockstats", params=[block_height]).json()
    hash = res["result"]["blockhash"]
    block = bitcoin_rpc("getblock", params=[hash]).json()["result"]
    block_cache[block_height] = (block["time"], block["mediantime"])
    return block_cache[block_height]


async def list_all_tx_impl(
    successfull_only: bool, index_offset: int, max_tx: int, reversed: bool
) -> List[GenericTx]:
    @force_async
    def _list_invoices():
        return lncfg.cln_sock.listinvoices()

    @force_async
    def _list_payments():
        return lncfg.cln_sock.listpays()

    @force_async
    def _list_transactions(current_block_height: int):
        # Make a temporary copy of the file to avoid locking the db.
        # CLN might want to write while we read.
        src = "/home/fusion44/.lightning/testnet/lightningd.sqlite3"
        dest = "/tmp/lightningd.sqlite3"
        shutil.copyfile(src, dest)

        conn = sqlite3.connect(dest, uri=True)
        cur = conn.execute("select * from outputs")
        res = cur.fetchall()
        conn.close()

        txs = []
        for o in res:
            # prev_out_tx = o[0].hex()
            amount = o[2]
            conf_block = o[9]
            spent_block = o[10]
            conf_time = _get_block_time(conf_block)[0]

            txs.append(
                GenericTx(
                    id="my id",
                    category=TxCategory.ONCHAIN,
                    type=TxType.RECEIVE,
                    amount=amount,
                    time_stamp=conf_time,
                    status=TxStatus.SUCCEEDED,
                    comment="",
                    block_height=conf_block,
                    num_confs=current_block_height - conf_block,
                )
            )

            if spent_block is not None:
                spent_time = _get_block_time(conf_block)[0]
                txs.append(
                    GenericTx(
                        id="my id",
                        category=TxCategory.ONCHAIN,
                        type=TxType.SEND,
                        amount=amount,
                        time_stamp=spent_time,
                        status=TxStatus.SUCCEEDED,
                        comment="",
                        block_height=spent_block,
                        num_confs=current_block_height - spent_block,
                    )
                )

        return txs

    try:
        start = time.time()

        info = await get_ln_info_impl()  # for the current block height
        res = await asyncio.gather(
            *[
                _list_invoices(),
                _list_transactions(info.block_height),
                _list_payments(),
            ]
        )

        tx = []
        for i in res[0]["invoices"]:
            tx.append(GenericTx.from_cln_json_invoice(i))

        # add all transactions
        tx = tx + res[1]

        for p in res[2]["pays"]:
            bolt11 = p["bolt11"]
            comment = ""
            if bolt11 in memo_cache:
                comment = memo_cache[bolt11]
            else:
                pr = await decode_pay_request_impl(bolt11)
                comment = pr.description
                memo_cache[bolt11] = pr.description
            tx.append(GenericTx.from_cln_json_payment(p, comment))

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

        end = time.time()
        print("The time of execution of above program is :", end - start)

        return tx[index_offset : index_offset + max_tx]
    except sqlite3.OperationalError as e:
        print("Error while trying to open the database:", e)


async def list_invoices_impl(
    pending_only: bool, index_offset: int, num_max_invoices: int, reversed: bool
) -> List[Invoice]:
    # TODO: Core Lightning returns way less information about
    # the invoice compared to LND. Only way to extract the data is to
    # decode the pay request... seems inefficient.
    # TODO: Core Lightning does not yet allow for proper paging. Cache this?
    @force_async
    def _list_invoices():
        return lncfg.cln_sock.listinvoices()

    res = await _list_invoices()

    tx = []
    for i in res["invoices"]:
        if pending_only:
            if i["status"] == "unpaid":
                tx.append(Invoice.from_cln_json(i))
        else:
            tx.append(Invoice.from_cln_json(i))

    if reversed:
        tx.reverse()

    if num_max_invoices == 0 or num_max_invoices == None:
        return tx

    return tx[index_offset : index_offset + num_max_invoices]


async def list_on_chain_tx_impl() -> List[OnChainTransaction]:
    raise NotImplementedError("c-lightning not yet implemented")


async def list_payments_impl(
    include_incomplete: bool, index_offset: int, max_payments: int, reversed: bool
):
    raise NotImplementedError("c-lightning not yet implemented")


async def add_invoice_impl(
    value_msat: int, memo: str = "", expiry: int = 3600, is_keysend: bool = False
) -> Invoice:
    raise NotImplementedError("c-lightning not yet implemented")


async def decode_pay_request_impl(pay_req: str) -> PaymentRequest:
    @force_async
    def _decode() -> PaymentRequest:
        return PaymentRequest.from_cln_json(lncfg.cln_sock.decodepay(pay_req))

    return await _decode()


async def get_fee_revenue_impl() -> FeeRevenue:
    @force_async
    def _get_fee_revenue() -> FeeRevenue:
        res = lncfg.cln_sock.listforwards(status="settled")
        day = week = month = year = total = 0

        now = time.time()
        t_day = now - 86400.0  # 1 day
        t_week = now - 604800.0  # 1 week
        t_month = now - 2592000.0  # 1 month
        t_year = now - 31536000.0  # 1 year

        # TODO: performance: cache this in redis
        for f in res["forwards"]:
            resolved_time = f["resolved_time"]
            fee = f["fee"]
            total += fee

            if resolved_time > t_day:
                day += fee
                week += fee
                month += fee
                year += fee
            elif resolved_time > t_week:
                week += fee
                month += fee
                year += fee
            elif resolved_time > t_month:
                month += fee
                year += fee
            elif resolved_time > t_year:
                year += fee

        return FeeRevenue(day=day, week=week, month=month, year=year, total=total)

    return await _get_fee_revenue()


async def new_address_impl(input: NewAddressInput) -> str:
    raise NotImplementedError("c-lightning not yet implemented")


async def send_coins_impl(input: SendCoinsInput) -> SendCoinsResponse:
    raise NotImplementedError("c-lightning not yet implemented")


async def send_payment_impl(
    pay_req: str,
    timeout_seconds: int,
    fee_limit_msat: int,
    amount_msat: Optional[int] = None,
) -> Payment:
    raise NotImplementedError("c-lightning not yet implemented")


async def get_ln_info_impl() -> LnInfo:
    @force_async
    def _get_info() -> LnInfo:
        res = lncfg.cln_sock.getinfo()
        return LnInfo.from_cln_json(get_implementation_name(), res)

    return await _get_info()


async def unlock_wallet_impl(password: str) -> bool:
    raise NotImplementedError("c-lightning not yet implemented")


async def listen_invoices() -> AsyncGenerator[Invoice, None]:
    @force_async
    def _wrapper(ln, last_pay_index):
        "async wrapper for waitanyinvoice"
        return ln.waitanyinvoice(last_pay_index)

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

    # wait for the invoices
    try:
        while True:
            r = await _wrapper(lncfg.cln_sock, last_pay_index=lastpay_index)
            r = Invoice.from_cln_json(r)
            lastpay_index = r.settle_index
            yield r
    except TypeError as e:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail=e)
    except AttributeError as ae:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail=ae)


async def listen_forward_events() -> ForwardSuccessEvent:
    # CLN has no subscription to forwarded events.
    # We must poll instead.

    interval = config("gather_ln_info_interval", default=2, cast=float)
    if interval > 0.2:
        # We don't want to poll too often, as it will slow down the
        # server but we still want to be a bit quicker than the
        # routine that sends the SSE messages in the lightning
        # repository.
        interval - 0.1

    # make sure we know how many forewards we have
    # we need to calculate the difference between each iteration
    res = lncfg.cln_sock.listforwards(status="settled")
    num_fwd_last_poll = len(res["forwards"])
    while True:
        res = lncfg.cln_sock.listforwards(status="settled")
        if len(res["forwards"]) > num_fwd_last_poll:
            fwds = res["forwards"][num_fwd_last_poll:]
            for fwd in fwds:
                yield ForwardSuccessEvent.from_cln_json(fwd)

            num_fwd_last_poll = len(res["forwards"])
        await asyncio.sleep(interval - 0.1)
