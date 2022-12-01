import asyncio
import json
import logging
import time
from typing import AsyncGenerator, List, Optional

import grpc
from decouple import config
from fastapi.exceptions import HTTPException
from starlette import status

import app.lightning.impl.protos.cln.node_pb2 as ln
import app.lightning.impl.protos.cln.node_pb2_grpc as clnrpc
import app.lightning.impl.protos.cln.primitives_pb2 as lnp
from app.api.utils import SSE, broadcast_sse_msg, config_get_hex_str, next_push_id
from app.bitcoind.utils import bitcoin_rpc_async
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
from app.lightning.utils import parse_cln_msat


async def _make_local_call(cmd: str):
    # FIXME: this is a hack because some of the commands are not exposed
    # in the CLN grpc interface yet.

    testnet = config("network") == "testnet"
    cmd = f"lightning-cli -k {'--testnet ' if testnet else ''}{cmd}"
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()

    if stderr != None and stderr != b"":
        err = stderr.decode()
        if "lightning-cli: Connecting to 'lightning-rpc': Permission denied" in err:
            logging.critical(
                "CLN_GRPC: Unable to connect to lightning-cli: Permission denied. Is the lightning-rpc socket readable for the API user?"
            )

            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="CLN_GRPC: Unable to connect to lightning-cli: Permission denied.",
            )

        if "lightning-cli: Moving into" in err and "No such file or directory" in err:
            logging.critical(
                "CLN_GRPC: Unable to connect to lightning-cli: No such file or directory. Is the lightning-rpc socket available to the API user?"
            )

            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="CLN_GRPC: Unable to connect to lightning-cli: API Can't access lightning-cli.",
            )

        logging.critical(f"CLN_GRPC: Unable to connect to lightning-cli: {err}")

        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="CLN_GRPC: Unable to connect to lightning-cli: Unknown error. Please consult the logs.",
        )
    return stdout, stderr


class LnNodeCLNgRPC(LightningNodeBase):
    _initialized = False
    _channel = None
    _cln_stub: clnrpc.NodeStub = None
    # Decoding the payment request take a long time,
    # hence we build a simple cache here.
    _memo_cache = {}
    _block_cache = {}

    def get_implementation_name(self) -> str:
        return "CLN_GRPC"

    async def initialize(self) -> AsyncGenerator[InitLnRepoUpdate, None]:
        logging.debug("CLN_GRPC: Unable to connect to CLN daemon, waiting...")
        if self._initialized:
            logging.warning(
                "CLN_GRPC: Connection already initialized. This function must not be called twice."
            )
            yield InitLnRepoUpdate(state=LnInitState.DONE)

        cln_grpc_cert = bytes.fromhex(
            config_get_hex_str(config("cln_grpc_cert"), name="cln_grpc_cert")
        )
        cln_grpc_key = bytes.fromhex(
            config_get_hex_str(config("cln_grpc_key"), name="cln_grpc_key")
        )
        cln_grpc_ca = bytes.fromhex(
            config_get_hex_str(config("cln_grpc_ca"), name="cln_grpc_ca")
        )
        cln_grpc_url = config("cln_grpc_ip") + ":" + config("cln_grpc_port")
        self.creds = grpc.ssl_channel_credentials(
            root_certificates=cln_grpc_ca,
            private_key=cln_grpc_key,
            certificate_chain=cln_grpc_cert,
        )

        opts = (("grpc.ssl_target_name_override", "cln"),)

        while not self._initialized:
            try:
                if self._channel is None:
                    self._channel = grpc.aio.secure_channel(
                        cln_grpc_url, self.creds, options=opts
                    )
                    self._cln_stub = clnrpc.NodeStub(self._channel)

                await self._cln_stub.Getinfo(ln.GetinfoRequest())
                self._initialized = True
                yield InitLnRepoUpdate(state=LnInitState.DONE)
            except grpc.aio._call.AioRpcError as error:
                details = error.details()
                logging.debug(f"CLN_GRPC: Waiting for CLN daemon... Details {details}")

                if "failed to connect to all addresses" in details:
                    yield InitLnRepoUpdate(
                        state=LnInitState.OFFLINE,
                        msg="Unable to connect to CLN daemon, waiting...",
                    )

                    await self._channel.close()
                    self._channel = self.cln_stub = None
                else:
                    logging.error(f"CLN_GRPC: Unknown error: {details}")
                    raise

                await asyncio.sleep(2)

        logging.info("CLN_GRPC: Initialization complete.")

    async def get_wallet_balance(self) -> WalletBalance:
        logging.debug("CLN_GRPC: get_wallet_balance() ")

        req = ln.ListfundsRequest()
        res = await self._cln_stub.ListFunds(req)
        onchain_confirmed = onchain_unconfirmed = onchain_total = 0

        for o in res.outputs:
            sat = o.amount_msat.msat / 1000
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

    async def _get_block_time(self, block_height: int) -> tuple:
        logging.debug(f"CLN_GRPC: _get_block_time(block_height={block_height}) ")

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

    async def list_all_tx(
        self, successful_only: bool, index_offset: int, max_tx: int, reversed: bool
    ) -> List[GenericTx]:
        logging.debug(
            f"CLN_GRPC: list_all_tx(successful_only={successful_only}, index_offset={index_offset}, max_tx={max_tx}, reversed={reversed})"
        )

        list_invoice_req = ln.ListinvoicesRequest()
        list_payments_req = ln.ListpaysRequest()

        try:
            res = await asyncio.gather(
                *[
                    self._cln_stub.ListInvoices(list_invoice_req),
                    self.list_on_chain_tx(),
                    self._cln_stub.ListPays(list_payments_req),
                    self.get_ln_info(),
                ]
            )
            tx = []
            for invoice in res[0].invoices:
                i = GenericTx.from_cln_grpc_invoice(invoice)
                if successful_only and i.status == TxStatus.SUCCEEDED:
                    tx.append(i)
                    continue
                tx.append(i)

            for transaction in res[1]:
                t = GenericTx.from_cln_grpc_onchain_tx(transaction, res[3].block_height)
                if successful_only and t.status == TxStatus.SUCCEEDED:
                    tx.append(t)
                    continue

                tx.append(t)

            for pay in res[2].pays:
                comment = ""

                if pay.bolt11 is not None and len(pay.bolt11) > 0:
                    if pay.bolt11 in self._memo_cache:
                        comment = self._memo_cache[pay.bolt11]
                    else:
                        pr = await self.decode_pay_request(pay.bolt11)
                        comment = pr.description
                        self._memo_cache[pay.bolt11] = pr.description

                p = GenericTx.from_cln_grpc_payment(pay, comment)

                if successful_only and p.status == TxStatus.SUCCEEDED:
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
        except grpc.aio._call.AioRpcError as error:
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR, detail=error.details()
            )

    async def list_invoices(
        self,
        pending_only: bool,
        index_offset: int,
        num_max_invoices: int,
        reversed: bool,
    ) -> List[Invoice]:
        logging.debug("CLN_GRPC: list_invoices() ")

        req = ln.ListinvoicesRequest()
        res = await self._cln_stub.ListInvoices(req)

        tx = []
        for i in res.invoices:
            if pending_only:
                if i.status == 0:
                    tx.append(Invoice.from_cln_grpc(i))
            else:
                tx.append(Invoice.from_cln_grpc(i))

        if reversed:
            tx.reverse()

        if num_max_invoices == 0 or num_max_invoices is None:
            return tx

        return tx[index_offset : index_offset + num_max_invoices]

    async def list_on_chain_tx(self) -> List[OnChainTransaction]:
        logging.debug("CLN_GRPC: list_on_chain_tx() ")
        info = await self.get_ln_info()  # for current block height
        res = await _make_local_call("bkpr-listincome")

        if not res:
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unknown CLN error while listing account income events",
            )

        if len(res) == 0:
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="No response from CLN while trying to list account income events",
            )

        decoded = res[0].decode()
        js = json.loads(decoded)

        txs = {}
        num_events = len(js["income_events"])
        for i in range(0, num_events):
            e = js["income_events"][i]
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
        res = await _make_local_call("bkpr-listaccountevents")
        if not res:
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unknown CLN error while listing account events",
            )

        if len(res) == 0:
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="No response from CLN while trying to list account events",
            )

        decoded = res[0].decode()
        js = json.loads(decoded)
        num_events = len(js["events"])
        for i in range(0, num_events):
            e = js["events"][i]
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

    async def list_payments(
        self,
        include_incomplete: bool,
        index_offset: int,
        max_payments: int,
        reversed: bool,
    ):
        logging.debug(
            f"CLN_GRPC: list_payments(include_incomplete={include_incomplete}, index_offset{index_offset}, max_payments={max_payments}, reversed={reversed})"
        )

        req = ln.ListpaysRequest()
        res = await self._cln_stub.ListPays(req)

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

        if max_payments == 0 or max_payments is None:
            return pays

        return pays[index_offset : index_offset + max_payments]

    async def add_invoice(
        self,
        value_msat: int,
        memo: str = "",
        expiry: int = 3600,
        is_keysend: bool = False,
    ) -> Invoice:
        logging.debug(
            f"CLN_GRPC: add_invoice(value_msat={value_msat}, memo={memo}, expiry={expiry}, is_keysend={is_keysend})"
        )

        if value_msat < 0:
            raise ValueError("value_msat cannot be negative")

        msat = None
        if value_msat == 0:
            msat = lnp.AmountOrAny(any=True)
        elif value_msat > 0:
            msat = lnp.AmountOrAny(amount=lnp.Amount(msat=value_msat))

        id = next_push_id()
        req = ln.InvoiceRequest(
            amount_msat=msat,
            description=memo,
            label=id,
            expiry=expiry,
        )

        try:
            res = await self._cln_stub.Invoice(req)
            return Invoice(
                payment_request=res.bolt11,
                memo=memo,
                value_msat=value_msat,
                expiry_date=res.expires_at,
                add_index=id,
                state=InvoiceState.OPEN,
            )
        except grpc.aio._call.AioRpcError as error:
            details = error.details()

            try:
                self._handle_base_cln_error(error)
            except HTTPException:
                raise

            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Unknown CLN error while adding invoice: {details}",
            )

    async def decode_pay_request(self, pay_req: str) -> PaymentRequest:
        logging.debug(f"CLN_GRPC: decode_pay_request(pay_req={pay_req})")

        res = await _make_local_call(f"decodepay bolt11={pay_req}")

        if not res:
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unknown CLN error decoding pay request",
            )

        if len(res) == 0:
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="No response from CLN decoding pay request",
            )

        decoded = res[0].decode()

        if "Invalid bolt11: Bad bech32 string" in decoded:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, detail="Invalid bolt11: Bad bech32 string"
            )

        return PaymentRequest.from_cln_json(json.loads(decoded))

    async def get_fee_revenue(self) -> FeeRevenue:
        logging.debug(f"CLN_GRPC: get_fee_revenue()")

        # status 1 == "settled"
        req = ln.ListforwardsRequest(status=1)
        res = await self._cln_stub.ListForwards(req)

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

    async def new_address(self, input: NewAddressInput) -> str:
        logging.debug(f"CLN_GRPC: new_address(input={input})")

        if input.type == OnchainAddressType.P2WKH:
            req = ln.NewaddrRequest(addresstype=2)
            res = await self._cln_stub.NewAddr(req)
            return res.bech32

        req = ln.NewaddrRequest(addresstype=1)
        res = await self._cln_stub.NewAddr(req)
        return res.p2sh_segwit

    async def send_coins(self, input: SendCoinsInput) -> SendCoinsResponse:
        logging.debug(f"CLN_GRPC: send_coins(input={input})")

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
            funds = await self._cln_stub.ListFunds(ln.ListfundsRequest())
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

            if not input.send_all and max_amt <= input.amount:
                raise HTTPException(
                    status.HTTP_412_PRECONDITION_FAILED,
                    detail=f"Could not afford {input.amount}sat. Not enough funds available",
                )

            req = ln.WithdrawRequest(
                destination=input.address,
                satoshi=lnp.AmountOrAll(
                    amount=lnp.Amount(msat=input.amount),
                    all=input.send_all,
                ),
                minconf=input.min_confs,
                feerate=fee_rate,
                utxos=utxos,
            )
            response = await self._cln_stub.Withdraw(req)
            r = SendCoinsResponse.from_cln_grpc(response, input)
            await broadcast_sse_msg(SSE.LN_ONCHAIN_PAYMENT_STATUS, r.dict())
            return r
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
                raise HTTPException(
                    status.HTTP_500_INTERNAL_SERVER_ERROR, detail=details
                )

    async def send_payment(
        self,
        pay_req: str,
        timeout_seconds: int,
        fee_limit_msat: int,
        amount_msat: Optional[int] = None,
    ) -> Payment:
        logging.debug(
            f"CLN_GRPC: send_payment(pay_req={pay_req}, timeout_seconds={timeout_seconds}, fee_limit_msat={fee_limit_msat}, amount_msat={amount_msat})"
        )

        amt = lnp.Amount(msat=amount_msat) if amount_msat != None else None
        fee_limit = lnp.Amount(msat=fee_limit_msat)
        req = ln.PayRequest(
            bolt11=pay_req,
            amount_msat=amt,
            maxfee=fee_limit,
            retry_for=timeout_seconds,
        )

        try:
            res = await self._cln_stub.Pay(req)
        except grpc.aio._call.AioRpcError as error:
            details = error.details()

            if "Ran out of routes to try after" in details:
                attempts = details.split("Ran out of routes to try after ")[1]
                attempts = attempts.split(" attempts")[0]
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Ran out of routes to try after {attempts} attempts.",
                )

            if "Invalid bolt11: " in details:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    detail="invalid bech32 string",
                )

            if "amount_msat parameter required" in details:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    detail="amount must be specified when paying a zero amount invoice",
                )

            if "amount_msat parameter unnecessary" in details:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    detail="amount must not be specified when paying a non-zero amount invoice",
                )

            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail=details)

        return Payment.from_cln_grpc(res)

    async def get_ln_info(self) -> LnInfo:
        logging.debug(f"CLN_GRPC: get_ln_info()")

        req = ln.GetinfoRequest()
        try:
            res = await self._cln_stub.Getinfo(req)
            return LnInfo.from_cln_grpc(self.get_implementation_name(), res)
        except grpc.aio._call.AioRpcError as error:
            details = error.details()

            try:
                self._handle_base_cln_error(error)
            except HTTPException:
                raise

            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"CLN_GRPC: Unknown CLN error while getting lightning info: {details}",
            )

    async def unlock_wallet(self, password: str) -> bool:
        logging.debug(f"CLN_GRPC: unlock_wallet(password=wedontlogpasswords)")

        # Core Lightning doesn't lock wallets,
        # so we don't need to do anything here
        return True

    async def listen_invoices(self) -> AsyncGenerator[Invoice, None]:
        logging.debug(f"CLN_GRPC: listen_invoices()")

        lastpay_index = 0
        invoices = await self.list_invoices(
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
            i = await self._cln_stub.WaitAnyInvoice(req)
            i = Invoice.from_cln_grpc(i)
            lastpay_index = i.settle_index
            yield i

    async def listen_forward_events(self) -> ForwardSuccessEvent:
        logging.debug(f"CLN_GRPC: listen_forward_events()")

        # CLN has no subscription to forwarded events.
        # We must poll instead.

        interval = config("gather_ln_info_interval", default=2, cast=float)

        # make sure we know how many forwards we have
        # we need to calculate the difference between each iteration
        # status=1 == "settled"
        req = ln.ListforwardsRequest(status=1)
        res = await self._cln_stub.ListForwards(req)
        num_fwd_last_poll = len(res.forwards)
        while True:
            res = await self._cln_stub.ListForwards(req)
            if len(res.forwards) > num_fwd_last_poll:
                fwds = res.forwards[num_fwd_last_poll:]
                for fwd in fwds:
                    yield ForwardSuccessEvent.from_cln_grpc(fwd)

                num_fwd_last_poll = len(res.forwards)
            await asyncio.sleep(interval - 0.1)

    async def connect_peer(self, node_URI: str) -> bool:
        logging.debug(f"CLN_GRPC: connect_peer(node_URI={node_URI})")

        try:
            id = node_URI.split("@")[0]
            stdout, stderr = await _make_local_call(f"connect id={node_URI}")
            if stdout:
                if id in stdout.decode():
                    return True
                if "Connection timed out" in stdout.decode():
                    raise HTTPException(
                        status.HTTP_504_GATEWAY_TIMEOUT,
                        detail="Connection establishment: Connection timed out.",
                    )
                if "Connection refused" in stdout.decode():
                    raise HTTPException(
                        status.HTTP_504_GATEWAY_TIMEOUT,
                        detail="Connection establishment: Connection refused.",
                    )
            if stderr:
                logging.error(f"CLN_GRPC: {stderr.decode()}")

            return False

        except grpc.aio._call.AioRpcError as error:
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR, detail=error.details()
            )

    async def peer_resolve_alias(self, node_pub: str) -> str:
        logging.debug(f"CLN_GRPC: peer_resolve_alias(node_pub={node_pub})")

        try:
            request = ln.ListnodesRequest(id=node_pub)
            response = await self._cln_stub.ListNodes(request)

            if len(response.nodes) == 0:
                return ""

            return str(response.nodes[0].alias)

        except grpc.aio._call.AioRpcError as error:
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR, detail=error.details()
            )

    async def channel_open(
        self, local_funding_amount: int, node_URI: str, target_confs: int
    ) -> str:
        logging.debug(
            f"CLN_GRPC: channel_open(local_funding_amount={local_funding_amount}, node_URI={node_URI}, target_confs={target_confs})"
        )

        fee_rate = None
        if target_confs == 1:
            fee_rate = "urgent"
        elif target_confs >= 2 and target_confs <= 9:
            fee_rate = "normal"
        elif target_confs >= 10:
            fee_rate = "slow"

        try:
            res = await self.connect_peer(node_URI)
            if not res:
                raise HTTPException(
                    status.HTTP_408_REQUEST_TIMEOUT,
                    detail="Unknown error while trying to connect to peer",
                )

            cmd = f"fundchannel id={node_URI} amount={local_funding_amount} feerate={fee_rate}"
            stdout, stderr = await _make_local_call(cmd)
            if stdout:
                o = stdout.decode()
                j = json.loads(o)
                if "txid" in o and "channel_id" in o:
                    return j["txid"]
                if "Unknown peer" in o:
                    raise HTTPException(
                        status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="We where able to connect to the peer but CLN can't find it when opening a channel.",
                    )
                if "Owning subdaemon openingd died" in o:
                    # https://github.com/ElementsProject/lightning/issues/2798#issuecomment-511205719
                    raise HTTPException(
                        status.HTTP_400_BAD_REQUEST,
                        detail="Likely the peer didn't like our channel opening proposal and disconnected from us.",
                    )
                if "Could not afford " in o:
                    raise HTTPException(
                        status.HTTP_400_BAD_REQUEST, detail=j["message"]
                    )
                if "Number of pending channels exceed maximum" in o:
                    raise HTTPException(
                        status.HTTP_400_BAD_REQUEST, detail=j["message"]
                    )

                raise HTTPException(
                    status.HTTP_500_INTERNAL_SERVER_ERROR, detail=j["message"]
                )
            if stderr:
                logging.error(f"CLN_GRPC: {stderr.decode()}")

            return False
        except grpc.aio._call.AioRpcError as error:
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR, detail=error.details()
            )

    async def channel_list(self) -> List[Channel]:
        logging.debug(f"CLN_GRPC: channel_list()")

        try:
            res = await self._cln_stub.ListFunds(ln.ListfundsRequest())
            peer_ids = [c.peer_id for c in res.channels]
            peer_res = await asyncio.gather(
                *[self.peer_resolve_alias(p) for p in peer_ids]
            )
            channels = [
                Channel.from_cln_grpc(c, p) for c, p in zip(res.channels, peer_res)
            ]
            return channels
        except grpc.aio._call.AioRpcError as error:
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR, detail=error.details()
            )

    async def channel_close(self, channel_id: int, force_close: bool) -> str:
        logging.debug(
            f"CLN_GRPC: channel_close(channel_id={channel_id}, force_close={force_close})"
        )

        try:
            # on CLN we wait for 2 minutes to negotiate a channel close
            # if peer doesn't respond we force close
            wait_time_before_unilateral_close = 120 if force_close else 0
            req = ln.CloseRequest(
                id=channel_id,
                unilateraltimeout=wait_time_before_unilateral_close,
                feerange=[lnp.Feerate(slow=True), lnp.Feerate(urgent=True)],
            )
            res = await self._cln_stub.Close(req)

            # “mutual”, “unilateral”, “unopened”
            t = res.item_type
            if t == 0 or t == 1:  # mutual, unilateral
                return res.txid.hex()
            elif t == 2:  # unopened
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST, detail="Channel is not open yet."
                )

            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail=f"CLN returned unknown close type: {t}",
            )
        except grpc.aio._call.AioRpcError as error:
            if "Channel is in state AWAITING_UNILATERAL" in error.details():
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    detail="Channel is awaiting an unilateral close.",
                )

            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR, detail=error.details()
            )

    def _handle_base_cln_error(self, error: grpc.aio._call.AioRpcError) -> None:
        # This method handles all errors common to all CLN calls
        details = error.details()

        if details and details.find("Received RST_STREAM with error code 8") > -1:
            logging.error(details)
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="CLN is responding with an error. Please check the logs.",
            )
