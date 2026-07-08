"""
Regression test for raspiblitz-web#286.

_do_electrs_status_advanced populated the detail fields on the happy path but
never set installed/configured/status, so a fully installed, configured and
running electrs was still reported as installed=false, configured=false,
status=offline (while paradoxically returning ports and sync details).
"""

from app.api.models import ProcessResult
from app.apps.impl import raspiblitz as rb
from app.apps.models import AppOnlineStatus
from app.external.result_type.src.result.result import Ok

_STATUS_OUT = "\n".join(
    [
        "##### STATUS ELECTRS SERVICE",
        "version='v0.10.6'",
        "configured=1",
        "installed=1",
        "serviceRunning=1",
        "localIP='192.168.1.5'",
        "publicIP='1.2.3.4'",
        "portTCP='50001'",
        "portSSL='50002'",
        "TORaddress='abc.onion'",
    ]
)

_SYNC_OUT = "\n".join(
    [
        "serviceRunning=1",
        "electrumResponding=1",
        "blockheight='800000'",
        "blockheightPercent='100'",
        "initialSynced=1",
        "infoSync=''",
    ]
)


async def test_electrs_advanced_reports_installed_when_running(monkeypatch):
    async def fake_exec(command, **kwargs):
        out = _SYNC_OUT if "status-sync" in command else _STATUS_OUT
        return Ok(ProcessResult(0, out, ""))

    monkeypatch.setattr(rb, "exec_bash_command", fake_exec)

    result = await rb._do_electrs_status_advanced()

    assert isinstance(result, Ok)
    s = result.ok_value
    # sanity: we reached the happy path (details populated)
    assert s.http_port == "50001"
    assert s.details["electrum_responding"] == "1"
    # the actual bug: these were left at their False/offline defaults
    assert s.installed is True
    assert s.configured is True
    assert s.status == AppOnlineStatus.ONLINE
