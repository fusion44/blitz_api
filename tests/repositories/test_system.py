import pytest
from fastapi import HTTPException, status

import app.system.service as sys
from app.system.models import LoginInput


@pytest.mark.asyncio
async def test_login(monkeypatch):
    async def fake_match_pw_positive(_):
        return True

    monkeypatch.setattr(
        "app.repositories.system.match_password",
        fake_match_pw_positive,
    )

    res = await sys.login(i=LoginInput(password="12345678"))
    assert type(res) is dict
    assert res.startswith("ey") == True

    async def fake_match_pw_negative(_):
        return False

    monkeypatch.setattr(
        "app.repositories.system.match_password",
        fake_match_pw_negative,
    )

    with pytest.raises(HTTPException) as exc_info:
        res = await sys.login(i=LoginInput(password="123456789"))
        print(res)

    exc = exc_info.value
    assert type(exc) is HTTPException
    assert exc.status_code == status.HTTP_401_UNAUTHORIZED
