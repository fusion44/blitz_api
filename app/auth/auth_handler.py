import time

import jwt
from loguru import logger

from app.api.config import config

JWT_SECRET = config("BAPI_JWT_SECRET")
JWT_ALGORITHM = config("BAPI_JWT_ALGORITHM")
# Token lifetime in seconds.
JWT_EXPIRY_TIME = config("BAPI_JWT_EXPIRY_TIME", default=3600, cast=int)


def sign_jwt() -> str:
    now = int(time.time())
    payload = {
        "user_id": "admin",
        "iat": now,
        # standard 'exp' claim (seconds) so PyJWT validates expiry itself
        "exp": now + JWT_EXPIRY_TIME,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decodeJWT(token: str) -> dict:
    try:
        # PyJWT validates the 'exp' claim and raises on expiry
        return jwt.decode(
            token,
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM],
            options={"require": ["exp"]},
        )
    except Exception as e:
        logger.warning(f"Unable to decode jwt_token {e}")
        return {}
