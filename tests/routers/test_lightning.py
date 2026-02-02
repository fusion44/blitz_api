from starlette.testclient import TestClient

from app.main import app
from tests.routers.utils import call_route

test_client = TestClient(app)


def test_route_authentications_latest():
    prefixes = ["/lightning"]

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
        call_route(test_client, f"{prefix}/get-info")
        call_route(test_client, f"{prefix}/decode-pay-req", params={"pay_req": ""})
        p = {"password": "1"}
        call_route(test_client, f"{prefix}/unlock-wallet", params=p, method="p")
