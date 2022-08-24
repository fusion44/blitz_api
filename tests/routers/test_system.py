from starlette.testclient import TestClient

from app.main import app
from tests.routers.utils import call_route

client = TestClient(app)


def test_route_authentications_latest():
    prefixes = ["/latest/system", "/v1/system"]

    for prefix in prefixes:
        call_route(client, f"{prefix}/refresh-token", method="p")
