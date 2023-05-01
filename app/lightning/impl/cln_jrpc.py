import asyncio
import json
import os
import sys
import time
from typing import AsyncGenerator, Dict, List, Optional, Union

import decouple
import grpc
from decouple import config
from fastapi.exceptions import HTTPException
from loguru import logger
from starlette import status

import app.lightning.impl.protos.cln.node_pb2 as ln
import app.lightning.impl.protos.cln.node_pb2_grpc as clnrpc
import app.lightning.impl.protos.cln.primitives_pb2 as lnp
from app.api.utils import SSE, broadcast_sse_msg, config_get_hex_str, next_push_id
from app.bitcoind.utils import bitcoin_rpc_async
from app.lightning.impl.cln_utils import (
    calc_fee_rate_str,
    cln_classify_fee_revenue,
    parse_cln_msat,
)
from app.lightning.impl.ln_base import LightningNodeBase
from app.lightning.models import (
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
    TxStatus,
    WalletBalance,
)
from app.lightning.utils import generic_grpc_error_handler

_WAIT_ANY_INVOICE_ID = 0
_SOCKET_BUFFER_SIZE_LIMIT = 1024 * 1024 * 10  # 10 MB


class LnNodeCLNjRPC(LightningNodeBase):
    lastpay_index = 0
    _current_id: int = _WAIT_ANY_INVOICE_ID + 1
    _futures: dict[int, asyncio.Future] = {}
    _socket_path: str = None
    _reader: asyncio.StreamReader = None
    _writer: asyncio.StreamWriter = None
    _loop: asyncio.AbstractEventLoop = None
    _initialized: bool = False
    _invoice_queue = asyncio.Queue()

    # Decoding the payment request take a long time,
    # hence we build a simple cache here.
    _bolt11_cache: dict[str, PaymentRequest] = {}
    _block_cache = {}

    def get_implementation_name(self) -> str:
        return "CLN_JRPC"

    @logger.catch(exclude=(HTTPException,))
    async def initialize(self) -> AsyncGenerator[InitLnRepoUpdate, None]:
        logger.info("Initializing CLN JSON-RPC implementation.")
        if self._initialized:
            logger.warning(
                "Connection already initialized. This function must not be called twice."
            )
            yield InitLnRepoUpdate(state=LnInitState.DONE)

        yield InitLnRepoUpdate(state=LnInitState.BOOTSTRAPPING)

        try:
            self._socket_path = decouple.config("cln_jrpc_path")
        except decouple.UndefinedValueError as e:
            logger.debug(e)
            logger.error(
                f"CLN JSON-RPC implementation set, but cln_jrpc_path is missing from the config file."
            )
            sys.exit(1)

        # check if the file self._socket_path exists
        if not os.path.exists(self._socket_path):
            logger.error(f"Socket file {self._socket_path} is not readable.")
            sys.exit(1)

        logger.info(
            f"Establishing a connection to the CLN socket at {self._socket_path}"
        )

        self._loop = asyncio.get_running_loop()

        while True:
            try:
                self._reader, self._writer = await asyncio.open_unix_connection(
                    path=self._socket_path,
                    limit=_SOCKET_BUFFER_SIZE_LIMIT,
                )

                break
            except ConnectionRefusedError:
                logger.info("CLN ConnectionRefusedError. Retrying in 10 seconds.")
                await asyncio.sleep(10)

        asyncio.create_task(self._read_loop())

        logger.info("Setting up invoice waitanyinvoice subscription.")
        await self._refresh_invoice_sub(True)

        info = await self.get_ln_info()
        if info is None:
            logger.error("Failed to get CLN node info.")
            sys.exit(1)

        logger.success(
            f"Connected to CLN node with alias {info.alias} and pubkey {info.identity_pubkey[:10]}...{info.identity_pubkey[-10:]}"
        )

        yield InitLnRepoUpdate(state=LnInitState.DONE)

    @logger.catch(exclude=(HTTPException,))
    async def get_wallet_balance(self) -> WalletBalance:
        logger.trace("get_wallet_balance()")

        # TODO: CLN doesn't currently include pending mempool transactions
        # implement the following:
        # https://github.com/andrewtoth/listmempoolfunds/blob/master/listmempoolfunds.py

        res = await self._send_request("listfunds")
        res = res["result"]
        onchain_confirmed = onchain_unconfirmed = onchain_total = 0
        chan_local = chan_remote = chan_pending_local = chan_pending_remote = 0

        for o in res["outputs"]:
            sat = parse_cln_msat(o["amount_msat"]) / 1000

            if o["status"] == "unconfirmed":
                onchain_unconfirmed += sat
            elif o["status"] == "confirmed" and not o["reserved"]:
                onchain_confirmed += sat

        onchain_total = onchain_confirmed + onchain_unconfirmed

        for c in res["channels"]:
            our_msat = parse_cln_msat(c["our_amount_msat"])
            their_msat = parse_cln_msat(c["amount_msat"]) - our_msat

            if c["state"] == "CHANNELD_NORMAL":
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

    async def _get_block_time(self, block_height: int) -> tuple:
        logger.trace(f"_get_block_time(block_height={block_height}) ")

        if block_height is None or block_height < 0:
            raise ValueError("block_height cannot be None or negative")

        if block_height in self._block_cache:
            return self._block_cache[block_height]

        res = await bitcoin_rpc_async("getblockstats", params=[block_height])
        hash = res["result"]["blockhash"]
        block = await bitcoin_rpc_async("getblock", params=[hash])
        self._block_cache[block_height] = (
            block["result"]["time"],
            block["result"]["mediantime"],
        )

        return self._block_cache[block_height]

    @logger.catch(exclude=(HTTPException,))
    async def list_all_tx(
        self, successful_only: bool, index_offset: int, max_tx: int, reversed: bool
    ) -> List[GenericTx]:
        logger.trace(
            f"list_all_tx({successful_only}, {index_offset}, {max_tx}, {reversed})"
        )

        res = await asyncio.gather(
            *[
                self.list_invoices(False, 0, 0, False),
                self.list_on_chain_tx(),
                self.list_payments(True, 0, 0, False),
                self.get_ln_info(),
            ]
        )

        if res[0] is None:
            logger.error("list_invoices() returned None")
        if res[1] is None:
            logger.error("list_on_chain_tx() returned None")
        if res[2] is None:
            logger.error("list_payments() returned None")
        if res[3] is None:
            logger.error("get_ln_info() returned None")

        tx = []
        for invoice in res[0]:
            i = GenericTx.from_invoice(invoice)
            if successful_only and i["status"] == "succeeded":
                tx.append(i)
                continue
            tx.append(i)

        for transaction in res[1]:
            t = GenericTx.from_onchain_tx(transaction, res[3].block_height)
            if successful_only and t.status == TxStatus.SUCCEEDED:
                tx.append(t)
                continue

            tx.append(t)

        for pay in res[2]:  # type: Payment
            comment = ""

            if pay.payment_request is not None and len(pay.payment_request) > 0:
                b11 = await self._decode_bolt11_cached(pay.payment_request)
                comment = b11.description

            p = GenericTx.from_payment(pay, comment)

            if successful_only and p["status"] == "succeeded":
                tx.append(p)
                continue

            tx.append(p)

        def sortKey(e: GenericTx):
            return e.time_stamp

        tx.sort(key=sortKey)

        if reversed:
            tx.reverse()

        l = len(tx)
        for invoice in range(l):
            tx[invoice].index = invoice

        if max_tx == 0:
            max_tx = l

        return tx[index_offset : index_offset + max_tx]

    @logger.catch(exclude=(HTTPException,))
    async def list_invoices(
        self,
        pending_only: bool,
        index_offset: int,
        num_max_invoices: int,
        reversed: bool,
    ):
        logger.trace(
            f"list_invoices({pending_only}, {index_offset}, {num_max_invoices}, {reversed})"
        )

        res = await self._send_request("listinvoices")

        if "error" in res:
            self._raise_internal_server_error("listing invoices", res)

        if not "result" in res or not "invoices" in res["result"]:
            logger.error(f"Got no error and no invoices key result: {res}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error while listing invoices: {res}",
            )

        res = res["result"]["invoices"]

        invoices = []
        for i in res:
            if not pending_only:
                invoices.append(Invoice.from_cln_json(i))
                continue

            if i["status"] == "unpaid":
                invoices.append(Invoice.from_cln_json(i))

        if reversed:
            invoices.reverse()

        if num_max_invoices == 0 or num_max_invoices is None:
            return invoices

        return invoices[index_offset : index_offset + num_max_invoices]

    @logger.catch(exclude=(HTTPException,))
    async def list_on_chain_tx(self) -> List[OnChainTransaction]:
        logger.trace("list_on_chain_tx()")
        info = await self.get_ln_info()  # for current block height
        res = await self._send_request("bkpr-listincome")
        if "error" in res:
            self._raise_internal_server_error("listing on-chain transactions", res)
        res = res["result"]

        txs = {}
        num_events = len(res["income_events"])
        for i in range(0, num_events):
            e = res["income_events"][i]
            if e["account"] != "wallet":
                continue

            if e["tag"] == "deposit" or e["tag"] == "withdrawal":
                tx = OnChainTransaction.from_cln_bkpr(e)
                txs[tx.tx_hash] = tx
            elif e["tag"] == "onchain_fee":
                if e["txid"] in txs:
                    txs[e["txid"]].total_fees = parse_cln_msat(e["debit_msat"]) / 1000

        # TODO: Improve this once CLN reports the block height in bkpr-listincome
        # see https://github.com/ElementsProject/lightning/issues/5694

        # now get the block height for each tx ...
        res = await self._send_request("bkpr-listaccountevents")
        if "error" in res:
            self._raise_internal_server_error("listing on-chain transactions", res)
        res = res["result"]

        num_events = len(res["events"])
        for i in range(0, num_events):
            e = res["events"][i]
            if e["account"] != "wallet" or e["type"] != "chain":
                continue

            txid = ""
            if e["tag"] == "deposit":
                txid = e["outpoint"].split(":")[0]
            elif e["tag"] == "withdrawal":
                txid = e["txid"]

            if len(txid) == 0:
                continue

            if txid in txs:
                txs[txid].block_height = e["blockheight"]
                txs[txid].num_confirmations = info.block_height - txs[txid].block_height

        return [txs[k] for k in txs.keys()]

    @logger.catch(exclude=(HTTPException,))
    async def list_payments(
        self,
        include_incomplete: bool,
        index_offset: int,
        max_payments: int,
        reversed: bool,
    ):
        logger.trace(
            f"list_payments({include_incomplete}, {index_offset}, {max_payments}, {reversed})"
        )

        res = await self._send_request("listpays")
        if "error" in res:
            self._raise_internal_server_error("listing payments", res)

        if not "result" in res or not "pays" in res["result"]:
            logger.error(f"Got no error and no pays key result: {res}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error while listing payments: {res}",
            )

        res = res["result"]["pays"]

        pays = []
        for p in res:
            if p["status"] == "complete":
                pays.append(Payment.from_cln_jrpc(p))
                continue

            if include_incomplete:
                b11_decoded = await self._decode_bolt11_cached(p["bolt11"])
                p["amount_msat"] = b11_decoded.num_msat
                pays.append(Payment.from_cln_jrpc(p))

        if reversed:
            pays.reverse()

        if max_payments == 0 or max_payments is None:
            return pays

        return pays[index_offset : index_offset + max_payments]

    @logger.catch(exclude=(HTTPException,))
    async def add_invoice(
        self,
        value_msat: int,
        memo: str = "",
        expiry: int = 3600,
        is_keysend: bool = False,
    ) -> Invoice:
        if value_msat < 0:
            raise ValueError("value_msat cannot be negative")

        pid = next_push_id()
        params = [value_msat, pid, memo, expiry]
        res = await self._send_request("invoice", params)

        if not "error" in res:
            res = res["result"]
            return Invoice(
                payment_request=res["bolt11"],
                memo=memo,
                value_msat=value_msat,
                expiry_date=res["expires_at"],
                add_index=pid,
                state=InvoiceState.OPEN,
            )

        m = res["error"]["message"]
        if "Duplicate label" in m:
            logger.error(m)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=m
            )

        logger.error(m)
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unknown error: {m}",
        )

    @logger.catch(exclude=(HTTPException,))
    async def decode_pay_request(self, pay_req: str) -> PaymentRequest:
        if pay_req in self._bolt11_cache:
            return self._bolt11_cache[pay_req]

        params = [pay_req]
        res = await self._send_request("decodepay", params)

        if not "error" in res:
            res = res["result"]
            req = PaymentRequest.from_cln_json(res)
            self._bolt11_cache[pay_req] = req
            return req

        m = res["error"]["message"]
        logger.error(m)

        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unknown error: {m}",
        )

    @logger.catch(exclude=(HTTPException,))
    async def get_fee_revenue(self) -> FeeRevenue:
        params = ["settled"]  # only list settled forwards
        res = await self._send_request("listforwards", params)

        if not "error" in res:
            res = res["result"]
            day, week, month, year, total = cln_classify_fee_revenue(res["forwards"])

            return FeeRevenue(day=day, week=week, month=month, year=year, total=total)

        m = res["error"]["message"]
        logger.error(m)

        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unknown error: {m}",
        )

    @logger.catch(exclude=(HTTPException,))
    async def new_address(self, input: NewAddressInput) -> str:
        res = await self._send_request("newaddr")

        if not "error" in res:
            res = res["result"]
            return res["bech32"]

        m = res["error"]["message"]
        logger.error(m)

        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unknown error: {m}",
        )

    @logger.catch(exclude=(HTTPException,))
    async def send_coins(self, input: SendCoinsInput) -> SendCoinsResponse:
        fee_rate = calc_fee_rate_str(input.sat_per_vbyte, input.target_conf)

        amt = "all" if input.send_all else input.amount

        params = [input.address, input.amount, fee_rate]
        res = await self._send_request("withdraw", params)

        if not "error" in res:
            res = res["result"]
            r = SendCoinsResponse.from_cln_json(res, input)
            await broadcast_sse_msg(SSE.LN_ONCHAIN_PAYMENT_STATUS, r.dict())

            return r

        if not "message" in res["error"]:
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Unknown error: {res}",
            )

        details = res["error"]["message"]
        logger.error(details)

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
        elif details and details.find("Could not afford ") > -1:
            raise HTTPException(status.HTTP_412_PRECONDITION_FAILED, detail=details)

        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unknown error: {details}",
        )

    @logger.catch(exclude=(HTTPException,))
    async def send_payment(
        self,
        pay_req: str,
        timeout_seconds: int,
        fee_limit_msat: int,
        amount_msat: Optional[int] = None,
    ) -> Payment:
        logger.trace("send_payment({pay_req}, {amount_msat}, {fee_limit_msat})")

        # pay bolt11 [amount_msat] [label] [riskfactor] [maxfeepercent]
        # [retry_for] [maxdelay] [exemptfee] [localinvreqid] [exclude]
        # [maxfee] [description]

        res = await self._send_request("listpays", {"bolt11": pay_req})
        if "error" in res:
            e = res["error"]["message"]
            if "Invalid invstring: unexpected prefix" in e:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    detail="invalid bech32 string",
                )

            self._raise_internal_server_error("checking if invoice was paid", res)

        pays = res["result"]["pays"]
        if len(pays) > 0 and pays[0]["status"] == "complete":
            raise HTTPException(
                status.HTTP_409_CONFLICT, detail="invoice is already paid"
            )

        params = {
            "bolt11": pay_req,
            "maxfee": fee_limit_msat,
            "retry_for": timeout_seconds,
            **({"msatoshi": amount_msat} if amount_msat is not None else {}),
        }
        res = await self._send_request("pay", params)

        if not "error" in res:
            res = res["result"]
            return Payment.from_cln_jrpc(res)

        message = res["error"]["message"]
        if "Ran out of routes to try after" in message:
            attempts = message.split("Ran out of routes to try after ")[1]
            attempts = attempts.split(" attempts")[0]
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Ran out of routes to try after {attempts} attempts.",
            )

        if "Invalid bolt11: " in message:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail="invalid bech32 string",
            )

        if "amount_msat parameter required" in message:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail="amount must be specified when paying a zero amount invoice",
            )

        if (
            "amount_msat parameter unnecessary" in message
            or "msatoshi parameter unnecessary" in message
        ):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail="amount must not be specified when paying a non-zero amount invoice",
            )

        logger.error(message)
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unknown error: {message}",
        )

    @logger.catch(exclude=(HTTPException,))
    async def get_ln_info(self) -> LnInfo:
        res = await self._send_request("getinfo")
        if "error" in res:
            self._raise_internal_server_error("getting info", res)

        return LnInfo.from_cln_jrpc(self.get_implementation_name(), res["result"])

    @logger.catch(exclude=(HTTPException,))
    async def unlock_wallet(self, password: str) -> bool:
        logger.trace(f"unlock_wallet(password=wedontlogpasswords)")

        # Core Lightning doesn't lock wallets,
        # so we don't need to do anything here
        return True

    @logger.catch(exclude=(HTTPException,))
    async def listen_invoices(self) -> AsyncGenerator[Invoice, None]:
        logger.trace("listen_invoices()")

        while True:
            try:
                data = await self._invoice_queue.get()
                data = json.loads(data)["result"]
                i = Invoice.from_cln_json(data)
                self.lastpay_index = i.settle_index
                await self._refresh_invoice_sub()
                yield i
            except Exception as e:
                logger.error(f"Got an invoice but could not parse the data: {e}")
                # if we have an error we are in an unknown state
                # so we fetch the latest invoice index and start from there
                await self._refresh_invoice_sub(True)

    @logger.catch(exclude=(HTTPException,))
    async def listen_forward_events(self) -> ForwardSuccessEvent:
        logger.trace("listen_forward_events()")

        # CLN has no subscription to forwarded events.
        # We must poll instead.

        interval = config("gather_ln_info_interval", default=2, cast=float)

        # make sure we know how many forwards we have
        # we need to calculate the difference between each iteration
        res = await self._send_request("listforwards", {"status": "settled"})

        if "error" in res:
            self._raise_internal_server_error("getting forwards", res)

        res = res["result"]
        num_fwd_last_poll = len(res["forwards"])
        while True:
            res = await self._send_request("listforwards", {"status": "settled"})
            res = res["result"]
            if len(res["forwards"]) > num_fwd_last_poll:
                fwds = res["forwards"][num_fwd_last_poll:]

                for fwd in fwds:
                    yield ForwardSuccessEvent.from_cln_json(fwd)

                num_fwd_last_poll = len(res["forwards"])
            await asyncio.sleep(interval - 0.1)

    @logger.catch(exclude=(HTTPException,))
    async def channel_open(
        self, local_funding_amount: int, node_URI: str, target_confs: int
    ) -> str:
        logger.trace(
            f"channel_open(local_funding_amount={local_funding_amount}, node_URI={node_URI}, target_confs={target_confs})"
        )
        # fundchannel id amount [feerate] [announce] [minconf] [utxos] [push_msat] [close_to] [request_amt] [compact_lease] [reserve]

        await self.connect_peer(node_URI)
        fee_rate = calc_fee_rate_str(None, target_confs)
        pub = node_URI.split("@")[0]
        params = {"id": pub, "amount": local_funding_amount, "feerate": fee_rate}
        res = await self._send_request("fundchannel", params)

        if "error" in res:
            self._handle_open_channel_error(res["error"])
        res = res["result"]

        if "txid" in res and "channel_id" in res:
            return res["txid"]

    def _handle_open_channel_error(self, error):
        logger.trace(f"_handle_open_channel_error({error})")
        message = error["message"]

        if "amount: should be a satoshi amount" in message:
            logger.error(message)
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail="The amount is not a valid satoshi amount.",
            )

        if "Unknown peer" in message:
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="We where able to connect to the peer but CLN can't find it when opening a channel.",
            )

        if "Owning subdaemon openingd died" in message:
            # https://github.com/ElementsProject/lightning/issues/2798#issuecomment-511205719
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail="Likely the peer didn't like our channel opening proposal and disconnected from us.",
            )

        if (
            "Number of pending channels exceed maximum" in message
            or "exceeds maximum chan size of 10 BTC" in message
            or "Could not afford" in message
        ):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=message)

        logger.error(message)
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unknown error: {message}",
        )

    @logger.catch(exclude=(HTTPException,))
    async def peer_resolve_alias(self, node_pub: str) -> str:
        logger.trace(f"peer_resolve_alias(node_pub={node_pub})")

        if node_pub == "":
            raise ValueError("node_pub is empty")

        res = await self._send_request("listnodes", [node_pub])

        if "error" in res:
            err_msg = res["error"]["message"]
            logger.error(f"Error resolving alias for node_pub={node_pub}\n{err_msg}")
            return ""

        nodes = res["result"]["nodes"]
        if len(nodes) == 0:
            return ""

        return str(nodes[0]["alias"])

    @logger.catch(exclude=(HTTPException,))
    async def channel_list(self) -> List[Channel]:
        logger.trace("channel_list()")

        res = await self._send_request("listfunds")
        if "error" in res:
            self._raise_internal_server_error("listing channels", res)

        res = res["result"]

        peer_ids = [c["peer_id"] for c in res["channels"]]
        peers = await asyncio.gather(*[self.peer_resolve_alias(p) for p in peer_ids])
        channels = [Channel.from_cln_jrpc(c, p) for c, p in zip(res["channels"], peers)]

        return channels

    @logger.catch(exclude=(HTTPException,))
    async def channel_close(self, channel_id: int, force_close: bool) -> str:
        # https://lightning.readthedocs.io/lightning-close.7.html
        logger.trace(
            f"channel_close(channel_id={channel_id}, force_close={force_close})"
        )

        # on CLN we wait for 2 minutes to negotiate a channel close
        # if peer doesn't respond we force close
        params = {
            "id": channel_id,
            "unilateraltimeout": 120 if force_close else 0,
        }
        res = await self._send_request("close", params)
        if "error" in res:
            message = res["error"]["message"]
            if (
                "Short channel ID not active:" in message
                or "Short channel ID not found" in message
            ):
                logger.warning(f"Error while closing channel {channel_id}: {message}")
                raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=message)

            self._raise_internal_server_error("closing channel", res)

        res = res["result"]

        # “mutual”, “unilateral”, “unopened”
        t = res["type"]
        if t == "mutual" or t == "unilateral":
            return res["txid"]
        elif t == "unopened":
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, detail="Channel is not open yet."
            )

        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=f"CLN returned unknown close type: {t}",
        )

    async def connect_peer(self, uri: str) -> bool:
        logger.trace(f"connect_peer(node_URI={uri})")

        res = await self._send_request("connect", [uri])

        if not "error" in res:
            return True

        message = res["error"]["message"]

        if "All addresses failed" in message:
            message = details.split('message: "')[1]

            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail=message,
            )

        if "no address known for peer" in message:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail="Connection establishment: No address known for peer",
            )

        if "Connection timed out" in message:
            raise HTTPException(
                status.HTTP_504_GATEWAY_TIMEOUT,
                detail="Connection establishment: Connection timed out.",
            )

        if "Connection refused" in message:
            raise HTTPException(
                status.HTTP_504_GATEWAY_TIMEOUT,
                detail="Connection establishment: Connection refused.",
            )

        logger.exception(message)

        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail=message)

    async def _read_loop(self):
        logger.trace("_read_loop()")

        while not self._writer.is_closing():
            try:
                data = await self._reader.readline()
                data = data.decode("utf-8")

                if data == "\n":
                    continue

                if data:
                    self._handle_response(data)
            except (ValueError, asyncio.exceptions.LimitOverrunError) as e:
                logger.exception(e)
                continue

    def _handle_response(self, data):
        logger.trace(f"_handle_response(data={data})")

        response = json.loads(data)
        id = response["id"]

        if id == _WAIT_ANY_INVOICE_ID:
            return self._invoice_queue.put_nowait(data)

        logger.trace(f"Got response: {response} for id {self._current_id}")
        future = self._futures[id]
        future.set_result(response)

        del self._futures[id]

    def _send_request(self, method: str, params: Union[Dict, List, None] = {}):
        self._current_id += 1
        data = self._build_request_data(method, self._current_id, params)
        logger.trace(f"Sending request: {data} with id {self._current_id}")
        self._writer.write(data.encode("utf-8"))
        future = self._loop.create_future()
        self._futures[self._current_id] = future

        return future

    def _build_request_data(self, method: str, id: int, params) -> bytes:
        return json.dumps(
            {
                "jsonrpc": "2.0",
                "id": id,
                "method": method,
                "params": params,
            }
        )

    def _raise_internal_server_error(self, action, res):
        err = res["error"]
        logger.error(f"Error while {action}: {err}")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while {action}: {err}",
        )

    async def _refresh_invoice_sub(self, refresh_pay_index=False):
        if refresh_pay_index:
            logger.info("Refreshing pay_index")

            invoices = await self.list_invoices(
                pending_only=False,
                index_offset=0,
                num_max_invoices=9999999999999,
                reversed=True,
            )

            if invoices is not None:
                for i in invoices:  # type Invoice
                    if i.state is not InvoiceState.SETTLED:
                        continue

                    if i.settle_index != None and i.settle_index < self.lastpay_index:
                        break

                    self.lastpay_index = i.settle_index

        data = self._build_request_data(
            "waitanyinvoice",
            _WAIT_ANY_INVOICE_ID,
            {"lastpay_index": self.lastpay_index},
        )

        logger.trace(f"Sending waitanyinvoice request: {data}")
        self._writer.write(data.encode("utf-8"))

    async def _decode_bolt11_cached(self, bolt11: str) -> PaymentRequest:
        if bolt11 in self._bolt11_cache:
            return self._bolt11_cache[bolt11]

        pr = await self.decode_pay_request(bolt11)
        self._bolt11_cache[bolt11] = pr
        return pr
