"""
Characterization tests for SendCoinsInput.amount / send_all validation.

These lock the behaviour of the amount/send_all cross-field rule while the
Pydantic v1 `@validator` is migrated to v2. They must pass before and after
the migration.
"""

import pytest
from pydantic import ValidationError

from app.lightning.models import SendCoinsInput


def test_neither_amount_nor_send_all_is_rejected():
    with pytest.raises(ValidationError):
        SendCoinsInput(address="bc1qexample")


def test_zero_amount_without_send_all_is_rejected():
    with pytest.raises(ValidationError):
        SendCoinsInput(address="bc1qexample", amount=0)


def test_amount_and_send_all_together_is_rejected():
    with pytest.raises(ValidationError):
        SendCoinsInput(address="bc1qexample", amount=1000, send_all=True)


def test_positive_amount_is_accepted():
    m = SendCoinsInput(address="bc1qexample", amount=1000)
    assert m.amount == 1000
    assert m.send_all is False


def test_send_all_without_amount_is_accepted():
    m = SendCoinsInput(address="bc1qexample", send_all=True)
    assert m.send_all is True
    assert m.amount == 0
