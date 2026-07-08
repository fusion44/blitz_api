"""
Regression test for blitz_api#277.

Bitcoin Core 28+ answers a JSON-RPC 2.0 request with a strict 2.0 response:
a successful reply contains a "result" key but no "error" key. The old code
did `if result["error"] is not None` and crashed with KeyError: 'error'.
get_network_info / get_blockchain_info must handle a success response that
has no "error" key.
"""

from app.bitcoind import service


async def test_get_network_info_success_without_error_key(monkeypatch):
    # strict JSON-RPC 2.0 success payload: note there is NO "error" key
    async def fake_rpc(method, params=[]):
        return {"jsonrpc": "2.0", "result": {"stub": "networkinfo"}, "id": 1}

    monkeypatch.setattr(service, "bitcoin_rpc_async", fake_rpc)
    monkeypatch.setattr(
        service.NetworkInfo, "from_rpc", staticmethod(lambda result: result)
    )

    # must not raise / swallow-to-None on the missing "error" key
    out = await service.get_network_info()

    assert out == {"stub": "networkinfo"}


async def test_get_blockchain_info_success_without_error_key(monkeypatch):
    async def fake_rpc(method, params=[]):
        return {"jsonrpc": "2.0", "result": {"stub": "blockchaininfo"}, "id": 1}

    monkeypatch.setattr(service, "bitcoin_rpc_async", fake_rpc)
    monkeypatch.setattr(
        service.BlockchainInfo, "from_rpc", staticmethod(lambda result: result)
    )

    out = await service.get_blockchain_info()

    assert out == {"stub": "blockchaininfo"}
