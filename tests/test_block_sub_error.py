"""
Regression test for the same #277 root cause in the block-subscription path.

Bitcoin Core 28+ returns strict JSON-RPC 2.0, so an errored getblock reply
has no "result" key. handle_block_sub did `yield json.dumps(r["result"])`
unguarded, which would crash the block stream with KeyError: 'result'.
"""

import json

from app.bitcoind import service


class _FakeSocket:
    def setsockopt(self, *args):
        pass

    def setsockopt_string(self, *args):
        pass

    def connect(self, *args):
        pass

    async def recv_multipart(self):
        # 32-byte block hash body -> a valid 64 char hex hash
        return (b"hashblock", b"\x11" * 32, b"\x00")


class _FakeCtx:
    def socket(self, *args):
        return _FakeSocket()

    def destroy(self):
        pass


class _FakeRequest:
    """is_disconnected() returns False for the first `process` checks, then
    True to break the loop."""

    def __init__(self, process: int):
        self._calls = 0
        self._process = process

    async def is_disconnected(self):
        self._calls += 1
        return self._calls > self._process


def _patch_zmq(monkeypatch):
    monkeypatch.setattr(service.zmq.asyncio, "Context", lambda: _FakeCtx())


async def test_handle_block_sub_skips_errored_getblock(monkeypatch):
    _patch_zmq(monkeypatch)

    async def fake_rpc(method, params=[]):
        # strict JSON-RPC 2.0 error: no "result" key
        return {"error": "some transient RPC error", "status": 500}

    monkeypatch.setattr(service, "bitcoin_rpc_async", fake_rpc)

    items = [item async for item in service.handle_block_sub(_FakeRequest(1))]

    assert items == []  # error skipped, nothing yielded, no KeyError


async def test_handle_block_sub_yields_on_success(monkeypatch):
    _patch_zmq(monkeypatch)

    async def fake_rpc(method, params=[]):
        return {"result": {"height": 5}, "error": None}

    monkeypatch.setattr(service, "bitcoin_rpc_async", fake_rpc)

    items = [item async for item in service.handle_block_sub(_FakeRequest(1))]

    assert len(items) == 1
    assert json.loads(items[0]) == {"height": 5}
