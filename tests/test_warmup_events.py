"""
Tests for the SSE warmup behavior in app.main.

Regression tests for raspiblitz#3608: the Apps tab in the WebUI never loads
on bitcoin-only nodes because the warmup data was sent under an SSE event
name the WebUI does not listen to.
"""

from app.api.models import ApiStartupStatus, StartupState
from app.api.utils import SSE
from app.apps.constants import AppManagementProcessState
from app.apps.models import AppStatusQueryResult, AppStatusUpdateTaskMessage
from app.external.result_type.src.result.result import Ok

import app.main as main


def _make_app_status_message() -> Ok:
    return Ok(
        AppStatusUpdateTaskMessage(
            state=AppManagementProcessState.SUCCESS,
            message=AppStatusQueryResult(data=[], errors=[], timestamp=1),
        )
    )


def _patch_common(monkeypatch, sent, *, node_type: str, lightning: StartupState):
    async def fake_send(id, event, data):
        sent.append((id, event, data))

    async def fake_bitcoin_warmup_data():
        return [{"blocks": 1}, {"cpu": 1}]

    monkeypatch.setattr(main, "node_type", node_type)
    monkeypatch.setattr(
        main,
        "api_startup_status",
        ApiStartupStatus(bitcoin=StartupState.DONE, lightning=lightning),
    )
    monkeypatch.setattr(main, "_send_sse_event", fake_send)
    monkeypatch.setattr(
        main, "get_bitcoin_client_warmup_data", fake_bitcoin_warmup_data
    )
    monkeypatch.setattr(main, "new_connections", ["conn-1"])
    monkeypatch.setattr(main, "warmup_running", False)


async def test_bitcoinonly_warmup_sends_app_status_as_app_state_message(monkeypatch):
    """The WebUI only listens for SSE.APP_STATE_MESSAGE to populate the Apps
    tab. In bitcoin-only mode the warmup app status must be sent under that
    event, exactly like in lightning mode."""
    sent = []
    _patch_common(
        monkeypatch, sent, node_type="none", lightning=StartupState.DISABLED
    )

    async def fake_warmup_data():
        return [
            {"alias": "test"},
            {"blocks": 1},
            _make_app_status_message(),
            {"cpu": 1},
        ]

    monkeypatch.setattr(
        main, "get_full_client_warmup_data_bitcoinonly", fake_warmup_data
    )

    await main.warmup_new_connections()

    events = [event for (_, event, _) in sent]
    assert SSE.APP_STATE_MESSAGE in events, (
        f"expected app status under event '{SSE.APP_STATE_MESSAGE}', "
        f"got events: {events}"
    )


async def test_bitcoinonly_warmup_data_converts_exceptions(monkeypatch):
    """A single failing data source must not wipe out the whole warmup
    data set; it must be converted to an error entry like in the
    lightning variant."""
    from app.api import warmup

    async def failing_system_info():
        raise RuntimeError("system info unavailable")

    async def fake_btc_info():
        return {"blocks": 1}

    async def fake_app_status():
        return _make_app_status_message()

    async def fake_hardware_info():
        return {"cpu": 1}

    monkeypatch.setattr(warmup, "get_system_info", failing_system_info)
    monkeypatch.setattr(warmup, "get_btc_info", fake_btc_info)
    monkeypatch.setattr(warmup, "_get_app_status_data", fake_app_status)
    monkeypatch.setattr(warmup, "get_hardware_info", fake_hardware_info)

    res = await warmup.get_full_client_warmup_data_bitcoinonly()

    assert isinstance(res, list) and len(res) == 4, (
        f"expected a 4-entry warmup data list, got: {res!r}"
    )
    assert res[1] == {"blocks": 1}
    assert res[3] == {"cpu": 1}


async def test_warmup_running_flag_reset_on_error(monkeypatch):
    """If fetching warmup data blows up, the warmup_running flag must be
    reset — otherwise every future SSE client is permanently starved of
    warmup data until the API restarts."""
    sent = []
    _patch_common(
        monkeypatch, sent, node_type="none", lightning=StartupState.DISABLED
    )

    async def broken_warmup_data():
        return None  # what @logger.catch produces when the gather raises

    monkeypatch.setattr(
        main, "get_full_client_warmup_data_bitcoinonly", broken_warmup_data
    )

    await main.warmup_new_connections()  # must not raise

    assert main.warmup_running is False


async def test_app_status_cache_error_triggers_update_when_unlocked(monkeypatch):
    """Characterization: when the cache read errors and no update lock is
    held, an update task must be triggered so clients eventually get data."""
    from app.api import warmup
    from app.api.error_report.report import Report
    from app.external.result_type.src.result.result import Err

    class FakeCache:
        async def get_cached_app_status(self):
            return Err(Report("redis unavailable"))

    class FakeTask:
        def __init__(self):
            self.delayed = 0

        def delay(self):
            self.delayed += 1

    async def fake_lock_status(key):
        return Ok(False)

    fake_task = FakeTask()
    monkeypatch.setattr(warmup, "app_cache", FakeCache())
    monkeypatch.setattr(warmup, "get_lock_status", fake_lock_status)
    monkeypatch.setattr(warmup, "update_app_state_task", fake_task)

    result = await warmup._get_app_status_data()

    assert isinstance(result, Ok)
    assert result.ok_value is None
    assert fake_task.delayed == 1, "update task must be triggered"


async def test_warmup_ready_does_not_fetch_partial_data(monkeypatch):
    """When the API is fully initialized (lightning DISABLED counts as
    initialized), warmup must not fall through into the partial-data
    branches and re-fetch bitcoin data."""
    sent = []
    _patch_common(
        monkeypatch, sent, node_type="none", lightning=StartupState.DISABLED
    )

    called = []

    async def tracking_bitcoin_warmup_data():
        called.append(True)
        return [{"blocks": 1}, {"cpu": 1}]

    async def fake_warmup_data():
        return [
            {"alias": "test"},
            {"blocks": 1},
            _make_app_status_message(),
            {"cpu": 1},
        ]

    monkeypatch.setattr(
        main, "get_bitcoin_client_warmup_data", tracking_bitcoin_warmup_data
    )
    monkeypatch.setattr(
        main, "get_full_client_warmup_data_bitcoinonly", fake_warmup_data
    )

    await main.warmup_new_connections()

    assert not called, (
        "fully-initialized warmup must not call get_bitcoin_client_warmup_data"
    )
