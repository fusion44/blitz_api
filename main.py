from app.repositories.bitcoin import register_bitcoin_info_gatherer, register_bitcoin_zmq_sub
from aioredis import Channel, Redis
from fastapi import FastAPI, Depends
from fastapi_plugins import (get_config, depends_redis, registered_configuration,
                             redis_plugin, RedisSettings)
from sse_starlette.sse import EventSourceResponse
from app.routers import apps, bitcoin, system

# start server with "uvicorn main:app --reload"


@registered_configuration
class AppSettings(RedisSettings):
    api_name: str = str(__name__)


app = FastAPI()
config = get_config()

app.include_router(apps.router)
app.include_router(bitcoin.router)
app.include_router(system.router)


@app.on_event('startup')
async def on_startup() -> None:
    await redis_plugin.init_app(app, config=config)
    await redis_plugin.init()
    await register_bitcoin_zmq_sub()
    await register_bitcoin_info_gatherer()


@app.on_event('shutdown')
async def on_shutdown() -> None:
    await redis_plugin.terminate()


@app.get('/')
def index():
    # path operation function
    return {'data': '123'}


@app.get("/sse/subscribe")
async def stream(channel: str = "default", redis: Redis = Depends(depends_redis)):
    return EventSourceResponse(subscribe(channel, redis))


async def subscribe(channel: str, redis: Redis):
    (sub,) = await redis.subscribe(channel=Channel(channel, False))

    while await sub.wait_message():
        data = await sub.get(encoding='utf-8')
        yield {"event": "event_id", "data": data}
