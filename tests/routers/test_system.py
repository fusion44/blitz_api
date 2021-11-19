from starlette.testclient import TestClient
from tests.routers.utils import call_route


def test_route_authentications_latest(test_client: TestClient):
    prefixes = ["/latest/system", "/v1/system"]

    for prefix in prefixes:
        call_route(test_client, f"{prefix}/refresh-token", method="p")
