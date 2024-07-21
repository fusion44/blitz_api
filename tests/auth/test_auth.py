import jwt

from app.auth.auth_handler import decode_jwt, sign_jwt

UNIX_TIME = 1629200000

DEFAULT_VALUES = {
    "secret": "test_secret",
    "algorithm": "HS256",
    "jwt_expiry_time": 36008,
}


def mock_config(key, default=None, cast=None, vals=DEFAULT_VALUES):
    if key not in vals:
        raise ValueError(f"Unknown key {key}")

    return vals.get(key, default)


def test_sign_jwt_valid_token(monkeypatch):
    monkeypatch.setattr("app.auth.auth_handler.config", mock_config)
    monkeypatch.setattr("app.auth.auth_handler.time.time", lambda: UNIX_TIME)

    token = sign_jwt()

    try:
        t = jwt.decode(
            token,
            mock_config("secret"),
            algorithms=[str(mock_config("algorithm"))],
        )

        assert "user_id" in t
        assert "expires" in t
        assert t["user_id"] == "admin"
        assert t["expires"] == UNIX_TIME + mock_config("jwt_expiry_time")
    except jwt.ExpiredSignatureError:
        raise AssertionError("Token expired unexpectedly")
    except jwt.InvalidTokenError as e:
        print(e)
        raise AssertionError(f"Invalid token: {e}")


def test_sign_jwt_expired_token(monkeypatch):
    monkeypatch.setattr("app.auth.auth_handler.config", mock_config)
    monkeypatch.setattr("app.auth.auth_handler.time.time", lambda: UNIX_TIME)

    token = sign_jwt()

    expired_time = UNIX_TIME + mock_config("jwt_expiry_time") + 3600
    monkeypatch.setattr("app.auth.auth_handler.time.time", lambda: expired_time)

    # Should return None when expired
    res = decode_jwt(token)
    assert res is None
