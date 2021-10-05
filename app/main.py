import asyncio

from aioredis import Channel, Redis
from fastapi import FastAPI, Request
from fastapi_plugins import (
    RedisSettings,
    get_config,
    redis_plugin,
    registered_configuration,
)
from fastapi_versioning import VersionedFastAPI
from starlette import status
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import RedirectResponse

from app.repositories.bitcoin import (
    register_bitcoin_status_gatherer,
    register_bitcoin_zmq_sub,
)
from app.repositories.lightning import register_lightning_listener
from app.repositories.system import register_hardware_info_gatherer
from app.repositories.utils import get_client_warmup_data
from app.routers import apps, bitcoin, lightning, setup, system
from app.sse_starlette import EventSourceResponse
from app.utils import SSE


@registered_configuration
class AppSettings(RedisSettings):
    api_name: str = str(__name__)


unversioned_app = FastAPI()
config = get_config()

unversioned_app.include_router(apps.router)
unversioned_app.include_router(bitcoin.router)
unversioned_app.include_router(lightning.router)
unversioned_app.include_router(system.router)
unversioned_app.include_router(setup.router)


app = VersionedFastAPI(
    unversioned_app,
    version_format="{major}",
    prefix_format="/v{major}",
    enable_latest=True,
)

origins = [
    "http://localhost",
    "http://localhost:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
        req.url_for("latest", path="docs"),
        status_code=status.HTTP_307_TEMPORARY_REDIRECT,
    )


num_connections = 0
connections = {}
new_connections = []


@app.get("/sse/subscribe", status_code=status.HTTP_200_OK)
async def stream(request: Request):
    global num_connections
    q = asyncio.Queue()
    connections[num_connections] = q
    num_connections += 1
    new_connections.append(q)

    if len(new_connections) == 1:
        loop = asyncio.get_event_loop()
        loop.create_task(warmup_new_connections())

    return EventSourceResponse(subscribe(request, num_connections - 1, q))


async def warmup_new_connections():
    global new_connections

    res = await get_client_warmup_data()

    for c in new_connections:
        await asyncio.gather(
            *[
                c.put({"id": SSE.SYSTEM_INFO, "data": res[0].dict()}),
                c.put({"id": SSE.BTC_INFO, "data": res[1].dict()}),
                c.put({"id": SSE.LN_INFO_LITE, "data": res[2].dict()}),
                c.put({"id": SSE.WALLET_BALANCE, "data": res[3].dict()}),
                c.put({"id": SSE.INSTALLED_APP_STATUS, "data": res[4]}),
            ]
        )

    new_connections.clear()


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
