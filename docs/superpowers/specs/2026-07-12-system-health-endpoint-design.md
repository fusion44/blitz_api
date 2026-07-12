# Design: Availability / health-check endpoint

- **Issue:** blitz_api#145 (add an availability / health check)
- **Date:** 2026-07-12
- **Repo:** `api` (blitz_api, FastAPI)

## Goal & current state

Give developers, uptime monitors, container liveness probes, and the WebUI a
cheap, always-reachable way to ask "is the blitz API there, and are its
subsystems ready?"

`GET /system/health` **already exists** but is a stub (`app/system/router.py`):
it is JWT-protected, its `verbose` flag is a documented no-op, and both backends
just `return SystemHealthInfo(healthy=True)`. The response models already exist
too (`app/system/models.py`): `SystemHealthInfo{healthy, message, subsystems}`
and `SubSystemHealthInfo{name, health, message}`. So this work **implements the
stub properly** and fixes two design flaws (it must be unauthenticated, and its
health signal must be real), rather than building from scratch.

## The contract

**Endpoint:** `GET /system/health` — pure GET, no body, no secrets,
**unauthenticated** (drop the JWT dependency; precedent: `GET /setup/status`).

**Source of truth:** the in-process `api_startup_status` singleton (bitcoin +
lightning `StartupState` ∈ `offline / bootstrapping / locked / done / disabled`).
No RPC calls — reading it is instant and cannot hang, and it is the exact state
the WebSocket already pushes to the UI, so the endpoint and the live UI never
disagree.

**Top-level `healthy`** = `api_startup_status.is_fully_initialized()`, i.e.
`bitcoin == DONE` **and** (`lightning == DONE` **or** `DISABLED`). The `api`
subsystem is implicitly always healthy — a response at all proves the API is
alive.

| condition | HTTP status | `healthy` | `message` |
|---|---|---|---|
| all ready | **200** | `true` | `""` |
| any subsystem not ready | **503** | `false` | e.g. `"bitcoind not ready: bootstrapping"` |

Status code, `healthy`, and `message` are **identical regardless of `verbose`**.
`verbose` only controls whether the `subsystems` array is populated.

**Top-level `message`** is `""` when healthy. When unhealthy it names the first
not-ready subsystem in check order (bitcoind before lightning) as
`"<subsystem> not ready: <state>"` — e.g. `"bitcoind not ready: bootstrapping"`.

**Subsystem mapping (verbose):** three entries, in order — `api`, `bitcoind`,
`lightning`.
- `api` → always `healthy: true`, `message: ""`.
- `bitcoind` → `healthy` iff state `DONE`; else `healthy: false`, `message` = the
  state (`offline` / `bootstrapping` / `locked`), appended with `bitcoin_msg`
  when non-empty (`"bootstrapping: <msg>"`).
- `lightning` → `healthy` iff `DONE` **or** `DISABLED`. `DISABLED` reports
  `healthy: true, message: "disabled"` (so a bitcoin-only node is fully
  healthy). Other non-`DONE` states report `healthy: false`, `message` = the
  state, appended with `lightning_msg` when non-empty.

```
GET /system/health              → 200  {"healthy": true, "message": ""}
GET /system/health?verbose=true → 200  {"healthy": true, "message": "",
                                        "subsystems": [api, bitcoind, lightning]}
# during startup: 503, healthy=false (body is still SystemHealthInfo)
```

## Architecture & refactor

Readiness comes entirely from `api_startup_status` — identical on every platform
— so the current delegation into the `native_python` / `raspiblitz` backends
only duplicates logic. The logic is pulled out to one platform-independent unit.

- **New `app/system/health.py`** — one pure function
  `build_health_info(status: ApiStartupStatus, verbose: bool) -> SystemHealthInfo`.
  All of the Section-above mapping lives here. Pure and synchronous → unit-tested
  with zero mocking and no TestClient.
- **`app/system/service.py`** — `system_health(verbose)` reads the shared status
  and returns `build_health_info(...)`; no more `await system.get_system_health`.
- **Remove** the now-dead `get_system_health` from `app/system/impl/system_base.py`
  (abstract), `native_python.py`, and `raspiblitz.py`. (Reintroducible later if an
  opt-in deep RPC probe is ever added — YAGNI now.)

**Break the circular import.** `api_startup_status` currently lives in
`app/main.py`, which imports `system_router`, so `system/` cannot import back
without a cycle. Hoist the singleton into a tiny **new `app/api/startup_status.py`**:

```python
from app.api.models import ApiStartupStatus

api_startup_status = ApiStartupStatus()
```

`app/main.py` imports it from there (its startup setter keeps mutating the same
shared object — no behavior change); `app/system/service.py` imports it too. No
cycle (`startup_status.py` depends only on `app.api.models`, which imports
neither `main` nor `system`).

**Router (`app/system/router.py`).**
- Drop `dependencies=[Depends(JWTBearer())]` → unauthenticated.
- Inject `response: Response`; set `response.status_code = 503` when
  `not result.healthy` (this keeps `response_model` serialization + OpenAPI
  intact, and — crucially — does **not** raise, so the error-normalization
  handlers never touch the 503 body).
- Update the `verbose` description (no longer "not implemented") and add
  `responses={503: {"description": "One or more subsystems are not ready"}}`.

**Model (`app/system/models.py`).** Rename `SubSystemHealthInfo.health` →
`healthy` (matches the top level and fusion44's own example; verified no
consumers exist in `api` or `web`). While there, switch these response-model
fields from the misused `Query(...)` to `Field(...)`.

**`openapi.json`** is committed and used to generate client libraries —
regenerate it after the route/model changes.

## Testing

**Pure-function unit tests (`tests/system/test_health.py`)** — the bulk of
coverage, no TestClient, no mocking:
- fully initialized (bitcoin `DONE`, lightning `DONE`) → `healthy=true`,
  `message=""`, `subsystems=[]` when `verbose=false`.
- `verbose=true` → exactly three subsystems (`api`, `bitcoind`, `lightning`)
  with correct `healthy`/`message` each.
- bitcoin `BOOTSTRAPPING` → `healthy=false`, message names bitcoind; verbose
  shows `bitcoind.healthy=false`.
- lightning `DISABLED` on a `DONE` bitcoin (bitcoin-only node) → top-level
  `healthy=true`, `lightning.healthy=true, message="disabled"`.
- lightning `LOCKED` → `healthy=false`.

**Route tests (`tests/routers/test_system.py`)** — `TestClient(main.app)`
constructed **without** `with` (so `lifespan`/background init never starts),
monkeypatching the shared `api_startup_status`:
- unauthenticated `GET /system/health` → **200** with no token (proves the JWT
  dependency is gone).
- unhealthy state → **503**, and the body is still a `SystemHealthInfo`
  (not an `ErrorMessage` — the status code is set, not raised).
- `?verbose=true` populates `subsystems`.

## Out of scope / follow-ups

- **No WebUI change** — nothing consumes `SystemHealthInfo` yet. A pre-login
  "is the API reachable" ping could use it later.
- **No deep / live RPC probe** — opt-in future addition; the abstract backend
  seam can be reintroduced then.
- **No new config.**
