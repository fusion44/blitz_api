import asyncio
import os
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


def handle_local_cookie():
    remove_local_cookie()

    blitz_path = os.path.join(os.path.expanduser("~"), ".blitz_api")
    full_cookie_file_path = os.path.join(blitz_path, ".cookie")
    enabled = config("BAPI_ENABLE_LOCAL_COOKIE_AUTH", default=False, cast=bool)

    if not enabled:
        return

    if not os.path.exists(blitz_path):
        try:
            os.makedirs(blitz_path)
        except OSError as e:
            logger.error(
                f"""Unable to create the .blit_api folder: {e}
                Please make sure that the target folder is readable.
            """
            )
    f = open(full_cookie_file_path, "w")
    f.write(sign_jwt())
    f.close()


def remove_local_cookie():
    full_cookie_file_path = os.path.join(
        os.path.expanduser("~"), ".blitz_api", ".cookie"
    )

    if os.path.exists(path=full_cookie_file_path):
        os.remove(full_cookie_file_path)


def register_cookie_updater():
    # We need to update the cookie file once the cookie is expired
    async def _cookie_updater():
        # refresh shortly before expiry; JWT_EXPIRY_TIME is in seconds.
        # guard against tiny/negative values that would busy-loop.
        refresh_interval = max(JWT_EXPIRY_TIME - 10, 1)
        while True:
            await asyncio.sleep(refresh_interval)
            handle_local_cookie()

    asyncio.create_task(_cookie_updater())
