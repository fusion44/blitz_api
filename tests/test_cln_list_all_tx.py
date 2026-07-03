"""
Regression tests for CLN list_all_tx.

Two bugs:
- `if pay is not Payment` compares an instance to the class (always true),
  so every payment was skipped and never appeared in the tx list.
- the successful_only filter appended the item inside the filter branch and
  then again unconditionally, so it never actually filtered anything.
"""

from app.lightning.impl.cln_jrpc import LnNodeCLNjRPC
from app.lightning.models import Payment, PaymentStatus, TxStatus


def _payment(status: PaymentStatus, value_msat: int) -> Payment:
    return Payment(
        payment_hash=f"hash-{value_msat}",
        value_msat=value_msat,
        fee_msat=0,
        creation_time_ns=value_msat,  # any stable, unique sort key
        payment_request="",
        status=status,
    )


def _patch_sources(monkeypatch, node, payments):
    async def fake_invoices(*a, **k):
        return []

    async def fake_onchain(*a, **k):
        return []

    async def fake_payments(*a, **k):
        return payments

    async def fake_info(*a, **k):
        return object()

    monkeypatch.setattr(node, "list_invoices", fake_invoices)
    monkeypatch.setattr(node, "list_on_chain_tx", fake_onchain)
    monkeypatch.setattr(node, "list_payments", fake_payments)
    monkeypatch.setattr(node, "get_ln_info", fake_info)


async def test_list_all_tx_includes_payments(monkeypatch):
    node = LnNodeCLNjRPC()
    _patch_sources(monkeypatch, node, [_payment(PaymentStatus.SUCCEEDED, 1000)])

    res = await node.list_all_tx(False, 0, 0, False)

    assert len(res) == 1, "the payment must appear in the tx list"
    assert res[0].amount == -1000


async def test_list_all_tx_successful_only_filters_payments(monkeypatch):
    node = LnNodeCLNjRPC()
    _patch_sources(
        monkeypatch,
        node,
        [
            _payment(PaymentStatus.SUCCEEDED, 1000),
            _payment(PaymentStatus.FAILED, 2000),
        ],
    )

    res = await node.list_all_tx(True, 0, 0, False)

    assert len(res) == 1, "successful_only must drop the failed payment"
    assert res[0].status == TxStatus.SUCCEEDED
