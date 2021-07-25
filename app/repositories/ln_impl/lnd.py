import app.repositories.ln_impl.protos.rpc_pb2 as ln
from app.models.lightning import Invoice
from app.utils import lightning_config as lncfg


async def get_wallet_balance_impl() -> object:
    req = ln.WalletBalanceRequest()
    response = await lncfg.lnd_stub.WalletBalance(req)

    return {
        "confirmed_balance": response.confirmed_balance,
        "total_balance": response.total_balance,
        "unconfirmed_balance": response.unconfirmed_balance,
    }


async def add_invoice_impl(value_msat: int, memo: str = "", expiry: int = 3600, is_keysend: bool = False) -> Invoice:
    i = ln.Invoice(
        memo=memo,
        value_msat=value_msat,
        expiry=expiry,
        is_keysend=is_keysend,
    )

    response = await lncfg.lnd_stub.AddInvoice(i)

    invoice = Invoice(
        r_hash=response.r_hash.hex(),
        payment_request=response.payment_request,
        add_index=response.add_index,
        payment_addr=response.payment_addr.hex(),
    )

    return invoice
