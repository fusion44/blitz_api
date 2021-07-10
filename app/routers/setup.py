import asyncio
from enum import Enum
from os import stat
from fastapi import APIRouter, HTTPException, status
from fastapi.params import Depends
from aioredis import Redis
from app.auth.auth_bearer import JWTBearer
from fastapi_plugins import depends_redis, redis_plugin

router = APIRouter(
    prefix="/setup",
    tags=["Setup"]
)


class SetupErrors(Enum):
    NAME_TO_LONG: 1
    PASSWORD_TO_SHORT: 2


async def fake_system_activity(redis: Redis):
    await redis.publish_json("default", {"type": "system_busy", "data": "Please hold on the line"})
    await asyncio.sleep(1)
    await redis.publish_json("default", {"type": "system_busy", "data": "Updating stuff"})
    await asyncio.sleep(2)
    await redis.publish_json("default", {"type": "system_busy", "data": "Installing stuff"})
    await asyncio.sleep(1)
    await redis.publish_json("default", {"type": "system_busy", "data": "Ensuring world peace"})
    await asyncio.sleep(1)
    await redis.publish_json("default", {"type": "system_busy", "data": "Solving world hunger"})
    await asyncio.sleep(1)
    await redis.publish_json("default", {"type": "system_busy", "data": "Bitcoin fixes this"})


def make_error(error_id: int, endpoint_url: str, err_description: str, description: str):
    return {
        "error_id": error_id,
        "endpoint_url": endpoint_url,
        "error_description": err_description,
        "description": description,
    }


def set_status(status: int, endpoint_url: str, description: str):
    return {
        "status": status,
        "endpoint_url": endpoint_url,
        "description": description,
    }


def get_setup_type_options(error: str = ""):
    return {"data": {
        "error": error,
        "type": "ask_setup_type",
        "endpoint_url": "/setup/type/{id}",
        "options": [
            {
                "id": 1,
                "short_desc": "Bitcoin",
                "long_desc": "Setup your RaspiBlitz as a Bitcoin Core node."
            },
            {
                "id": 2,
                "short_desc": "Litecoin",
                "long_desc": "Setup your RaspiBlitz as a Litecoin Core node."
            },
            {
                "id": 3,
                "short_desc": "Migrate a RaspiBlitz",
                "long_desc": "Setup your RaspiBlitz as a Litecoin Core node."
            },
        ]
    }}


setup_status = set_status(2, "/setup/start_setup", "HDD needs setup (2)")

setup_var_type = -1
setup_var_name = ""
setup_var_password_a = ""
setup_var_password_b = ""
setup_var_password_c = ""
setup_var_use_tor = True
setup_var_hdd_formatted = False


@router.get("/status")
def get_status():
    return setup_status


@router.post("/start_setup")
async def start_setup(redis: Redis = Depends(depends_redis)):
    await redis.publish_json("default", {"data": "Starting setup"})
    await asyncio.sleep(1)
    await redis.publish_json("default", {"data": "Hardware test"})
    await asyncio.sleep(1)
    await redis.publish_json("default", {"data": "Hardware looks good! Ready to proceed - have fun!"})
    await asyncio.sleep(1)
    await redis.publish_json("default", get_setup_type_options())


@router.post("/type/{id}", status_code=status.HTTP_200_OK)
async def start_setup(id: int, redis: Redis = Depends(depends_redis)):
    setup_var_type = id
    if id == 1:
        await redis.publish_json("default", {"data": "Starting Bitcoin Core setup"})
    elif id == 2:
        await redis.publish_json("default", {"data": "Starting Litecoin Core setup"})
    elif id == 3:
        await redis.publish_json("default", {"data": "Starting migration ..."})
    else:
        setup_var_type = -1
        await redis.publish_json("default", get_setup_type_options("Unknown setup type"))
        return

    setup_status = set_status(
        3, "setup/set_name/{name}", "Set name, one word, basic characters and not to long")

    await redis.publish_json("default", setup_status)
    await fake_system_activity(redis)


@router.post("/set_name/{name}", status_code=status.HTTP_200_OK)
async def set_name(name: str, redis: Redis = Depends(depends_redis)):
    if(len(name) > 80):
        await redis.publish_json("default", make_error(
            SetupErrors.NAME_TO_LONG,
            "setup/set_name/{name}",
            "Name can be max. 80 characters",
            "Set name, one word, basic characters and not to long",)
        )
        raise HTTPException(status.HTTP_406_NOT_ACCEPTABLE,
                            detail="Name can be max. 80 characters")
    elif(setup_var_type == -1):
        await redis.publish_json("default", get_setup_type_options("Setup type must be set first"))
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            detail="Setup type must be set first")
    else:
        setup_var_name = name
        setup_status = set_status(
            3,
            "/set_password/a/{password}",
            "Set password A")
        await redis.publish_json("default", setup_status)
    await fake_system_activity(redis)


@router.post("/set_password/{type}/{password}", status_code=status.HTTP_200_OK)
async def start_setup(type: str, password: str, redis: Redis = Depends(depends_redis)):
    if(len(password) < 8):
        await redis.publish_json("default", make_error(
            SetupErrors.PASSWORD_TO_SHORT,
            "setup/set_password/{type}/{password}",
            "Password must be min. 8 characters",
            "Set password, min 8 characters")
        )
        raise HTTPException(status.HTTP_406_NOT_ACCEPTABLE,
                            detail="Password must be min. 8 characters")
    else:
        if type == "a":
            setup_var_password_a = password
            setup_status = set_status(
                4,
                "setup/set_password/b/{password}",
                "Set password B")
            await redis.publish_json("default", setup_status)
        elif type == "b":
            setup_var_password_b = password
            setup_status = set_status(
                4,
                "setup/set_tor/{enabled}",
                "Set TOR true or false")
            await redis.publish_json("default", setup_status)
        elif type == "c":
            setup_var_password_c = password
            setup_status = set_status(
                5,
                "setup/set_password/c/{password}",
                "Set password C")
            await redis.publish_json("default", setup_status)
        await fake_system_activity()


@router.post("setup/set_tor/{enabled}", status_code=status.HTTP_200_OK)
async def set_tor(enabled: bool, redis: Redis = Depends(depends_redis)):
    setup_var_use_tor = enabled
    await fake_system_activity(redis)
    setup_status = set_status(
        5,
        "setup/format_hdd",
        "HDD needs to be formatted")

    await redis.publish_json("default", setup_status)


@router.post("format_hdd", status_code=status.HTTP_200_OK)
async def format_hdd(redis: Redis = Depends(depends_redis)):
    setup_var_hdd_formatted = True
    await fake_system_activity(redis)
    setup_status = set_status(
        7,
        "setup/set_password/c/{password}",
        "Set password C")
    await redis.publish_json("default", setup_status)
