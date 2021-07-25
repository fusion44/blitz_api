from app.models.lightning import Invoice


async def get_wallet_balance_impl():
    raise NotImplementedError("c-lightning not yet implemented")


async def add_invoice_impl(value_msat: int, memo: str = "", expiry: int = 3600, is_keysend: bool = False) -> Invoice:
    raise NotImplementedError("c-lightning not yet implemented")
