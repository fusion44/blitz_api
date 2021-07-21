from app.models.lightning import Invoice
from app.utils import lightning_config

if lightning_config.ln_node == "lnd":
    from app.repositories.ln_impl.lnd import (add_invoice_impl,
                                              get_wallet_balance_impl)
else:
    from app.repositories.ln_impl.clightning import (add_invoice_impl,
                                                     get_wallet_balance_impl)


def get_wallet_balance():
    return get_wallet_balance_impl()


def add_invoice(value_msat: int, memo: str = "", expiry: int = 3600, is_keysend: bool = False) -> Invoice:
    return add_invoice_impl(memo, value_msat, expiry, is_keysend)
