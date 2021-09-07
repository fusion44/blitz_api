import asyncio

import aioredis
from aioredis import Channel, Redis
from fastapi import Depends, FastAPI, Request
from fastapi_plugins import (
    RedisSettings,
    depends_redis,
    get_config,
    redis_plugin,
    registered_configuration,
)
from fastapi_versioning import VersionedFastAPI
from starlette import status

from app.repositories.bitcoin import (
    register_bitcoin_status_gatherer,
    register_bitcoin_zmq_sub,
)
from app.repositories.lightning import register_lightning_listener
from app.repositories.system import register_hardware_info_gatherer
from app.routers import apps, bitcoin, lightning, setup, system
from app.sse_starlette import EventSourceResponse

# start server with "uvicorn main:app --reload"


@registered_configuration
class AppSettings(RedisSettings):
    api_name: str = str(__name__)


app = FastAPI()
config = get_config()

app.include_router(apps.router)
app.include_router(bitcoin.router)
app.include_router(lightning.router)
app.include_router(system.router)
app.include_router(setup.router)


connections = []


app = VersionedFastAPI(
    app, version_format="{major}", prefix_format="/v{major}", enable_latest=True
)


@app.on_event("startup")
async def on_startup():
    await redis_plugin.init_app(app, config=config)
    await redis_plugin.init()
    await register_all_handlers()


@app.on_event("shutdown")
async def on_shutdown() -> None:
    await redis_plugin.terminate()


@app.get("/")
def index():
    # path operation function
    return {"data": "123"}


@app.get("/sse/subscribe", status_code=status.HTTP_200_OK)
async def stream(
    request: Request, channel: str = "default", redis: Redis = Depends(depends_redis)
):
    connections.append(request)
    return EventSourceResponse(subscribe(request, channel, redis))


async def subscribe(request: Request, channel: str, redis: Redis):
    (sub,) = await redis.subscribe(channel=Channel(channel, False))
    try:
        while await sub.wait_message():
            if await request.is_disconnected():
                connections.remove(request)
                await request.close()
                break
            else:
                if len(connections) > 0:
                    data = await sub.get(encoding="utf-8")
                    yield data
    except asyncio.CancelledError as e:
        connections.remove(request)
        await request.close()
    except aioredis.errors.ChannelClosedError as cle:
        connections.remove(request)
        await request.close()


async def register_all_handlers():
    await register_bitcoin_zmq_sub()
    await register_bitcoin_status_gatherer()
    await register_hardware_info_gatherer()
    await register_lightning_listener()
