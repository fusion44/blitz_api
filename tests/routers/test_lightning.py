from starlette.testclient import TestClient

from app.main import app
from app.models.lightning import LightningInfoLite
from app.routers import lightning
from tests.routers.test_lightning_utils import get_valid_lightning_info_lite
from tests.routers.utils import call_route
from tests.utils import monkeypatch_auth

test_client = TestClient(app)


def test_route_authentications_latest():
    prefixes = ["/latest/lightning", "/v1/lightning"]

    for prefix in prefixes:
        p = {"value_msat": 1337}
        call_route(test_client, f"{prefix}/add-invoice", params=p, method="p")
        call_route(test_client, f"{prefix}/get-balance")
        call_route(test_client, f"{prefix}/get-fee-revenue")
        call_route(test_client, f"{prefix}/list-all-tx")
        call_route(test_client, f"{prefix}/list-invoices")
        call_route(test_client, f"{prefix}/list-onchain-tx")
        call_route(test_client, f"{prefix}/list-payments")
        p = {"type": "p2wkh"}
        call_route(test_client, f"{prefix}/new-address", params=p, method="p")
        p = {"amount": "", "address": ""}
        call_route(test_client, f"{prefix}/send-coins", params=p, method="p")
        p = {"pay_req": "1337"}
        call_route(test_client, f"{prefix}/send-payment", params=p, method="p")
        call_route(test_client, f"{prefix}/get-info-lite")
        call_route(test_client, f"{prefix}/get-info")
        call_route(test_client, f"{prefix}/decode-pay-req", params={"pay_req": ""})
        p = {"password": "1"}
        call_route(test_client, f"{prefix}/unlock-wallet", params=p, method="p")


def test_get_ln_status(monkeypatch):
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
