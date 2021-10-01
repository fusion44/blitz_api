import asyncio

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
from starlette.responses import RedirectResponse

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


app = VersionedFastAPI(
    app, version_format="{major}", prefix_format="/v{major}", enable_latest=True
)


@app.on_event("startup")
async def on_startup():
    await redis_plugin.init_app(app, config=config)
    await redis_plugin.init()
    await register_all_handlers(redis_plugin.redis)


@app.on_event("shutdown")
async def on_shutdown() -> None:
    await redis_plugin.terminate()


@app.get("/")
def index(req: Request):
    return RedirectResponse(
        req.url_for("latest", path="docs"), status_code=status.HTTP_307_TEMPORARY_REDIRECT
    )


num_connections = 0
connections = {}


@app.get("/sse/subscribe", status_code=status.HTTP_200_OK)
async def stream(request: Request):
    global num_connections
    q = asyncio.Queue()
    connections[num_connections] = q
    num_connections += 1
    return EventSourceResponse(subscribe(request, num_connections - 1, q))


async def subscribe(request: Request, id: int, q: asyncio.Queue):
    try:
        while True:
            if await request.is_disconnected():
                connections.pop(id)
                await request.close()
                break
            else:
                data = await q.get()
                yield data
    except asyncio.CancelledError as e:
        connections.pop(id)
        await request.close()


async def register_all_handlers(redis: Redis):
    await register_bitcoin_zmq_sub()
    await register_bitcoin_status_gatherer()
    await register_hardware_info_gatherer()
    await register_lightning_listener()

    (sub,) = await redis.subscribe(channel=Channel("default", False))
    loop = asyncio.get_event_loop()
    loop.create_task(broadcast_data_sse(sub))


async def broadcast_data_sse(sub):
    while await sub.wait_message():
        data = await sub.get(encoding="utf-8")
        for k in connections.keys():
            if connections.get(k):
                await connections.get(k).put(data)
