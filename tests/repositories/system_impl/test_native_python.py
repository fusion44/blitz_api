import pytest
from pydantic import AnyStrMinLengthError, ValidationError

import app.repositories.system_impl.native_python as npy
from app.models.system import LoginInput


@pytest.mark.asyncio
async def test_match_password(monkeypatch):
    ok = LoginInput(password="password_1234")
    nok = LoginInput(password="wrong_password")

    monkeypatch.setattr(
        "app.repositories.system_impl.native_python.config",
        lambda _, cast: ok.password,
    )

    res = await npy.match_password(ok)
    assert res == True

    res = await npy.match_password(nok)
    assert res == False

    with pytest.raises(ValidationError) as exc_info:
        # Should be 8 characters
        LoginInput(password="1234567")

    exc = exc_info.value
    assert type(exc) is ValidationError
    assert type(exc.args[0][0].exc) is AnyStrMinLengthError
