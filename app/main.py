import asyncio
import json
import logging

from aioredis import Channel, Redis
from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import HTTPException
from fastapi_plugins import (
    RedisSettings,
    get_config,
    redis_plugin,
    registered_configuration,
)
from starlette import status
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import RedirectResponse

from app.auth.auth_handler import (
    handle_local_cookie,
    register_cookie_updater,
    remove_local_cookie,
)
from app.external.fastapi_versioning import VersionedFastAPI
from app.external.sse_starlette import EventSourceResponse
from app.models.system import APIPlatform
from app.repositories.bitcoin import (
    register_bitcoin_status_gatherer,
    register_bitcoin_zmq_sub,
)
from app.repositories.lightning import (
    listen_for_ssh_unlock,
    register_lightning_listener,
    register_wallet_unlock_listener,
    unregister_wallet_unlock_listener,
)
from app.repositories.system import register_hardware_info_gatherer
from app.repositories.utils import get_client_warmup_data
from app.routers import apps, bitcoin, lightning, setup, system
from app.utils import SSE, redis_get, send_sse_message


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
    await check_defer_register_handlers()
    handle_local_cookie()
    register_cookie_updater()


@app.on_event("shutdown")
async def on_shutdown() -> None:
    await redis_plugin.terminate()
    remove_local_cookie()


@app.get("/")
def index(req: Request):
    return RedirectResponse(
        req.url_for("latest", path="docs"),
        status_code=status.HTTP_307_TEMPORARY_REDIRECT,
    )


num_connections = 0
connections = {}
new_connections = []
wallet_locked = True


@app.get("/sse/subscribe", status_code=status.HTTP_200_OK)
async def stream(request: Request):
    global wallet_locked
    global num_connections
    q = asyncio.Queue()
    connections[num_connections] = q
    num_connections += 1
    new_connections.append(q)

    if wallet_locked:
        # send the the wallet locked event to the new connection
        await q.put(_make_evt_data(SSE.WALLET_LOCK_STATUS, {"locked": True}))
    else:
        await q.put(_make_evt_data(SSE.WALLET_LOCK_STATUS, {"locked": False}))

    if not wallet_locked and len(new_connections) == 1:
        # if the wallet is locked, we'll handle the warmup in _handle_ln_wallet_locked()
        loop = asyncio.get_event_loop()
        loop.create_task(warmup_new_connections())

    return EventSourceResponse(subscribe(request, num_connections - 1, q))


async def warmup_new_connections():
    global new_connections

    res = await get_client_warmup_data()

    for c in new_connections:
        await asyncio.gather(
            *[
                c.put(_make_evt_data(SSE.SYSTEM_INFO, res[0].dict())),
                c.put(_make_evt_data(SSE.BTC_INFO, res[1].dict())),
                c.put(_make_evt_data(SSE.LN_INFO, res[2].dict())),
                c.put(_make_evt_data(SSE.LN_INFO_LITE, res[3].dict())),
                c.put(_make_evt_data(SSE.LN_FEE_REVENUE, res[4])),
                c.put(_make_evt_data(SSE.WALLET_BALANCE, res[5].dict())),
                c.put(_make_evt_data(SSE.INSTALLED_APP_STATUS, res[6])),
            ]
        )

    new_connections.clear()


def _make_evt_data(evt: SSE, data):
    d1 = {"event": evt, "data": json.dumps(jsonable_encoder(data))}
    # d2 = {"event": evt, "data": jsonable_encoder(data)}
    return d1


async def subscribe(request: Request, id: int, q: asyncio.Queue):
    try:
        while True:
            if await request.is_disconnected():
                connections.pop(id)
                await request.close()
                break
            else:
                data = jsonable_encoder(await q.get())
                yield data
    except asyncio.CancelledError as e:
        connections.pop(id)
        await request.close()


register_handlers_finished = False


async def check_defer_register_handlers():
    """
    Special case for RaspiBlitz: Depending on the current setup step
    there still isn't a Bitcoin Deamon or Lightning Node running.
    We must defer the registration of all those handlers until later
    when everything is properly setup.

    Since there is a final reboot after the setup there is no need to
    check in the background whether setup is finished. The API server
    is restartet anyway.
    """

    platform = APIPlatform.get_current()
    if platform != APIPlatform.RASPIBLITZ:
        # Handle everything BUT RaspiBlitz normally
        await register_all_handlers(redis_plugin.redis)
    else:
        # Handle Raspiblitz
        setup_phase = await redis_get("setupPhase")

        if setup_phase == "done":
            await register_all_handlers(redis_plugin.redis)
        else:
            logging.warning(
                f"Setup not finished. Defering handler startup. Current phase: '{setup_phase}'"
            )


async def register_all_handlers(redis: Redis):
    global register_handlers_finished
    global wallet_locked

    if register_handlers_finished:
        raise RuntimeError("register_all_handlers() must not be called twice.")

    try:
        await register_bitcoin_zmq_sub()
        await register_bitcoin_status_gatherer()
        await register_hardware_info_gatherer()
        await register_lightning_listener()
        wallet_locked = False
    except HTTPException as r:
        if r.status_code == status.HTTP_423_LOCKED:
            # When the node is locked we must call register_lightning_listener
            # again when the user unlocks the wallet.
            print("Wallet is locked... waiting for unlock.")
            loop = asyncio.get_event_loop()
            loop.create_task(_handle_ln_wallet_locked())
        else:
            raise
    except NotImplementedError as r:
        raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, detail=r.args[0])

    (sub,) = await redis.subscribe(channel=Channel("default", False))
    loop = asyncio.get_event_loop()
    loop.create_task(broadcast_data_sse(sub))
    register_handlers_finished = True


async def broadcast_data_sse(sub):
    while await sub.wait_message():
        data = json.loads(await sub.get(encoding="utf-8"))
        for k in connections.keys():
            if connections.get(k):
                await connections.get(k).put(data)


async def _handle_ln_wallet_locked():
    global wallet_locked
    q = asyncio.Queue()
    register_wallet_unlock_listener(q)
    listen_for_ssh_unlock()
    await q.get()
    # Give the node a few seconds to fully start up
    await asyncio.sleep(5)
    print("Wallet was unlocked.")
    await register_lightning_listener()
    wallet_locked = False
    unregister_wallet_unlock_listener(q)

    # send a wallet unlocked message to all connections before
    # sending the warmup messages
    await send_sse_message(SSE.WALLET_LOCK_STATUS, {"locked": False})

    # send the connection warmup messages
    loop = asyncio.get_event_loop()
    loop.create_task(warmup_new_connections())
