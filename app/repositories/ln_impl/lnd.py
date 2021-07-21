import app.repositories.ln_impl.protos.rpc_pb2 as ln
from app.utils import lightning_config as lncfg


def get_wallet_balance_impl() -> object:
    response = lncfg.lnd_stub.WalletBalance(
        ln.WalletBalanceRequest(),
        metadata=[('macaroon', lncfg.lnd_macaroon)],
    )

    return {
        "confirmed_balance": response.confirmed_balance,
        "total_balance": response.total_balance,
        "unconfirmed_balance": response.unconfirmed_balance,
    }
