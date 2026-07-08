"""
The hardware-info gatherer must survive a failing get_hardware_info.

_handle_gather_hardware_info had no error handling, so a single exception
from get_hardware_info killed the task permanently ("Task exception was
never retrieved") and hardware SSE updates stopped until restart.
"""

import asyncio

import pytest

from app.system import service


async def test_gatherer_survives_get_hardware_info_error(monkeypatch):
    calls = {"n": 0}

    async def flaky_hardware_info():
        calls["n"] += 1
        if calls["n"] == 1:
            raise ValueError("bad redis value")
        return {"ok": True}

    sent = []

    async def fake_broadcast(event, data):
        sent.append(data)

    # break the infinite loop after the second iteration
    async def fake_sleep(_seconds):
        if calls["n"] >= 2:
            raise asyncio.CancelledError()

    monkeypatch.setattr(service, "get_hardware_info", flaky_hardware_info)
    monkeypatch.setattr(service, "broadcast_sse_msg", fake_broadcast)
    monkeypatch.setattr(service.asyncio, "sleep", fake_sleep)

    with pytest.raises(asyncio.CancelledError):
        await service._handle_gather_hardware_info()

    # first iteration errored but did not kill the loop; second succeeded
    assert calls["n"] == 2
    assert sent == [{"ok": True}]
