import asyncio
from unittest.mock import AsyncMock

import pytest

from app import main
from app.api.models import ApiStartupStatus, StartupState
from app.api.utils import SSE
from app.apps.models import AppManagementProcessState, AppStatusQueryResult, AppStatusUpdateTaskMessage
from app.external.result_type.src.result.result import Ok


@pytest.mark.parametrize("node_type, legacy", [("none", True), ("lnd_grpc", False)])
def test_initial_app_list_uses_live_event_name(monkeypatch, node_type, legacy):
    message = AppStatusUpdateTaskMessage(
        state=AppManagementProcessState.SUCCESS,
        message=AppStatusQueryResult(data=[], errors=[], timestamp=42),
    )
    send = AsyncMock()
    monkeypatch.setattr(main, "_send_sse_event", send)
    monkeypatch.setattr(main, "new_connections", ["authenticated-client"])
    monkeypatch.setattr(main, "api_startup_status", ApiStartupStatus(
        bitcoin=StartupState.DONE,
        lightning=StartupState.DISABLED if legacy else StartupState.DONE,
    ))
    monkeypatch.setattr(main, "get_full_client_warmup_data_bitcoinonly",
                        AsyncMock(return_value=[RuntimeError("internal probe detail"), {}, Ok(message), {}]))
    monkeypatch.setattr(main, "get_full_client_warmup_data",
                        AsyncMock(return_value=[{}, {}, {}, {}, {}, Ok(message), {}]))
    monkeypatch.setattr(main, "node_type", node_type)

    asyncio.run(main.warmup_new_connections())

    if legacy:
        send.assert_any_await(
            "authenticated-client", SSE.SYSTEM_INFO, {"error": "Warmup data unavailable"}
        )
    expected = [SSE.APP_STATE_MESSAGE]
    if legacy:
        expected.append(SSE.INSTALLED_APP_STATUS)
    assert [call.args for call in send.await_args_list if call.args[1] in
            (SSE.APP_STATE_MESSAGE, SSE.INSTALLED_APP_STATUS)] == [
        ("authenticated-client", event, message.model_dump()) for event in expected
    ]


def test_a_failed_dashboard_probe_does_not_lock_out_new_connections(monkeypatch):
    dashboard = AsyncMock(side_effect=[RuntimeError("probe unavailable"), None])
    monkeypatch.setattr(main, "_send_dashboard_warmup", dashboard)
    monkeypatch.setattr(main, "new_connections", ["authenticated-client"])
    monkeypatch.setattr(main, "warmup_running", False)
    with pytest.raises(RuntimeError):
        asyncio.run(main.warmup_new_connections())
    asyncio.run(main.warmup_new_connections())
    assert dashboard.await_count == 2
