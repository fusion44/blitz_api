"""
Regression test: a duplicate app-manage request must not touch the lock or
lifecycle of the install that is already running.

app_manage_task_impl released APP_MANAGE_LOCK_KEY and broadcast a FINISHED
message from its `finally` block even on the early-return path where the lock
was already held by another task. That deleted the running install's lock
(allowing concurrent installs) and made its listener stop early.
"""

import json

from app.apps.models import AppId, InstallMode
from app.external.result_type.src.result.result import Ok
from app.apps.tasks_impl import app_manage


async def test_lock_already_held_does_not_release_or_finish(monkeypatch):
    sent = []
    release_calls = []

    class FakeNotifier:
        def __init__(self, *args, **kwargs):
            pass

        async def connect(self):
            return Ok(None)

        async def send_message(self, key, contents):
            sent.append(contents)
            return Ok(None)

    async def fake_acquire(key, lock_ttl, redis):
        return Ok(False)  # lock already held by the running install

    async def fake_release(key, redis):
        release_calls.append(key)
        return Ok(None)

    monkeypatch.setattr(app_manage, "BaseChannelNotifier", FakeNotifier)
    monkeypatch.setattr(app_manage, "acquire_lock", fake_acquire)
    monkeypatch.setattr(app_manage, "release_update_lock", fake_release)

    await app_manage.app_manage_task_impl(
        "redis://127.0.0.1:6379/0", AppId.MEMPOOL, InstallMode.ON, True
    )

    states = [json.loads(c)["state"] for c in sent]

    assert release_calls == [], (
        "must not release the lock it never acquired (belongs to the running install)"
    )
    assert "finished" not in states, (
        "must not broadcast FINISHED and stop the running install's listener"
    )
    # the client should still be told the task is already running
    assert "failure" in states


async def test_acquired_lock_is_released_and_finished(monkeypatch):
    """The task that actually holds the lock must always release it and send
    FINISHED, otherwise the lock stays stuck until its TTL expires."""
    sent = []
    release_calls = []

    class FakeNotifier:
        def __init__(self, *args, **kwargs):
            pass

        async def connect(self):
            return Ok(None)

        async def send_message(self, key, contents):
            sent.append(contents)
            return Ok(None)

    async def fake_acquire(key, lock_ttl, redis):
        return Ok(True)  # lock acquired by this task

    async def fake_release(key, redis):
        release_calls.append(key)
        return Ok(None)

    async def empty_install(app_id):
        # an async generator that yields nothing (install does nothing here)
        return
        yield  # pragma: no cover

    class FakeApps:
        def install_app(self, app_id):
            return empty_install(app_id)

    monkeypatch.setattr(app_manage, "BaseChannelNotifier", FakeNotifier)
    monkeypatch.setattr(app_manage, "acquire_lock", fake_acquire)
    monkeypatch.setattr(app_manage, "release_update_lock", fake_release)
    monkeypatch.setattr(app_manage, "Apps", FakeApps)

    await app_manage.app_manage_task_impl(
        "redis://127.0.0.1:6379/0", AppId.MEMPOOL, InstallMode.ON, True
    )

    states = [json.loads(c)["state"] for c in sent]
    assert release_calls == [app_manage.AppsServiceKeys.APP_MANAGE_LOCK_KEY]
    assert "finished" in states
