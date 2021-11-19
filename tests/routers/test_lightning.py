from app.models.lightning import LightningInfoLite
from app.routers import lightning
from fastapi import status
from starlette.testclient import TestClient
from tests.routers.utils import call_route
from tests.utils import monkeypatch_auth

from .test_lightning_utils import get_valid_lightning_info_lite


def test_route_authentications_latest(test_client: TestClient):
    prefixes = ["/latest/lightning", "/v1/lightning"]

    for prefix in prefixes:
        p = {"value_msat": 1337}
        call_route(test_client, f"{prefix}/add-invoice", params=p, method="p")
        call_route(test_client, f"{prefix}/get-balance")
        call_route(test_client, f"{prefix}/list-all-tx")
        call_route(test_client, f"{prefix}/list-invoices")
        call_route(test_client, f"{prefix}/list-onchain-tx")
        call_route(test_client, f"{prefix}/list-payments")
        p = {"amount": "", "address": ""}
        call_route(test_client, f"{prefix}/send-coins", params=p, method="p")
        p = {"pay_req": "1337"}
        call_route(test_client, f"{prefix}/send-payment", params=p, method="p")
        call_route(test_client, f"{prefix}/get-info-lite")
        call_route(test_client, f"{prefix}/get-info")
        call_route(test_client, f"{prefix}/decode-pay-req", params={"pay_req": ""})


def test_get_ln_status(test_client: TestClient, monkeypatch):
    prefix_latest = "/latest/lightning"
    prefix_v1 = "/v1/lightning"

    monkeypatch_auth(monkeypatch)

    async def mock_get_ln_info_lite() -> LightningInfoLite:
        return get_valid_lightning_info_lite()

    monkeypatch.setattr(lightning, "get_ln_info_lite", mock_get_ln_info_lite)

    response = test_client.get(f"{prefix_latest}/get-info-lite")

    r_js = response.json()
    v_js = get_valid_lightning_info_lite().dict()
    assert r_js == v_js

    response = test_client.get(f"{prefix_v1}/get-info-lite")
    r_js = response.json()
    v_js = get_valid_lightning_info_lite().dict()
    assert r_js == v_js
