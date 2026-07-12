from starlette.testclient import TestClient

from app.main import app
from tests.routers.utils import call_route
import app.main as main
from app.api.models import StartupState

client = TestClient(app)


def test_route_authentications_latest():
    prefixes = ["/system"]

    for prefix in prefixes:
        call_route(client, f"{prefix}/refresh-token", method="p")


def _set_status(bitcoin, lightning):
    main.api_startup_status.bitcoin = bitcoin
    main.api_startup_status.lightning = lightning


def test_health_is_unauthenticated_and_200_when_ready():
    _set_status(StartupState.DONE, StartupState.DONE)
    # no `with`: don't start lifespan/background tasks
    c = TestClient(main.app)
    resp = c.get("/system/health")  # no Authorization header
    assert resp.status_code == 200
    body = resp.json()
    assert body["healthy"] is True
    assert body["subsystems"] == []


def test_health_503_when_not_ready_body_is_health_info():
    _set_status(StartupState.BOOTSTRAPPING, StartupState.DONE)
    c = TestClient(main.app)
    resp = c.get("/system/health")
    assert resp.status_code == 503
    body = resp.json()
    # body is a SystemHealthInfo, NOT an ErrorMessage
    assert body["healthy"] is False
    assert "error_code" not in body
    assert body["message"] == "bitcoind not ready: bootstrapping"


def test_health_verbose_lists_subsystems():
    _set_status(StartupState.DONE, StartupState.DONE)
    c = TestClient(main.app)
    resp = c.get("/system/health?verbose=true")
    assert resp.status_code == 200
    names = [s["name"] for s in resp.json()["subsystems"]]
    assert names == ["api", "bitcoind", "lightning"]
