import asyncio
import logging

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

from app.auth.auth_bearer import JWTBearer
from app.auth.auth_handler import (
    handle_local_cookie,
    register_cookie_updater,
    remove_local_cookie,
)
from app.external.fastapi_versioning import VersionedFastAPI
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
from app.utils import SSE, broadcast_sse_msg, build_sse_event, sse_mgr

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
    await broadcast_sse_msg(SSE.SYSTEM_STARTUP_INFO, api_startup_status.dict())

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
    await broadcast_sse_msg(SSE.SYSTEM_STARTUP_INFO, api_startup_status.dict())


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


new_connections = []


def _send_sse_event(id, event, data):
    return sse_mgr.send_to_single(id, build_sse_event(event, data))


@app.get(
    "/sse/subscribe",
    status_code=status.HTTP_200_OK,
)
async def stream(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        # No token in cookies found, try to get it from the Authorization header
        token = request.headers.get("authorization").replace("Bearer ", "")

    if not token or not JWTBearer().verify_jwt(jwtoken=token):
        # Raise an exception if no token is found or the token is invalid
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No or invalid authorization code.",
        )

    event_source, id = sse_mgr.add_connection(request)
    new_connections.append(id)

    await _send_sse_event(
        id, SSE.SYSTEM_STARTUP_INFO, jsonable_encoder(api_startup_status.dict())
    )

    loop = asyncio.get_event_loop()
    loop.create_task(warmup_new_connections())

    return event_source


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
            for id in new_connections:
                await asyncio.gather(
                    *[
                        _send_sse_event(id, SSE.SYSTEM_INFO, res[0].dict()),
                        _send_sse_event(id, SSE.BTC_INFO, res[1].dict()),
                        _send_sse_event(id, SSE.LN_INFO, res[2].dict()),
                        _send_sse_event(id, SSE.LN_INFO_LITE, res[3].dict()),
                        _send_sse_event(id, SSE.LN_FEE_REVENUE, res[4]),
                        _send_sse_event(id, SSE.WALLET_BALANCE, res[5].dict()),
                        _send_sse_event(id, SSE.HARDWARE_INFO, res[6]),
                    ]
                )

        # when its bitcoin only
        else:

            res = await get_full_client_warmup_data_bitcoinonly()
            for id in new_connections:
                await asyncio.gather(
                    *[
                        _send_sse_event(id, SSE.SYSTEM_INFO, res[0].dict()),
                        _send_sse_event(id, SSE.BTC_INFO, res[1].dict()),
                        _send_sse_event(id, SSE.HARDWARE_INFO, res[2]),
                    ]
                )

        new_connections.clear()

    if (
        api_startup_status.bitcoin == StartupState.DONE
        and api_startup_status.lightning != StartupState.DONE
    ):
        res = await get_bitcoin_client_warmup_data()
        for id in new_connections:
            await asyncio.gather(
                *[
                    _send_sse_event(id, SSE.BTC_INFO, res[0].dict()),
                    _send_sse_event(id, SSE.HARDWARE_INFO, res[1]),
                ]
            )

        # don't clear new_connections, we'll try again later when api is initialized

    if (
        api_startup_status.bitcoin != StartupState.DONE
        and api_startup_status.lightning != StartupState.DONE
    ):
        # send only the most minimal available data without Bitcoin Core and Lightning running
        res = await get_hardware_info()
        for id in new_connections:
            await _send_sse_event(id, SSE.HARDWARE_INFO, res),

        # don't clear new_connections, we'll try again later when api is initialized

    warmup_running = False


register_handlers_finished = False


async def register_all_handlers():
    global register_handlers_finished

    if register_handlers_finished:
        raise RuntimeError("register_all_handlers() must not be called twice.")

    await register_hardware_info_gatherer()

    register_handlers_finished = True
