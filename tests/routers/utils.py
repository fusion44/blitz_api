from fastapi import status
from starlette.testclient import TestClient

invalid_auth_header = {"Authorization": "Bearer dsgfdg"}


def call_route(test_client: TestClient, route: str, params={}, method="g"):
    # Test with no "Authentication" header at all
    # Should return a 401 by BlitzAPI's JWTBearer
    response = None
    if method == "g":
        response = test_client.get(route, params=params)
    elif method == "p":
        response = test_client.post(route, params=params)
    
    assert response.status_code == status.HTTP_401_UNAUTHORIZED

    # Test with an invalid "Authentication" header
    # Should return a 401 by BlitzAPI's JWTBearer
    response = None
    if method == "g":
        response = test_client.get(route, params=params, headers=invalid_auth_header)
    elif method == "p":
        response = test_client.post(route, params=params, headers=invalid_auth_header)

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
