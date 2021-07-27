from app.models.lightning import Invoice, Payment


async def get_wallet_balance_impl():
    raise NotImplementedError("c-lightning not yet implemented")


async def add_invoice_impl(value_msat: int, memo: str = "", expiry: int = 3600, is_keysend: bool = False) -> Invoice:
    raise NotImplementedError("c-lightning not yet implemented")


async def send_payment_impl(pay_req: str, timeout_seconds: int, fee_limit_msat: int) -> Payment:
    raise NotImplementedError("c-lightning not yet implemented")


async def register_lightning_listener_impl():
    raise NotImplementedError("c-lightning not yet implemented")
