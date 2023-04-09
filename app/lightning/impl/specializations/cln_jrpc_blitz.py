import asyncio
from typing import AsyncGenerator, List, Optional

from decouple import config
from fastapi.exceptions import HTTPException
from loguru import logger
from starlette import status

from app.api.utils import call_script2, redis_get
from app.lightning.impl.cln_jrpc import LnNodeCLNjRPC
from app.lightning.impl.specializations.blitz_common import blitz_cln_unlock
from app.lightning.models import (
    Channel,
    FeeRevenue,
    ForwardSuccessEvent,
    GenericTx,
    InitLnRepoUpdate,
    Invoice,
    LnInfo,
    LnInitState,
    NewAddressInput,
    OnChainTransaction,
    Payment,
    PaymentRequest,
    SendCoinsInput,
    SendCoinsResponse,
    WalletBalance,
)


class LnNodeCLNjRPCBlitz(LnNodeCLNjRPC):
    # RaspiBlitz implements a lock function on top of CLN, so we need to implement this on Blitz only.

    _unlocked = False

    _NETWORK = config("network", default="mainnet")

    def get_implementation_name(self) -> str:
        return "CLN_JRPC_BLITZ"

    @logger.catch(exclude=(HTTPException,))
    async def initialize(self) -> AsyncGenerator[InitLnRepoUpdate, None]:
        logger.debug("RaspiBlitz is locked, waiting for unlock...")

        while not self._unlocked:
            key = f"ln_cl_{self._NETWORK}_locked"
            res = await redis_get(key)
            if res == "0":
                logger.debug(
                    f"Redis key {key} indicates that RaspiBlitz has been unlocked"
                )

                self._unlocked = True
                yield InitLnRepoUpdate(state=LnInitState.BOOTSTRAPPING_AFTER_UNLOCK)
                break
            elif res == "1":
                logger.debug(
                    f"Redis key {key} indicates that RaspiBlitz is still locked"
                )

                yield InitLnRepoUpdate(
                    state=LnInitState.LOCKED,
                    msg="Wallet locked, unlock it to enable full RPC access",
                )
            else:
                logger.error(f"Redis key {key} returns an unexpected value: {res}")
                raise HTTPException(
                    status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Unknown lock status: {res}",
                )

            await asyncio.sleep(2)

        async for u in super().initialize():
            yield u
            if u.state == LnInitState.DONE:
                break

        logger.info("Initialization complete.")

    async def get_wallet_balance(self) -> WalletBalance:
        self._check_if_locked()
        return await super().get_wallet_balance()

    async def list_all_tx(
        self, successful_only: bool, index_offset: int, max_tx: int, reversed: bool
    ) -> List[GenericTx]:
        self._check_if_locked()
        return await super().list_all_tx(
            successful_only, index_offset, max_tx, reversed
        )

    async def list_invoices(
        self,
        pending_only: bool,
        index_offset: int,
        num_max_invoices: int,
        reversed: bool,
    ):
        self._check_if_locked()
        return await super().list_invoices(
            pending_only, index_offset, num_max_invoices, reversed
        )

    async def list_on_chain_tx(self) -> List[OnChainTransaction]:
        self._check_if_locked()
        return await super().list_on_chain_tx()

    async def list_payments(
        self,
        include_incomplete: bool,
        index_offset: int,
        max_payments: int,
        reversed: bool,
    ):
        self._check_if_locked()
        return await super().list_payments(
            include_incomplete, index_offset, max_payments, reversed
        )

    async def add_invoice(
        self,
        value_msat: int,
        memo: str = "",
        expiry: int = 3600,
        is_keysend: bool = False,
    ) -> Invoice:
        self._check_if_locked()
        return await super().add_invoice(value_msat, memo, expiry, is_keysend)

    async def decode_pay_request(self, pay_req: str) -> PaymentRequest:
        self._check_if_locked()
        return await super().decode_pay_request(pay_req)

    async def get_fee_revenue(self) -> FeeRevenue:
        self._check_if_locked()
        return await super().get_fee_revenue()

    async def new_address(self, input: NewAddressInput) -> str:
        self._check_if_locked()
        return await super().new_address(input)

    async def send_coins(self, input: SendCoinsInput) -> SendCoinsResponse:
        self._check_if_locked()
        return await super().send_coins(input)

    async def send_payment(
        self,
        pay_req: str,
        timeout_seconds: int,
        fee_limit_msat: int,
        amount_msat: Optional[int] = None,
    ) -> Payment:
        self._check_if_locked()
        return await super().send_payment(
            pay_req, timeout_seconds, fee_limit_msat, amount_msat
        )

    async def get_ln_info(self) -> LnInfo:
        self._check_if_locked()
        return await super().get_ln_info()

    @logger.catch(exclude=(HTTPException,))
    async def unlock_wallet(self, password: str) -> bool:
        # RaspiBlitz implements a wallet lock functionality on top of CLN,
        # so we need to implement this on Blitz only
        _unlocked = await blitz_cln_unlock(self._NETWORK, password)

        return _unlocked

    async def listen_invoices(self) -> AsyncGenerator[Invoice, None]:
        self._check_if_locked()
        async for i in super().listen_invoices():
            yield i

    async def listen_forward_events(self) -> ForwardSuccessEvent:
        self._check_if_locked()
        async for i in super().listen_forward_events():
            yield i

    async def channel_open(
        self,
        local_funding_amount: int,
        node_URI: str,
        target_confs: int,
        push_amount_sat: int,
    ) -> str:
        self._check_if_locked()
        return await super().channel_open(
            local_funding_amount,
            node_URI,
            target_confs,
            push_amount_sat,
        )

    async def peer_resolve_alias(self, node_pub: str) -> str:
        self._check_if_locked()
        return await super().peer_resolve_alias(node_pub)

    async def channel_list(self) -> List[Channel]:
        self._check_if_locked()
        return await super().channel_list()

    async def channel_close(self, channel_id: int, force_close: bool) -> str:
        self._check_if_locked()
        return await super().channel_close(channel_id, force_close)

    @logger.catch(exclude=(HTTPException,))
    def _check_if_locked(self):
        logger.debug(f"_check_if_locked()")

        if not self._unlocked:
            raise HTTPException(
                status.HTTP_423_LOCKED,
                detail="Wallet is locked. Unlock via /lightning/unlock-wallet",
            )
