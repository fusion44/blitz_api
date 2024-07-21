import asyncio
import os
import time

import jwt
from decouple import config
from loguru import logger


def sign_jwt() -> str:
    payload = {
        "user_id": "admin",
        "expires": int(
            time.time() + config("jwt_expiry_time", default=300, cast=int),
        ),
    }
    token = jwt.encode(
        payload,
        config("secret"),
        algorithm=str(config("algorithm")),
    )
    return token


def decode_jwt(token: str):
    try:
        decoded_token = jwt.decode(
            token, config("secret"), algorithms=[str(config("algorithm"))]
        )
        return decoded_token if decoded_token["expires"] >= time.time() else None
    except Exception as e:
        logger.warning(f"Unable to decode jwt_token {e}")
        return {}


def handle_local_cookie():
    remove_local_cookie()

    blitz_path = os.path.join(os.path.expanduser("~"), ".blitz_api")
    full_cookie_file_path = os.path.join(blitz_path, ".cookie")
    enabled = config("enable_local_cookie_auth", default=False, cast=bool)

    if not os.path.exists(blitz_path):
        os.makedirs(blitz_path)

    if enabled:
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
    expiry_time = config("jwt_expiry_time")

    async def _cookie_updater():
        while True:
            await asyncio.sleep(expiry_time - 10)
            handle_local_cookie()

    loop = asyncio.get_event_loop()
    loop.create_task(_cookie_updater())
