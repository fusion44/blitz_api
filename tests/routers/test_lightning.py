from app.models.lightning import LightningStatus
from app.routers import lightning
from fastapi import status
from starlette.testclient import TestClient
from tests.utils import monkeypatch_auth

from .test_lightning_utils import get_valid_lightning_status


def test_route_authentications_latest(test_client: TestClient):
    prefix = "/latest/lightning"
    response = test_client.get(f"{prefix}/get-ln-status")
    assert response.status_code == status.HTTP_403_FORBIDDEN

    response = test_client.post(f"{prefix}/add-invoice", params={"value_msat": 1337})
    assert response.status_code == status.HTTP_403_FORBIDDEN

    response = test_client.get(f"{prefix}/get-balance")
    assert response.status_code == status.HTTP_403_FORBIDDEN

    response = test_client.post(f"{prefix}/send-payment", params={"pay_req": "1337"})
    assert response.status_code == status.HTTP_403_FORBIDDEN

    response = test_client.get(f"{prefix}/get-info")
    assert response.status_code == status.HTTP_403_FORBIDDEN

    response = test_client.get(f"{prefix}/decode-pay-req", params={"pay_req": ""})
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_route_authentications_v1(test_client: TestClient):
    prefix = "/v1/lightning"
    response = test_client.get(f"{prefix}/get-ln-status")
    assert response.status_code == status.HTTP_403_FORBIDDEN

    response = test_client.post(f"{prefix}/add-invoice", params={"value_msat": 1337})
    assert response.status_code == status.HTTP_403_FORBIDDEN

    response = test_client.get(f"{prefix}/get-balance")
    assert response.status_code == status.HTTP_403_FORBIDDEN

    response = test_client.post(f"{prefix}/send-payment", params={"pay_req": ""})
    assert response.status_code == status.HTTP_403_FORBIDDEN

    response = test_client.get(f"{prefix}/get-info")
    assert response.status_code == status.HTTP_403_FORBIDDEN

    response = test_client.get(f"{prefix}/decode-pay-req", params={"pay_req": ""})
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_get_ln_status(test_client: TestClient, monkeypatch):
    prefix_latest = "/latest/lightning"
    prefix_v1 = "/v1/lightning"

    monkeypatch_auth(monkeypatch)

    async def mock_get_ln_status() -> LightningStatus:
        return get_valid_lightning_status()

    monkeypatch.setattr(lightning, "get_ln_status", mock_get_ln_status)

    response = test_client.get(f"{prefix_latest}/get-ln-status")

    r_js = response.json()
    v_js = get_valid_lightning_status().dict()
    assert r_js == v_js

    response = test_client.get(f"{prefix_v1}/get-ln-status")
    r_js = response.json()
    v_js = get_valid_lightning_status().dict()
    assert r_js == v_js
