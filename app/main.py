import asyncio
import json
import logging

from aioredis import Channel, Redis
from decouple import config as dconfig
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
from app.models.api import ApiStartupStatus, StartupState
from app.models.lightning import LnInitState
from app.models.system import APIPlatform
from app.repositories.bitcoin import (
    initialize_bitcoin_repo,
    register_bitcoin_status_gatherer,
    register_bitcoin_zmq_sub,
)
from app.repositories.lightning import initialize_ln_repo, register_lightning_listener
from app.repositories.system import register_hardware_info_gatherer
from app.repositories.utils import get_client_warmup_data
from app.routers import apps, bitcoin, lightning, setup, system
from app.utils import SSE, redis_get, send_sse_message

logging.basicConfig(level=logging.WARNING)

node_type = dconfig("ln_node")


@registered_configuration
class AppSettings(RedisSettings):
    api_name: str = str(__name__)


unversioned_app = FastAPI()
config = get_config()

unversioned_app.include_router(apps.router)
unversioned_app.include_router(bitcoin.router)
if node_type != "none":
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
    register_cookie_updater()
    await send_sse_message(SSE.SYSTEM_STARTUP_INFO, api_startup_status.dict())

    loop = asyncio.get_event_loop()
    loop.create_task(_initialize_bitcoin())
    loop.create_task(_initialize_lightning())

    await check_defer_register_handlers()
    handle_local_cookie()


api_startup_status = ApiStartupStatus()


async def _initialize_bitcoin():
    api_startup_status.bitcoin = StartupState.OFFLINE
    await send_sse_message(SSE.SYSTEM_STARTUP_INFO, api_startup_status.dict())

    await initialize_bitcoin_repo()
    await register_bitcoin_zmq_sub()
    await register_bitcoin_status_gatherer()

    api_startup_status.bitcoin = StartupState.DONE
    await send_sse_message(SSE.SYSTEM_STARTUP_INFO, api_startup_status.dict())


async def _initialize_lightning():
    if node_type == "none":
        api_startup_status.lightning = StartupState.DISABLED
        api_startup_status.lightning_msg = ""
        await send_sse_message(SSE.SYSTEM_STARTUP_INFO, api_startup_status.dict())
        logging.info("Lightning node is disabled, skipping initialization")
        return

    try:
        async for u in initialize_ln_repo():
            changed = False
            if (
                u.state == LnInitState.OFFLINE
                and api_startup_status.lightning != StartupState.OFFLINE
            ):
                api_startup_status.lightning = StartupState.OFFLINE
                changed = True
            elif (
                u.state == LnInitState.BOOTSTRAPPING
                and api_startup_status.lightning != StartupState.BOOTSTRAPPING
            ):
                api_startup_status.lightning = StartupState.BOOTSTRAPPING
                changed = True
            elif (
                u.state == LnInitState.LOCKED
                and api_startup_status.lightning != StartupState.LOCKED
            ):
                api_startup_status.lightning = StartupState.LOCKED
                changed = True
            elif (
                u.state == LnInitState.DONE
                and api_startup_status.lightning != StartupState.DONE
            ):
                # We've successfully connected to the lightning node
                # We can now register all lightning listeners
                await register_lightning_listener()
                api_startup_status.lightning = StartupState.DONE
                api_startup_status.lightning_msg = ""
                changed = True

            if api_startup_status.lightning_msg != u.msg:
                api_startup_status.lightning_msg = u.msg
                changed = True

            if changed:
                await send_sse_message(
                    SSE.SYSTEM_STARTUP_INFO, api_startup_status.dict()
                )
    except HTTPException as r:
        logging.error(f"Exception {r.detail}.")
        raise
    except NotImplementedError as r:
        raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, detail=r.args[0])


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


@app.get("/sse/subscribe", status_code=status.HTTP_200_OK)
async def stream(request: Request):

    global num_connections
    q = asyncio.Queue()
    connections[num_connections] = q
    num_connections += 1
    new_connections.append(q)

    await q.put(_make_evt_data(SSE.SYSTEM_STARTUP_INFO, api_startup_status.dict()))

    if (
        api_startup_status.bitcoin == StartupState.DONE
        and api_startup_status.lightning == StartupState.DONE
        and len(new_connections) == 1
    ):
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
    there still isn't a Bitcoin Daemon or Lightning Node running.
    We must defer the registration of all those handlers until later
    when everything is properly setup.

    Since there is a final reboot after the setup there is no need to
    check in the background whether setup is finished. The API server
    is restarted anyway.
    """

    platform = APIPlatform.get_current()
    if platform != APIPlatform.RASPIBLITZ:
        # Handle everything BUT RaspiBlitz normally
        await register_all_handlers(redis_plugin.redis)
    else:
        # Handle Raspiblitz
        setup_phase = await redis_get("setupPhase")

        while setup_phase != "done":
            f"Setup not finished. Deferring handler startup. Current phase: '{setup_phase}'"
            await asyncio.sleep(1)
            setup_phase = await redis_get("setupPhase")
            print(f"Setup phase: '{setup_phase}'")

        await register_all_handlers(redis_plugin.redis)


async def register_all_handlers(redis: Redis):
    global register_handlers_finished

    if register_handlers_finished:
        raise RuntimeError("register_all_handlers() must not be called twice.")

    await register_hardware_info_gatherer()

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
