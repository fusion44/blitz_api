import asyncio
from unittest.mock import AsyncMock

import pytest

from app.api.models import ProcessResult
from app.apps.models import AppOnlineStatus
from app.external.result_type.src.result.result import Ok


@pytest.mark.parametrize(
    "service_line, expected",
    [("", AppOnlineStatus.ONLINE), ("serviceRunning=1", AppOnlineStatus.ONLINE),
     ("serviceRunning=0", AppOnlineStatus.OFFLINE)],
)
def test_installed_and_running_are_independent(monkeypatch, tmp_path, service_line, expected):
    monkeypatch.setenv("BAPI_RB_SHELL_SCRIPT_PATH", str(tmp_path))
    monkeypatch.setenv("BAPI_LN_NODE", "none")
    from app.apps.impl import raspiblitz

    script = ProcessResult(0, f"installed=1\nconfigured=0\n{service_line}\n", "")
    monkeypatch.setattr(raspiblitz, "exec_bash_command", AsyncMock(return_value=Ok(script)))
    result = asyncio.run(raspiblitz.RaspiBlitzApps().get_app_status_single("thunderhub"))
    status = result.unwrap()
    assert status.installed and not status.configured
    assert status.status == expected
