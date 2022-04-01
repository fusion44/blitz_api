from typing import List, Optional

from app.models.lightning import (
    FeeRevenue,
    ForwardSuccessEvent,
    GenericTx,
    Invoice,
    LnInfo,
    NewAddressInput,
    OnChainTransaction,
    Payment,
    PaymentRequest,
    SendCoinsInput,
    SendCoinsResponse,
)


def get_implementation_name() -> str:
    return "c-lightning"


async def get_wallet_balance_impl():
    raise NotImplementedError("c-lightning not yet implemented")


async def list_all_tx_impl(
    successfull_only: bool, index_offset: int, max_tx: int, reversed: bool
) -> List[GenericTx]:
    raise NotImplementedError("c-lightning not yet implemented")


async def list_invoices_impl(
    pending_only: bool, index_offset: int, num_max_invoices: int, reversed: bool
):
    raise NotImplementedError("c-lightning not yet implemented")


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
    raise NotImplementedError("c-lightning not yet implemented")


async def get_fee_revenue_impl() -> FeeRevenue:
    raise NotImplementedError("c-lightning not yet implemented")


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
    raise NotImplementedError("c-lightning not yet implemented")


async def unlock_wallet_impl(password: str) -> bool:
    raise NotImplementedError("c-lightning not yet implemented")


async def listen_invoices() -> Invoice:
    raise NotImplementedError("c-lightning not yet implemented")


async def listen_forward_events() -> ForwardSuccessEvent:
    raise NotImplementedError("c-lightning not yet implemented")
