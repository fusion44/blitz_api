import pytest
from app.main import app
from starlette.testclient import TestClient


@pytest.fixture(scope="module")
def test_client():
    client = TestClient(app)
    yield client
