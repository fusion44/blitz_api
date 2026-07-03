"""
Regression tests: the native_python system impl must not swallow exceptions.

@logger.catch defaults to reraise=False, so methods that raise
NotImplementedError silently returned None. The service layer relies on
NotImplementedError propagating (to return 501) and on unexpected errors
surfacing rather than becoming a None result.
"""

import pytest

from app.system.impl import native_python as np


def _system():
    return np.NativePythonSystem()


async def test_change_password_raises_not_implemented():
    with pytest.raises(NotImplementedError):
        await _system().change_password("a", "old", "new")


async def test_get_debug_logs_raw_raises_not_implemented():
    with pytest.raises(NotImplementedError):
        await _system().get_debug_logs_raw()


async def test_login_does_not_swallow_unexpected_errors(monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("config exploded")

    monkeypatch.setattr(np, "config", boom)

    with pytest.raises(RuntimeError):
        await _system().login(np.LoginInput(password="12345678"))
