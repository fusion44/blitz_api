import asyncio
import logging

import async_timeout
from decouple import config as dconfig
from fastapi import Depends, FastAPI, Request
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

from app.auth.auth_bearer import JWTBearer
from app.auth.auth_handler import (
    handle_local_cookie,
    register_cookie_updater,
    remove_local_cookie,
)
from app.external.fastapi_versioning import VersionedFastAPI
from app.external.sse_starlette import EventSourceResponse, ServerSentEvent
from app.models.api import ApiStartupStatus, StartupState
from app.models.lightning import LnInitState
from app.repositories.bitcoin import (
    initialize_bitcoin_repo,
    register_bitcoin_status_gatherer,
    register_bitcoin_zmq_sub,
)
from app.repositories.lightning import initialize_ln_repo, register_lightning_listener
from app.repositories.system import get_hardware_info, register_hardware_info_gatherer
from app.repositories.utils import (
    get_bitcoin_client_warmup_data,
    get_full_client_warmup_data,
    get_full_client_warmup_data_bitcoinonly,
)
from app.routers import apps, bitcoin, lightning, setup, system
from app.utils import SSE, send_sse_message, sse_queue

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

    await register_all_handlers()
    handle_local_cookie()


api_startup_status = ApiStartupStatus()


async def _set_startup_status(
    bitcoin: StartupState = None,
    bitcoin_msg: str = None,
    lightning: StartupState = None,
    lightning_msg: str = None,
):
    # We must know when both bitcoin and lightning are initialized
    # to trigger the warmup method for new SSE clients
    if bitcoin is not None:
        api_startup_status.bitcoin = bitcoin
    if bitcoin_msg is not None:
        api_startup_status.bitcoin_msg = bitcoin_msg
    if lightning is not None:
        api_startup_status.lightning = lightning
    if lightning_msg is not None:
        api_startup_status.lightning_msg = lightning_msg

    loop = asyncio.get_event_loop()
    loop.create_task(warmup_new_connections())
    await send_sse_message(SSE.SYSTEM_STARTUP_INFO, api_startup_status.dict())


async def _initialize_bitcoin():
    await _set_startup_status(bitcoin=StartupState.OFFLINE)
    await initialize_bitcoin_repo()
    await register_bitcoin_zmq_sub()
    await register_bitcoin_status_gatherer()
    await _set_startup_status(bitcoin=StartupState.DONE)


async def _initialize_lightning():
    if node_type == "none" or node_type == "":
        api_startup_status.lightning = StartupState.DISABLED
        api_startup_status.lightning_msg = ""
        await _set_startup_status(lightning=StartupState.DISABLED)
        logging.info("Lightning node is disabled, skipping initialization")
        return

    try:
        async for u in initialize_ln_repo():
            ln_status = None
            ln_msg = None
            changed = False
            if (
                u.state == LnInitState.OFFLINE
                and api_startup_status.lightning != StartupState.OFFLINE
            ):
                ln_status = StartupState.OFFLINE
                changed = True
            elif (
                u.state == LnInitState.BOOTSTRAPPING
                and api_startup_status.lightning != StartupState.BOOTSTRAPPING
            ):
                ln_status = StartupState.BOOTSTRAPPING
                changed = True
            elif (
                u.state == LnInitState.LOCKED
                and api_startup_status.lightning != StartupState.LOCKED
            ):
                ln_status = StartupState.LOCKED
                changed = True
            elif (
                u.state == LnInitState.DONE
                and api_startup_status.lightning != StartupState.DONE
            ):
                # We've successfully connected to the lightning node
                # We can now register all lightning listeners
                await register_lightning_listener()
                ln_status = StartupState.DONE
                ln_msg = ""
                changed = True

            if api_startup_status.lightning_msg != u.msg:
                ln_msg = u.msg
                changed = True

            if changed:
                await _set_startup_status(lightning=ln_status, lightning_msg=ln_msg)

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


@app.get(
    "/sse/subscribe",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(JWTBearer())],
)
async def stream(request: Request):

    global num_connections
    q = asyncio.Queue()
    connections[num_connections] = q
    num_connections += 1
    new_connections.append(q)

    await q.put(
        ServerSentEvent(
            event=SSE.SYSTEM_STARTUP_INFO,
            data=jsonable_encoder(api_startup_status.dict()),
        )
    )

    loop = asyncio.get_event_loop()
    loop.create_task(warmup_new_connections())

    return EventSourceResponse(subscribe(request, num_connections - 1, q))


warmup_running = False


async def warmup_new_connections():
    # This doesn't keep track of which connection has received
    # which data already, so it may send data twice data to the client
    # when the startup state changes. Especially the hardware info
    # is rather data intensive. This is OK for now, to keep the code simple.

    global new_connections
    if len(new_connections) == 0:
        return

    global warmup_running
    if warmup_running:
        logging.debug("Warmup already running, skipping")
        return

    warmup_running = True
    is_ready = api_startup_status.is_fully_initialized()

    if is_ready:

        # when lightning is active
        if node_type != "" and node_type != "none":

            res = await get_full_client_warmup_data()
            for c in new_connections:
                await asyncio.gather(
                    *[
                        c.put(send_sse_message(SSE.SYSTEM_INFO, res[0].dict())),
                        c.put(send_sse_message(SSE.BTC_INFO, res[1].dict())),
                        c.put(send_sse_message(SSE.LN_INFO, res[2].dict())),
                        c.put(send_sse_message(SSE.LN_INFO_LITE, res[3].dict())),
                        c.put(send_sse_message(SSE.LN_FEE_REVENUE, res[4])),
                        c.put(send_sse_message(SSE.WALLET_BALANCE, res[5].dict())),
                        c.put(send_sse_message(SSE.INSTALLED_APP_STATUS, res[6])),
                        c.put(send_sse_message(SSE.HARDWARE_INFO, res[7])),
                    ]
                )

        # when its bitcoin only
        else:

            res = await get_full_client_warmup_data_bitcoinonly()
            for c in new_connections:
                await asyncio.gather(
                    *[
                        c.put(send_sse_message(SSE.SYSTEM_INFO, res[0].dict())),
                        c.put(send_sse_message(SSE.BTC_INFO, res[1].dict())),
                        c.put(send_sse_message(SSE.INSTALLED_APP_STATUS, res[2])),
                        c.put(send_sse_message(SSE.HARDWARE_INFO, res[3])),
                    ]
                )

        new_connections.clear()

    if (
        api_startup_status.bitcoin == StartupState.DONE
        and api_startup_status.lightning != StartupState.DONE
    ):
        res = await get_bitcoin_client_warmup_data()
        for c in new_connections:
            await asyncio.gather(
                *[
                    c.put(send_sse_message(SSE.BTC_INFO, res[0].dict())),
                    c.put(send_sse_message(SSE.HARDWARE_INFO, res[1])),
                ]
            )

        # don't clear new_connections, we'll try again later when api is initialized

    if (
        api_startup_status.bitcoin != StartupState.DONE
        and api_startup_status.lightning != StartupState.DONE
    ):
        # send only the most minimal available data without Bitcoin Core and Lightning running
        res = await get_hardware_info()
        for c in new_connections:
            await c.put(send_sse_message(SSE.HARDWARE_INFO, res)),

        # don't clear new_connections, we'll try again later when api is initialized

    warmup_running = False


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


register_handlers_finished = False


async def register_all_handlers():
    global register_handlers_finished

    if register_handlers_finished:
        raise RuntimeError("register_all_handlers() must not be called twice.")

    await register_hardware_info_gatherer()

    loop = asyncio.get_event_loop()
    loop.create_task(broadcast_data_sse())
    register_handlers_finished = True


# TODO: Add a SSE manager class that handles all connections and
#       sending of messages. Currently functions are distributed
#       between main.py and utils.py with cross calls
async def broadcast_data_sse():
    while True:
        try:
            async with async_timeout.timeout(1):
                message = await sse_queue.get()
                if message is not None:
                    for k in connections.keys():
                        if connections.get(k):
                            await connections.get(k).put(message)
                await asyncio.sleep(0.01)
        except asyncio.TimeoutError:
            pass
