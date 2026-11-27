from stat import S_IMODE
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.setup.impl.raspiblitz import router as setup


@pytest.fixture
def setup_client(monkeypatch, tmp_path):
    values = {"setupPhase": "setup", "state": "waitsetup", "hddBlocksBitcoin": "1"}

    async def get_value(key):
        return values.get(key)

    handoff = tmp_path / "raspiblitz.setup"
    advance = AsyncMock()
    monkeypatch.setattr(setup, "setupFilePath", str(handoff))
    monkeypatch.setattr(setup, "redis_get", get_value)
    monkeypatch.setattr(setup, "_call_script", advance)
    monkeypatch.setattr(setup, "sign_jwt", lambda: {"token": "fixture"})
    app = FastAPI()
    app.include_router(setup.router)
    return TestClient(app), handoff, advance, values


def submit(client, **changes):
    data = dict(hostname="test-node", lightning="none", passwordA="Fixture-A", passwordB="Fixture-B")
    return client.post("/setup/setup-start-done", json={**data, **changes})


@pytest.mark.parametrize("keep,action,format_disk,clean_disk", [
    (True, "keepBlockchain", "0", "1"), (False, "all", "1", "0")
])
def test_fresh_setup_from_recovery(setup_client, keep, action, format_disk, clean_disk):
    client, handoff, advance, values = setup_client
    values["setupPhase"] = "recovery"
    response = submit(client, forceFreshSetup=True, keepBlockchain=keep)
    assert response.status_code == 200
    assert S_IMODE(handoff.stat().st_mode) == 0o640
    lines = handoff.read_text().splitlines()
    assert {"menuchoice=setup", "systemCopy=0", f"deleteData={action}",
            f"formatHDD={format_disk}", f"cleanHDD={clean_disk}"}.issubset(lines)
    advance.assert_awaited_once()


def test_mismatched_system_requires_a_matching_frontend(setup_client, monkeypatch, tmp_path):
    client, _, advance, _ = setup_client
    monkeypatch.setattr(setup, "setupFilePath", str(tmp_path / "missing" / "raspiblitz.setup"))
    response = submit(client, keepBlockchain=False)
    assert response.status_code == 409
    advance.assert_not_awaited()


@pytest.mark.parametrize("changes, expected", [
    ({"keepBlockchain": True}, 400), ({"lightning": "unsupported"}, 400),
    ({"passwordA": "invalid input"}, 400), ({"hostname": "a b c"}, 400),
])
def test_rejected_input_leaves_handoff_untouched(setup_client, changes, expected):
    client, handoff, advance, values = setup_client
    values["hddBlocksBitcoin"] = "0"
    response = submit(client, **{"keepBlockchain": False, **changes})
    assert response.status_code == expected
    assert not handoff.exists()
    advance.assert_not_awaited()


def test_existing_recovery_does_not_request_a_disk_action(setup_client):
    client, handoff, advance, values = setup_client
    values["setupPhase"] = "recovery"
    assert submit(client).status_code == 200
    assert "deleteData" not in handoff.read_text()
    advance.assert_awaited_once()
