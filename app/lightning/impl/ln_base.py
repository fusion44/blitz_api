from abc import abstractmethod
from typing import AsyncGenerator, List, Optional

from app.lightning.models import (
    Channel,
    FeeRevenue,
    ForwardSuccessEvent,
    GenericTx,
    InitLnRepoUpdate,
    Invoice,
    LnInfo,
    NewAddressInput,
    OnChainTransaction,
    Payment,
    PaymentRequest,
    SendCoinsInput,
    SendCoinsResponse,
    WalletBalance,
)


class LightningNodeBase:
    @abstractmethod
    def get_implementation_name(self) -> str:
        raise NotImplementedError()

    @abstractmethod
    async def initialize(self) -> AsyncGenerator[InitLnRepoUpdate, None]:
        raise NotImplementedError()

    @abstractmethod
    async def get_wallet_balance(self) -> WalletBalance:
        raise NotImplementedError()

    @abstractmethod
    async def list_all_tx(
        self, successful_only: bool, index_offset: int, max_tx: int, reversed: bool
    ) -> List[GenericTx]:
        raise NotImplementedError()

    @abstractmethod
    async def list_invoices(
        self,
        pending_only: bool,
        index_offset: int,
        num_max_invoices: int,
        reversed: bool,
    ):
        raise NotImplementedError()

    @abstractmethod
    async def list_on_chain_tx(self) -> List[OnChainTransaction]:
        raise NotImplementedError()

    @abstractmethod
    async def list_payments(
        self,
        include_incomplete: bool,
        index_offset: int,
        max_payments: int,
        reversed: bool,
    ):
        raise NotImplementedError()

    @abstractmethod
    async def add_invoice(
        self,
        value_msat: int,
        memo: str = "",
        expiry: int = 3600,
        is_keysend: bool = False,
    ) -> Invoice:
        raise NotImplementedError()

    @abstractmethod
    async def decode_pay_request(self, pay_req: str) -> PaymentRequest:
        raise NotImplementedError()

    @abstractmethod
    async def get_fee_revenue(self) -> FeeRevenue:
        raise NotImplementedError()

    @abstractmethod
    async def new_address(self, input: NewAddressInput) -> str:
        raise NotImplementedError()

    @abstractmethod
    async def send_coins(self, input: SendCoinsInput) -> SendCoinsResponse:
        raise NotImplementedError()

    @abstractmethod
    async def send_payment(
        self,
        pay_req: str,
        timeout_seconds: int,
        fee_limit_msat: int,
        amount_msat: Optional[int] = None,
    ) -> Payment:
        raise NotImplementedError()

    @abstractmethod
    async def get_ln_info(self) -> LnInfo:
        raise NotImplementedError()

    @abstractmethod
    async def unlock_wallet(self, password: str) -> bool:
        raise NotImplementedError()

    @abstractmethod
    async def listen_invoices(self) -> AsyncGenerator[Invoice, None]:
        raise NotImplementedError()

    @abstractmethod
    async def listen_forward_events(self) -> ForwardSuccessEvent:
        raise NotImplementedError()

    @abstractmethod
    async def channel_open(
        self, local_funding_amount: int, node_URI: str, target_confs: int
    ) -> str:
        raise NotImplementedError()

    @abstractmethod
    async def peer_resolve_alias(self, node_pub: str) -> str:
        raise NotImplementedError()

    @abstractmethod
    async def channel_list(self) -> List[Channel]:
        raise NotImplementedError()

    @abstractmethod
    async def channel_close(self, channel_id: int, force_close: bool) -> str:
        raise NotImplementedError()
