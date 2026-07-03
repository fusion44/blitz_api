"""
Tests for JWT signing/validation.

Two bugs are covered:
- expiry was computed in seconds but added to a milliseconds epoch, so with
  the default (300) tokens effectively never got the intended lifetime, and
  the cookie-refresh loop slept for the wrong unit.
- a custom "expires" claim was used instead of the standard "exp", so PyJWT
  performed no expiry validation of its own.
"""

import time

import jwt

from app.auth.auth_bearer import JWTBearer
from app.auth.auth_handler import (
    JWT_ALGORITHM,
    JWT_EXPIRY_TIME,
    JWT_SECRET,
    decodeJWT,
    sign_jwt,
)


def test_signed_token_expiry_is_in_seconds():
    token = sign_jwt()
    payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])

    assert "exp" in payload, "token must carry a standard 'exp' claim"
    # exp must be roughly now + JWT_EXPIRY_TIME *seconds* (not ms)
    expected = time.time() + JWT_EXPIRY_TIME
    assert abs(payload["exp"] - expected) < 5, (
        f"exp {payload['exp']} not ~{expected} (unit mismatch?)"
    )


def test_expired_standard_claim_is_rejected():
    now = int(time.time())
    # old code would accept this (future ms 'expires'); the fixed code must
    # reject it because the standard 'exp' claim is in the past
    token = jwt.encode(
        {
            "user_id": "admin",
            "expires": int((now + 9999) * 1000),
            "exp": now - 10,
        },
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )

    assert decodeJWT(token) == {}
    assert JWTBearer().verify_jwt(token) is False


def test_fresh_token_verifies():
    token = sign_jwt()
    assert JWTBearer().verify_jwt(token) is True
