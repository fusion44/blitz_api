import asyncio
import os
import time
from typing import Dict

import jwt
from decouple import config

JWT_SECRET = config("secret")
JWT_ALGORITHM = config("algorithm")
JWT_EXPIRY_TIME = config("jwt_expiry_time", default=300, cast=int)


def signJWT() -> Dict[str, str]:
    payload = {
        "user_id": "admin",
        "expires": int(round(time.time() * 1000) + JWT_EXPIRY_TIME),
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return token_response(token)


def token_response(token: str):
    return {"access_token": token}


def decodeJWT(token: str) -> dict:
    try:
        decoded_token = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return decoded_token if decoded_token["expires"] >= time.time() else None
    except Exception as e:
        print(f"Unable to decode jwt_token {e}")
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
        f.write(signJWT()["access_token"])
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
        while True:
            await asyncio.sleep(JWT_EXPIRY_TIME - 10)
            handle_local_cookie()

    loop = asyncio.get_event_loop()
    loop.create_task(_cookie_updater())
