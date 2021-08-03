from app.models.lightning import Invoice, LnInfo, Payment
from app.utils import SSE, lightning_config, send_sse_message

if lightning_config.ln_node == "lnd":
    from app.repositories.ln_impl.lnd import (add_invoice_impl,
                                              get_ln_info_impl,
                                              get_wallet_balance_impl,
                                              register_lightning_listener_impl,
                                              send_payment_impl)
else:
    from app.repositories.ln_impl.clightning import (
        add_invoice_impl, get_ln_info_impl, get_wallet_balance_impl,
        register_lightning_listener_impl, send_payment_impl)


async def get_wallet_balance():
    return await get_wallet_balance_impl()


async def add_invoice(value_msat: int, memo: str = "", expiry: int = 3600, is_keysend: bool = False) -> Invoice:
    return await add_invoice_impl(memo, value_msat, expiry, is_keysend)


async def send_payment(pay_req: str, timeout_seconds: int, fee_limit_msat: int) -> Payment:
    res = await send_payment_impl(pay_req, timeout_seconds, fee_limit_msat)
    update_wallet_balance_via_sse()
    return res


async def update_wallet_balance_via_sse():
    res = await get_wallet_balance_impl()
    await send_sse_message(SSE.WALLET_BALANCE, res)


async def get_ln_info() -> LnInfo:
    return await get_ln_info_impl()


async def register_lightning_listener():
    await register_lightning_listener_impl()
