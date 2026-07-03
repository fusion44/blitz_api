"""
Regression test: uninstalling an app must honour the keep_data choice.

_manage_app dropped input.keep_data and always ran the bonus script with a
bare "off", so the RaspiBlitz bonus script fell back to an interactive
whiptail prompt (which hangs the non-interactive API) instead of the
requested keep/delete behaviour.
"""

import pytest

from app.apps.impl import raspiblitz
from app.apps.models import AppId, AppUninstallInput
from app.external.result_type.src.result.result import Ok


@pytest.fixture
def node(monkeypatch):
    n = raspiblitz.RaspiBlitzApps()

    async def fake_valid(app_id, installing):
        return Ok(None)

    monkeypatch.setattr(raspiblitz, "_validate_app_id", lambda app_id: Ok(None))
    monkeypatch.setattr(n, "_valid_installed_status", fake_valid)
    return n


async def _run_uninstall(node, monkeypatch, keep_data: bool) -> str:
    captured = {}

    async def fake_bonus(app_id, params):
        captured["params"] = params
        return
        yield  # unreachable; makes this an async generator

    monkeypatch.setattr(node, "run_bonus_script", fake_bonus)

    async for _ in node.uninstall_app(
        AppUninstallInput(app_id=AppId.MEMPOOL, keep_data=keep_data)
    ):
        pass

    return captured["params"]


async def test_uninstall_delete_data(node, monkeypatch):
    params = await _run_uninstall(node, monkeypatch, keep_data=False)
    assert params == "off --delete-data"


async def test_uninstall_keep_data(node, monkeypatch):
    params = await _run_uninstall(node, monkeypatch, keep_data=True)
    assert params == "off --keep-data"
