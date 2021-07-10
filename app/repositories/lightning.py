from app.utils import lightning_config

if lightning_config.ln_node == "lnd":
    from app.repositories.ln_impl.lnd import get_wallet_balance_impl
else:
    from app.repositories.ln_impl.clightning import get_wallet_balance_impl


def get_wallet_balance():
    return get_wallet_balance_impl()
