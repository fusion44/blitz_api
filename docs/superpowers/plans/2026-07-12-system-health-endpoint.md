# System Health Endpoint Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the stubbed `GET /system/health` into a real, unauthenticated availability/readiness endpoint driven by the existing startup state.

**Architecture:** Hoist the in-process `api_startup_status` singleton into a shared module (breaks a circular import), compute health in one pure platform-independent function `build_health_info`, wire it through the service + router (unauthenticated, 503-when-unhealthy), drop the now-dead per-backend `get_system_health`, and regenerate the committed `openapi.json`.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic v2, pytest, jujutsu (jj) for commits.

## Global Constraints

- Endpoint is `GET /system/health`, **unauthenticated** — no `dependencies=[Depends(JWTBearer())]`.
- `healthy` (top level) = `api_startup_status.is_fully_initialized()` (bitcoin `DONE` and lightning `DONE` or `DISABLED`).
- HTTP status: **200** when `healthy`, **503** when not. The handler **sets** `response.status_code`; it never raises — so the 503 body stays a `SystemHealthInfo`, never an `ErrorMessage`.
- `verbose` only controls whether `subsystems` is populated; status code / `healthy` / `message` are identical either way.
- `subsystems`, when present, is exactly three entries in this order: `api`, `bitcoind`, `lightning`.
- `api` → always `healthy: true`. `bitcoind` → `healthy` iff `DONE`. `lightning` → `healthy` iff `DONE` or `DISABLED`; `DISABLED` reports `healthy: true, message: "disabled"`.
- Non-`DONE`, non-`DISABLED` subsystem `message` = the lowercased state value, and `"<state>: <msg>"` when the corresponding `*_msg` is non-empty.
- Top-level `message` = `""` when healthy; when unhealthy, `"<subsystem> not ready: <state>"` for the first not-ready subsystem, bitcoind checked before lightning.
- The subsystem model field is named **`healthy`** (rename from `health`).
- No new config vars. No WebUI change. No live/deep RPC probe.
- Commit with **jj using explicit paths only** (never bare `jj commit`). Every commit message ends with:
  `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`
- Run tests via: `cd /home/f44/dev/blitz/base/api && devenv shell -- bash -c 'uv run python -m pytest <args>'`.

---

### Task 1: Hoist `api_startup_status` into a shared module

**Files:**
- Create: `app/api/startup_status.py`
- Modify: `app/main.py` (remove the local `api_startup_status` definition at line 197; add an import; drop the now-unused `ApiStartupStatus` name from the models import at line 19)
- Test: `tests/test_startup_status.py`

**Interfaces:**
- Consumes: `ApiStartupStatus` from `app.api.models`.
- Produces: `app.api.startup_status.api_startup_status` — the single shared `ApiStartupStatus` instance the whole app reads/mutates.

**Why:** `api_startup_status` currently lives in `app/main.py`, which imports `app.system.router`. The health service (Task 3) must read it from `app/system/`, which would create a cycle. Moving the singleton to a leaf module (`app.api.startup_status`, which depends only on `app.api.models`) breaks the cycle with no behavior change.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_startup_status.py
def test_main_uses_the_shared_singleton():
    import app.main as main
    from app.api.startup_status import api_startup_status

    # main must read/mutate the exact same object, not its own copy
    assert main.api_startup_status is api_startup_status
```

- [ ] **Step 2: Run test to verify it fails**

Run: `devenv shell -- bash -c 'uv run python -m pytest tests/test_startup_status.py -q'`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.api.startup_status'`.

- [ ] **Step 3: Create the shared module**

```python
# app/api/startup_status.py
from app.api.models import ApiStartupStatus

# Single in-process source of truth for bitcoin/lightning startup state.
# Mutated by the startup tasks in app.main; read by the /system/health endpoint
# and the WebSocket warmup. Kept in this leaf module so app.system can import it
# without a circular dependency on app.main.
api_startup_status = ApiStartupStatus()
```

- [ ] **Step 4: Rewire `app/main.py`**

Remove the standalone definition (currently `app/main.py:197`):
```python
api_startup_status = ApiStartupStatus()
```

Add an import next to the other `app.api.*` imports (near `app/main.py:17-20`):
```python
from app.api.startup_status import api_startup_status
```

Drop the now-unused `ApiStartupStatus` from the models import (currently `app/main.py:19`), changing:
```python
from app.api.models import ApiErrors, ApiStartupStatus, StartupState
```
to:
```python
from app.api.models import ApiErrors, StartupState
```
Leave every other `api_startup_status.<...>` reference in `main.py` untouched — they now operate on the imported shared object.

- [ ] **Step 5: Run the test to verify it passes**

Run: `devenv shell -- bash -c 'uv run python -m pytest tests/test_startup_status.py -q'`
Expected: PASS (1 passed).

- [ ] **Step 6: Run the full suite (no behavior change)**

Run: `devenv shell -- bash -c 'uv run python -m pytest -q'`
Expected: all pass (previous count was 125, now 126 with the new test).

- [ ] **Step 7: Commit**

```bash
jj commit app/api/startup_status.py app/main.py tests/test_startup_status.py -m "refactor(api): hoist api_startup_status into a shared leaf module

Move the in-process startup-state singleton out of app.main into
app.api.startup_status so app.system can read it without a circular
import. No behavior change - main mutates the same shared object.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: Pure `build_health_info` + model rename

**Files:**
- Create: `app/system/health.py`
- Modify: `app/system/models.py` (rename `SubSystemHealthInfo.health` → `healthy`; switch the two health models' fields from `Query(...)` to `Field(...)`)
- Test: `tests/test_system_health.py`

**Interfaces:**
- Consumes: `ApiStartupStatus`, `StartupState` from `app.api.models`; `SystemHealthInfo`, `SubSystemHealthInfo` from `app.system.models`.
- Produces: `build_health_info(status: ApiStartupStatus, verbose: bool) -> SystemHealthInfo`.

- [ ] **Step 1: Rename the model field and switch to `Field`**

In `app/system/models.py`, add `Field` to the pydantic import (currently `from pydantic import BaseModel`):
```python
from pydantic import BaseModel, Field
```
Replace the two model classes (currently `app/system/models.py:129-142`) with:
```python
class SubSystemHealthInfo(BaseModel):
    name: str = Field(..., description="Name of the subsystem")
    healthy: bool = Field(..., description="Whether this subsystem is healthy or not")
    message: str = Field(
        "", description="Optional message describing the subsystem's health"
    )


class SystemHealthInfo(BaseModel):
    healthy: bool = Field(
        ..., description="Whether the API and all its subsystems are ready"
    )
    message: str = Field("", description="Set to a reason string when not healthy")
    subsystems: list[SubSystemHealthInfo] = Field(
        [], description="Per-subsystem health; populated only when verbose=true"
    )
```
Leave the `from fastapi import Query` import in place — other models in this file still use `Query`.

- [ ] **Step 2: Write the failing tests**

```python
# tests/test_system_health.py
from app.api.models import ApiStartupStatus, StartupState
from app.system.health import build_health_info


def _names(info):
    return [s.name for s in info.subsystems]


def _by_name(info, name):
    return next(s for s in info.subsystems if s.name == name)


def test_all_ready_is_healthy_no_subsystems_without_verbose():
    status = ApiStartupStatus(
        bitcoin=StartupState.DONE, lightning=StartupState.DONE
    )
    info = build_health_info(status, verbose=False)
    assert info.healthy is True
    assert info.message == ""
    assert info.subsystems == []


def test_verbose_lists_three_subsystems_in_order():
    status = ApiStartupStatus(
        bitcoin=StartupState.DONE, lightning=StartupState.DONE
    )
    info = build_health_info(status, verbose=True)
    assert _names(info) == ["api", "bitcoind", "lightning"]
    assert _by_name(info, "api").healthy is True
    assert _by_name(info, "bitcoind").healthy is True
    assert _by_name(info, "lightning").healthy is True


def test_bitcoin_bootstrapping_is_unhealthy():
    status = ApiStartupStatus(
        bitcoin=StartupState.BOOTSTRAPPING, lightning=StartupState.DONE
    )
    info = build_health_info(status, verbose=True)
    assert info.healthy is False
    assert info.message == "bitcoind not ready: bootstrapping"
    assert _by_name(info, "bitcoind").healthy is False
    assert _by_name(info, "bitcoind").message == "bootstrapping"


def test_bitcoin_message_is_appended_when_present():
    status = ApiStartupStatus(
        bitcoin=StartupState.BOOTSTRAPPING,
        bitcoin_msg="syncing headers",
        lightning=StartupState.DONE,
    )
    info = build_health_info(status, verbose=True)
    assert _by_name(info, "bitcoind").message == "bootstrapping: syncing headers"


def test_lightning_disabled_is_healthy_on_bitcoin_only_node():
    status = ApiStartupStatus(
        bitcoin=StartupState.DONE, lightning=StartupState.DISABLED
    )
    info = build_health_info(status, verbose=True)
    assert info.healthy is True
    ln = _by_name(info, "lightning")
    assert ln.healthy is True
    assert ln.message == "disabled"


def test_lightning_locked_is_unhealthy():
    status = ApiStartupStatus(
        bitcoin=StartupState.DONE, lightning=StartupState.LOCKED
    )
    info = build_health_info(status, verbose=True)
    assert info.healthy is False
    assert info.message == "lightning not ready: locked"
    assert _by_name(info, "lightning").healthy is False
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `devenv shell -- bash -c 'uv run python -m pytest tests/test_system_health.py -q'`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.system.health'`.

- [ ] **Step 4: Implement `build_health_info`**

```python
# app/system/health.py
from app.api.models import ApiStartupStatus, StartupState
from app.system.models import SubSystemHealthInfo, SystemHealthInfo


def _state_message(state: StartupState, msg: str | None) -> str:
    if msg:
        return f"{state.value}: {msg}"
    return state.value


def _bitcoind_subsystem(status: ApiStartupStatus) -> SubSystemHealthInfo:
    if status.bitcoin == StartupState.DONE:
        return SubSystemHealthInfo(name="bitcoind", healthy=True, message="")
    return SubSystemHealthInfo(
        name="bitcoind",
        healthy=False,
        message=_state_message(status.bitcoin, status.bitcoin_msg),
    )


def _lightning_subsystem(status: ApiStartupStatus) -> SubSystemHealthInfo:
    if status.lightning == StartupState.DISABLED:
        return SubSystemHealthInfo(name="lightning", healthy=True, message="disabled")
    if status.lightning == StartupState.DONE:
        return SubSystemHealthInfo(name="lightning", healthy=True, message="")
    return SubSystemHealthInfo(
        name="lightning",
        healthy=False,
        message=_state_message(status.lightning, status.lightning_msg),
    )


def build_health_info(status: ApiStartupStatus, verbose: bool) -> SystemHealthInfo:
    """Build the SystemHealthInfo from the current startup state.

    Pure and synchronous: healthy == status.is_fully_initialized(). The `api`
    subsystem is always healthy (a response proves the API is alive).
    """
    healthy = status.is_fully_initialized()

    message = ""
    if not healthy:
        if status.bitcoin != StartupState.DONE:
            message = f"bitcoind not ready: {status.bitcoin.value}"
        else:
            message = f"lightning not ready: {status.lightning.value}"

    subsystems: list[SubSystemHealthInfo] = []
    if verbose:
        subsystems = [
            SubSystemHealthInfo(name="api", healthy=True, message=""),
            _bitcoind_subsystem(status),
            _lightning_subsystem(status),
        ]

    return SystemHealthInfo(healthy=healthy, message=message, subsystems=subsystems)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `devenv shell -- bash -c 'uv run python -m pytest tests/test_system_health.py -q'`
Expected: PASS (6 passed).

- [ ] **Step 6: Commit**

```bash
jj commit app/system/health.py app/system/models.py tests/test_system_health.py -m "feat(api): add pure build_health_info + rename subsystem field to healthy

build_health_info maps the startup state to SystemHealthInfo (platform
independent, pure, synchronous). Rename SubSystemHealthInfo.health ->
healthy to match the top level, and switch the two health models from
the misused Query() to Field().

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: Wire into the service + router (unauthenticated, 503); drop dead backend method

**Files:**
- Modify: `app/system/service.py` (rewrite `system_health`; add imports)
- Modify: `app/system/router.py` (drop auth, set 503, update docs, add `response_model`/`responses`)
- Modify: `app/system/impl/system_base.py` (remove abstract `get_system_health` + unused `SystemHealthInfo` import if now unused)
- Modify: `app/system/impl/native_python.py` (remove `get_system_health` + unused `SystemHealthInfo` import if now unused)
- Modify: `app/system/impl/raspiblitz.py` (remove `get_system_health` + unused `SystemHealthInfo` import if now unused)
- Test: `tests/routers/test_system.py`

**Interfaces:**
- Consumes: `build_health_info` from `app.system.health`; `api_startup_status` from `app.api.startup_status`.
- Produces: `system_health(verbose: bool) -> SystemHealthInfo` (now reads shared state, no backend delegation); the unauthenticated `GET /system/health` route.

- [ ] **Step 1: Write the failing route tests**

Append to `tests/routers/test_system.py` (keep the existing imports/test; add these):
```python
import app.main as main
from app.api.models import StartupState


def _set_status(bitcoin, lightning):
    main.api_startup_status.bitcoin = bitcoin
    main.api_startup_status.lightning = lightning


def test_health_is_unauthenticated_and_200_when_ready():
    _set_status(StartupState.DONE, StartupState.DONE)
    # no `with`: don't start lifespan/background tasks
    c = TestClient(main.app)
    resp = c.get("/system/health")  # no Authorization header
    assert resp.status_code == 200
    body = resp.json()
    assert body["healthy"] is True
    assert body["subsystems"] == []


def test_health_503_when_not_ready_body_is_health_info():
    _set_status(StartupState.BOOTSTRAPPING, StartupState.DONE)
    c = TestClient(main.app)
    resp = c.get("/system/health")
    assert resp.status_code == 503
    body = resp.json()
    # body is a SystemHealthInfo, NOT an ErrorMessage
    assert body["healthy"] is False
    assert "error_code" not in body
    assert body["message"] == "bitcoind not ready: bootstrapping"


def test_health_verbose_lists_subsystems():
    _set_status(StartupState.DONE, StartupState.DONE)
    c = TestClient(main.app)
    resp = c.get("/system/health?verbose=true")
    assert resp.status_code == 200
    names = [s["name"] for s in resp.json()["subsystems"]]
    assert names == ["api", "bitcoind", "lightning"]
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `devenv shell -- bash -c 'uv run python -m pytest tests/routers/test_system.py -q'`
Expected: FAIL — health currently requires JWT (`test_health_is_unauthenticated_and_200_when_ready` gets 403), and the stub always returns `healthy=True` with a 200 (so the 503 test fails).

- [ ] **Step 3: Rewrite the service function**

In `app/system/service.py`, add imports near the other `app.*` imports (top of file):
```python
from app.api.startup_status import api_startup_status
from app.system.health import build_health_info
```
Replace the existing `system_health` (currently `app/system/service.py:59-65`) with:
```python
async def system_health(verbose: bool) -> SystemHealthInfo:
    # Readiness is platform independent: read the shared startup state directly.
    return build_health_info(api_startup_status, verbose)
```
(Keep the existing `SystemHealthInfo` import in `service.py` — it is still used in the return annotation.)

- [ ] **Step 4: Update the router**

In `app/system/router.py`, replace the `/health` route (currently `app/system/router.py:137-149`) with:
```python
@router.get(
    "/health",
    name=f"{_PREFIX}.health",
    summary="Returns info about the system's health",
    response_model=SystemHealthInfo,
    responses={503: {"description": "One or more subsystems are not ready"}},
)
async def get_system_health(
    response: Response,
    verbose: bool = Query(
        False,
        description="If true, include a per-subsystem (api, bitcoind, lightning) health breakdown.",
    ),
) -> SystemHealthInfo:
    result = await system_health(verbose)
    if not result.healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return result
```
Note: the JWT dependency is removed. `Response` and `status` are already imported (`app/system/router.py:1`); leave the `Depends`/`JWTBearer` imports in place (other routes still use them).

- [ ] **Step 5: Remove the dead backend method**

The service no longer delegates to the backend, so remove the abstract method and both stubs.

In `app/system/impl/system_base.py`, delete (currently lines 20-22):
```python
    @abstractmethod
    async def get_system_health(self, verbose: bool) -> SystemHealthInfo:
        raise NotImplementedError()
```
In `app/system/impl/native_python.py`, delete (currently lines 58-60):
```python
    @logger.catch(exclude=(HTTPException,))
    async def get_system_health(self, verbose: bool) -> SystemHealthInfo:
        return SystemHealthInfo(healthy=True)
```
In `app/system/impl/raspiblitz.py`, delete (currently lines 108-109):
```python
    async def get_system_health(self, verbose: bool) -> SystemHealthInfo:
        return SystemHealthInfo(healthy=True)
```
Then, in each of those three files, check whether `SystemHealthInfo` is still referenced:
```bash
grep -n "SystemHealthInfo" app/system/impl/system_base.py app/system/impl/native_python.py app/system/impl/raspiblitz.py
```
For any file where the only remaining hit is the import line, remove `SystemHealthInfo` from that file's `from app.system.models import (...)` import.

- [ ] **Step 6: Run the system tests, then the full suite**

Run: `devenv shell -- bash -c 'uv run python -m pytest tests/routers/test_system.py -q'`
Expected: PASS (existing auth test + the three new health tests).

Run: `devenv shell -- bash -c 'uv run python -m pytest -q'`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
jj commit app/system/service.py app/system/router.py app/system/impl/system_base.py app/system/impl/native_python.py app/system/impl/raspiblitz.py tests/routers/test_system.py -m "feat(api): implement GET /system/health readiness endpoint (#145)

Make /system/health unauthenticated, compute real readiness from the
shared startup state via build_health_info, and return 503 (body still a
SystemHealthInfo) when a subsystem is not ready. Drop the now-dead
per-backend get_system_health delegation.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: Regenerate the committed `openapi.json`

**Files:**
- Modify: `openapi.json` (generated artifact)

**Why:** `openapi.json` is committed and used to generate client libraries. The route is now unauthenticated, its `verbose` description changed, it declares a 503 response, and the `SubSystemHealthInfo.health` field was renamed to `healthy` — all must be reflected.

- [ ] **Step 1: Regenerate `openapi.json`**

This mirrors the spec-writing half of `gen_client_libs.py` (the v1 sub-app selection + `get_openapi` + `json.dump`) without running the external client generators.

Run:
```bash
cd /home/f44/dev/blitz/base/api && devenv shell -- bash -c 'uv run python - <<PY
import importlib, json
from fastapi.openapi.utils import get_openapi

app = importlib.import_module("app.main").app
for route in app.router.routes:
    if "v1" in route.path:
        app = route.app
        break

specs = get_openapi(
    title=app.title or None,
    version=app.version or None,
    openapi_version=app.openapi_version or None,
    description=app.description or None,
    routes=app.routes or None,
)
with open("openapi.json", "w") as f:
    json.dump(specs, f, indent=2)
print("wrote openapi.json")
PY'
```
Expected: prints `wrote openapi.json`.

- [ ] **Step 2: Verify the health path reflects the changes**

Run:
```bash
cd /home/f44/dev/blitz/base/api && devenv shell -- bash -c 'uv run python - <<PY
import json
spec = json.load(open("openapi.json"))
health = spec["paths"]["/system/health"]["get"]
assert "security" not in health, "health must be unauthenticated (no security)"
assert "503" in health["responses"], "503 must be documented"
sub = spec["components"]["schemas"]["SubSystemHealthInfo"]["properties"]
assert "healthy" in sub and "health" not in sub, "field must be renamed to healthy"
print("openapi.json health endpoint OK")
PY'
```
Expected: prints `openapi.json health endpoint OK`.

- [ ] **Step 3: Commit**

```bash
jj commit openapi.json -m "chore(api): regenerate openapi.json for the health endpoint (#145)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Self-Review

- **Spec coverage:** unauthenticated GET (Task 3) ✓; readiness from `api_startup_status` via `is_fully_initialized` (Task 2 `build_health_info`) ✓; 200/503 with `SystemHealthInfo` body, never raised (Task 3 router) ✓; verbose subsystem breakdown, order api/bitcoind/lightning (Task 2) ✓; DISABLED lightning → healthy (Task 2) ✓; top-level message rule (Task 2) ✓; field rename `health`→`healthy` + `Query`→`Field` (Task 2) ✓; circular-import hoist (Task 1) ✓; drop dead backend delegation (Task 3) ✓; regenerate openapi.json (Task 4) ✓; pure-function + route tests (Tasks 2, 3) ✓.
- **Type consistency:** `build_health_info(status: ApiStartupStatus, verbose: bool) -> SystemHealthInfo` produced in Task 2 and consumed identically in Task 3; `api_startup_status` produced in Task 1 and consumed in Task 3; `SubSystemHealthInfo.healthy` used consistently across Tasks 2, 3, 4.
- **Placeholders:** none — every code step shows complete code; the openapi.json step shows the exact regeneration + verification commands (the file content itself is a generated artifact, not hand-authored).
