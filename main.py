from aioredis import Channel, Redis
from fastapi import Depends, FastAPI, Request
from fastapi_plugins import (RedisSettings, depends_redis, get_config,
                             redis_plugin, registered_configuration)
from sse_starlette.sse import EventSourceResponse

from app.repositories.bitcoin import (register_bitcoin_info_gatherer,
                                      register_bitcoin_zmq_sub)
from app.repositories.hardware_info import register_hardware_info_gatherer
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


@app.on_event('startup')
async def on_startup() -> None:
    await redis_plugin.init_app(app, config=config)
    await redis_plugin.init()


@app.on_event('shutdown')
async def on_shutdown() -> None:
    await redis_plugin.terminate()


@app.get('/')
def index():
    # path operation function
    return {'data': '123'}


connections = []


@app.get("/sse/subscribe")
async def stream(request: Request, channel: str = "default", redis: Redis = Depends(depends_redis)):
    connections.append(request)
    if len(connections) == 1:
        # start all subscription activity
        await register_all_handlers()

    return EventSourceResponse(subscribe(request, channel, redis))


async def subscribe(request: Request, channel: str, redis: Redis):
    (sub,) = await redis.subscribe(channel=Channel(channel, False))

    while await sub.wait_message():
        if await request.is_disconnected():
            connections.remove(request)
            break

        if len(connections) > 0:
            data = await sub.get(encoding='utf-8')
            yield data


async def register_all_handlers():
    await register_bitcoin_zmq_sub()
    await register_bitcoin_info_gatherer()
    await register_hardware_info_gatherer()
