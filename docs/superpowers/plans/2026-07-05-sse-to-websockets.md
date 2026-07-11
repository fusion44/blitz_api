# SSE → WebSocket Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Server-Sent-Events realtime channel with an authenticated WebSocket channel across `blitz_api` (FastAPI) and `raspiblitz-web` (React), removing SSE entirely.

**Architecture:** A single `/ws` endpoint pushes `{event, data}` JSON frames to authenticated clients. Auth is a first-message handshake (`{type:"auth", token}`). A `WebSocketManager` tracks authed sockets and fans out broadcasts. The WebUI connects a `WebSocket`, authenticates on open, dispatches frames into the existing realtime context, and reconnects with backoff. Same ~20 events and payloads as today — only the transport changes.

**Tech Stack:** Python 3.12 / FastAPI 0.139 / Starlette 1.3 / pytest (`TestClient.websocket_connect`); React 19 / TypeScript / Vitest; `ws` (Node) for the backend-mock.

## Global Constraints

- Event string values are **unchanged** from today's SSE enum (`btc_info`, `ln_info`, `hardware_info`, `system_startup_info`, `app_state_update_message`, …). Only the transport/envelope changes.
- Envelope (server→client): `{"event": "<name>", "data": <payload>}`, JSON text frame.
- Auth: first-message `{"type":"auth","token":"<jwt>"}`; validate via `JWTBearer().verify_jwt(token)`; close `4401` on invalid/missing, `4408` on ≤5s timeout.
- Server→client only. No inbound commands. Actions stay on REST.
- API runs from `api/`; tests run via `devenv shell -- bash -c 'uv run python -m pytest ...'`. WebUI runs from `web/`; tests via `npm test`.
- Commit style: conventional commits, trailer `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`. Repos use `jj`; `jj commit <paths> -m "..."`.
- API repo and WebUI repo must be merged/deployed together (clean cut).

---

## Phase 1 — API (`api/`)

### File Structure (Phase 1)

- Create: `app/api/ws_manager.py` — `WebSocketManager` (connection registry, auth handshake, send/broadcast). One responsibility: own the WS connections.
- Modify: `app/api/utils.py` — replace `sse_mgr`/`build_sse_event`/`broadcast_sse_msg` with `ws_mgr`/`broadcast_msg`; rename `SSE` enum → `Event`.
- Modify: `app/main.py` — replace `/sse/subscribe` with `/ws`; port warmup helpers to WS.
- Modify (mechanical rename `SSE.`→`Event.`, `broadcast_sse_msg`→`broadcast_msg`): `app/lightning/service.py`, `app/apps/tasks_impl/listeners.py`, `app/bitcoind/service.py`, `app/lightning/impl/cln_grpc.py`, `app/lightning/impl/lnd_grpc.py`, `app/lightning/impl/cln_jrpc.py`, `app/system/service.py`, `app/system/impl/raspiblitz.py`.
- Delete: `app/api/sse_manager.py`, `app/external/sse_starlette/`.
- Test: `tests/test_ws_manager.py`, `tests/test_ws_endpoint.py`.

---

### Task 1: `WebSocketManager` — auth handshake + registry

**Files:**
- Create: `app/api/ws_manager.py`
- Test: `tests/test_ws_manager.py`

**Interfaces:**
- Produces:
  - `class WebSocketManager` with:
    - `async connect(self, websocket) -> tuple[int | None, bool]` — accepts, runs auth handshake, registers on success. Returns `(id, authed)`; `(None, False)` when auth fails/times out (socket already closed).
    - `async send_to_single(self, id: int, event: str, data) -> None`
    - `async broadcast_to_all(self, event: str, data) -> None`
    - `def disconnect(self, id: int) -> None`
  - module singleton `ws_mgr = WebSocketManager()`
  - `AUTH_TIMEOUT_SECONDS = 5`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ws_manager.py
import asyncio
import json

import pytest

from app.api.ws_manager import WebSocketManager


class FakeWebSocket:
    """Minimal stand-in for starlette WebSocket."""

    def __init__(self, incoming=None):
        self.accepted = False
        self.closed_code = None
        self.sent = []
        self._incoming = list(incoming or [])

    async def accept(self):
        self.accepted = True

    async def receive_text(self):
        if not self._incoming:
            # emulate a client that never sends -> block until cancelled
            await asyncio.sleep(3600)
        return self._incoming.pop(0)

    async def send_text(self, text):
        self.sent.append(text)

    async def close(self, code=1000):
        self.closed_code = code


async def test_valid_auth_registers_and_can_receive(monkeypatch):
    monkeypatch.setattr(
        "app.api.ws_manager.JWTBearer",
        lambda: type("B", (), {"verify_jwt": lambda self, jwtoken: True})(),
    )
    mgr = WebSocketManager()
    ws = FakeWebSocket([json.dumps({"type": "auth", "token": "good"})])

    id_, authed = await mgr.connect(ws)

    assert authed is True
    assert id_ is not None
    assert ws.accepted is True
    await mgr.send_to_single(id_, "btc_info", {"blocks": 1})
    assert json.loads(ws.sent[0]) == {"event": "btc_info", "data": {"blocks": 1}}


async def test_invalid_token_closes_4401(monkeypatch):
    monkeypatch.setattr(
        "app.api.ws_manager.JWTBearer",
        lambda: type("B", (), {"verify_jwt": lambda self, jwtoken: False})(),
    )
    mgr = WebSocketManager()
    ws = FakeWebSocket([json.dumps({"type": "auth", "token": "bad"})])

    id_, authed = await mgr.connect(ws)

    assert authed is False
    assert id_ is None
    assert ws.closed_code == 4401


async def test_auth_timeout_closes_4408(monkeypatch):
    monkeypatch.setattr("app.api.ws_manager.AUTH_TIMEOUT_SECONDS", 0.05)
    mgr = WebSocketManager()
    ws = FakeWebSocket([])  # never sends

    id_, authed = await mgr.connect(ws)

    assert authed is False
    assert ws.closed_code == 4408
```

- [ ] **Step 2: Run test to verify it fails**

Run: `devenv shell -- bash -c 'uv run python -m pytest tests/test_ws_manager.py -q'`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.api.ws_manager'`

- [ ] **Step 3: Write minimal implementation**

```python
# app/api/ws_manager.py
import asyncio
import json

from fastapi.encoders import jsonable_encoder
from loguru import logger

from app.auth.auth_bearer import JWTBearer

AUTH_TIMEOUT_SECONDS = 5


def _build_frame(event: str, data) -> str:
    return json.dumps({"event": event, "data": jsonable_encoder(data)})


class WebSocketManager:
    def __init__(self) -> None:
        self._connections: dict[int, object] = {}
        self._next_id = 0

    async def connect(self, websocket) -> tuple[int | None, bool]:
        await websocket.accept()
        try:
            raw = await asyncio.wait_for(
                websocket.receive_text(), timeout=AUTH_TIMEOUT_SECONDS
            )
        except (asyncio.TimeoutError, TimeoutError):
            await websocket.close(code=4408)
            return None, False

        try:
            msg = json.loads(raw)
            token = msg["token"] if msg.get("type") == "auth" else None
        except (ValueError, TypeError, KeyError):
            token = None

        if not token or not JWTBearer().verify_jwt(jwtoken=token):
            await websocket.close(code=4401)
            return None, False

        conn_id = self._next_id
        self._next_id += 1
        self._connections[conn_id] = websocket
        return conn_id, True

    def disconnect(self, id: int) -> None:
        self._connections.pop(id, None)

    async def send_to_single(self, id: int, event: str, data) -> None:
        ws = self._connections.get(id)
        if ws is None:
            return
        try:
            await ws.send_text(_build_frame(event, data))
        except Exception as e:
            logger.debug(f"dropping ws connection {id}: {e}")
            self.disconnect(id)

    async def broadcast_to_all(self, event: str, data) -> None:
        frame = _build_frame(event, data)
        for conn_id, ws in list(self._connections.items()):
            try:
                await ws.send_text(frame)
            except Exception as e:
                logger.debug(f"dropping ws connection {conn_id}: {e}")
                self.disconnect(conn_id)


ws_mgr = WebSocketManager()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `devenv shell -- bash -c 'uv run python -m pytest tests/test_ws_manager.py -q'`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
jj commit app/api/ws_manager.py tests/test_ws_manager.py -m "feat(api): add WebSocketManager with first-message auth handshake

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: `utils.py` façade + `Event` enum rename

**Files:**
- Modify: `app/api/utils.py`
- Modify (mechanical): `app/lightning/service.py`, `app/apps/tasks_impl/listeners.py`, `app/bitcoind/service.py`, `app/lightning/impl/cln_grpc.py`, `app/lightning/impl/cln_jrpc.py`, `app/lightning/impl/lnd_grpc.py`, `app/system/service.py`, `app/system/impl/raspiblitz.py`

**Interfaces:**
- Consumes: `ws_mgr`, `WebSocketManager` from Task 1.
- Produces:
  - `class Event` (same members/values as old `SSE`) in `app/api/utils.py`.
  - `async broadcast_msg(event: str, data) -> None` in `app/api/utils.py`.
  - Removes `SSE`, `broadcast_sse_msg`, `build_sse_event`, `sse_mgr` from `app/api/utils.py`.

- [ ] **Step 1: In `app/api/utils.py`, rename the `SSE` class to `Event`** (keep every member and string value identical). Find `class SSE:` (~line 320) and change to `class Event:`.

- [ ] **Step 2: Replace the SSE manager import + broadcast/build helpers.** Replace the import `from app.api.sse_manager import SSEManager` and the block:

```python
sse_mgr = SSEManager()


def build_sse_event(event: str, json_data: Optional[Dict]):
    return ServerSentEvent(
        event=event,
        data=json.dumps(jsonable_encoder(json_data)),
    )


async def broadcast_sse_msg(event: str, json_data: Optional[Dict]):
    ...
    await sse_mgr.broadcast_to_all(build_sse_event(event, json_data))
```

with:

```python
from app.api.ws_manager import ws_mgr


async def broadcast_msg(event: str, json_data: Optional[Dict]):
    """Broadcast an event to all connected WebSocket clients."""
    await ws_mgr.broadcast_to_all(event, json_data)
```

Remove the now-unused `ServerSentEvent` import from `app/api/utils.py` if present.

- [ ] **Step 3: Mechanically update all domain callers.** In each of the 8 files listed under Files, replace `broadcast_sse_msg` → `broadcast_msg` and `SSE.` → `Event.`, and fix the import line `from app.api.utils import SSE, broadcast_sse_msg` → `from app.api.utils import Event, broadcast_msg` (member order may vary; keep other imported names).

Run this to preview every line that must change:
```bash
grep -rn "broadcast_sse_msg\|\bSSE\b\|SSE\." app/lightning app/apps app/bitcoind app/system --include="*.py" | grep -v __pycache__
```

- [ ] **Step 4: Verify nothing references the old names** (main.py handled in Task 3; expect only main.py + tests to still reference `SSE`/`broadcast_sse_msg` at this point):

Run: `grep -rn "broadcast_sse_msg\|build_sse_event\|\bSSE\b" app/lightning app/apps app/bitcoind app/system --include="*.py" | grep -v __pycache__`
Expected: no output.

- [ ] **Step 5: Run the full suite** (main.py still imports old names → import error is expected until Task 3; run only the already-migrated modules' import check):

Run: `devenv shell -- bash -c 'uv run python -c "import app.bitcoind.service, app.lightning.service, app.system.service, app.apps.tasks_impl.listeners; print(\"imports ok\")"'`
Expected: `imports ok`

- [ ] **Step 6: Commit**

```bash
jj commit app/api/utils.py app/lightning app/apps app/bitcoind app/system -m "refactor(api): Event enum + broadcast_msg over WebSocket

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: `/ws` endpoint + warmup port in `main.py`

**Files:**
- Modify: `app/main.py`
- Test: `tests/test_ws_endpoint.py`

**Interfaces:**
- Consumes: `ws_mgr`, `Event`, `broadcast_msg` from Tasks 1-2.
- Produces: `@app.websocket("/ws")` route; `_send_ws_event(id, event, data)` helper replacing `_send_sse_event`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ws_endpoint.py
import json

from starlette.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_ws_requires_auth_then_streams():
    with client.websocket_connect("/ws") as ws:
        ws.send_text(json.dumps({"type": "auth", "token": "any"}))
        # first frame after auth is the startup status
        frame = json.loads(ws.receive_text())
        assert frame["event"] == "system_startup_info"
        assert "data" in frame


def test_ws_bad_token_is_closed():
    from starlette.websockets import WebSocketDisconnect

    # force verify_jwt to reject
    import app.api.ws_manager as m

    orig = m.JWTBearer
    m.JWTBearer = lambda: type("B", (), {"verify_jwt": lambda self, jwtoken: False})()
    try:
        with client.websocket_connect("/ws") as ws:
            ws.send_text(json.dumps({"type": "auth", "token": "bad"}))
            try:
                ws.receive_text()
                assert False, "expected disconnect"
            except WebSocketDisconnect as e:
                assert e.code == 4401
    finally:
        m.JWTBearer = orig
```

Note: the default test token passes because `JWTBearer().verify_jwt` is monkeypatched off only in the second test; for the first test, patch it on via a fixture if the real verify rejects "any". Adjust: in `test_ws_requires_auth_then_streams`, monkeypatch `app.api.ws_manager.JWTBearer` to accept, mirroring Task 1.

- [ ] **Step 2: Run test to verify it fails**

Run: `devenv shell -- bash -c 'uv run python -m pytest tests/test_ws_endpoint.py -q'`
Expected: FAIL — no `/ws` route (`WebSocketDisconnect`/404).

- [ ] **Step 3: Replace the SSE endpoint and helper in `main.py`.**

Replace `_send_sse_event`:
```python
async def _send_sse_event(id, event, data):
    return await sse_mgr.send_to_single(id, build_sse_event(event, data))
```
with:
```python
async def _send_ws_event(id, event, data):
    return await ws_mgr.send_to_single(id, event, data)
```

Replace the whole `@app.get("/sse/subscribe")` `async def stream(request)` block with:
```python
@app.websocket("/ws")
async def stream(websocket: WebSocket):
    conn_id, authed = await ws_mgr.connect(websocket)
    if not authed:
        return  # ws_mgr already closed the socket

    new_connections.append(conn_id)
    await _send_ws_event(
        conn_id,
        Event.SYSTEM_STARTUP_INFO,
        jsonable_encoder(api_startup_status.model_dump()),
    )
    asyncio.create_task(warmup_new_connections())

    try:
        while True:
            # server-push only; receive loop just detects disconnect
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_mgr.disconnect(conn_id)
        if conn_id in new_connections:
            new_connections.remove(conn_id)
```

- [ ] **Step 4: Update imports and every `_send_sse_event`/`SSE.`/`sse_mgr` reference in `main.py`.**
  - Imports: change `from app.api.utils import SSE, broadcast_sse_msg, build_sse_event, sse_mgr` → `from app.api.utils import Event, broadcast_msg` and add `from app.api.ws_manager import ws_mgr`.
  - Add `from fastapi import WebSocket` and `from starlette.websockets import WebSocketDisconnect`.
  - Replace all `_send_sse_event(` → `_send_ws_event(`, all `SSE.` → `Event.`, all `broadcast_sse_msg(` → `broadcast_msg(`.
  - In `warmup_new_connections`/`_handle`, `_send_ws_event(id, event, res.model_dump())` etc. — the signature is unchanged (id, event, data).

Preview references to fix:
```bash
grep -n "_send_sse_event\|sse_mgr\|broadcast_sse_msg\|build_sse_event\|\bSSE\.\|add_connection\|EventSource" app/main.py
```
Expected after edits: no output.

- [ ] **Step 5: Run tests**

Run: `devenv shell -- bash -c 'uv run python -m pytest tests/test_ws_endpoint.py tests/test_ws_manager.py -q'`
Expected: PASS

- [ ] **Step 6: Run full suite**

Run: `devenv shell -- bash -c 'uv run python -m pytest -q'`
Expected: PASS (SSE-specific `tests/test_sse_manager.py` will be removed in Task 4; if it fails on import now, proceed to Task 4 first then re-run).

- [ ] **Step 7: Commit**

```bash
jj commit app/main.py tests/test_ws_endpoint.py -m "feat(api): serve realtime updates over /ws WebSocket

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: Delete SSE remnants

**Files:**
- Delete: `app/api/sse_manager.py`, `app/external/sse_starlette/`, `tests/test_sse_manager.py`

**Interfaces:** none produced; verifies nothing imports SSE anymore.

- [ ] **Step 1: Verify no references remain**

Run: `grep -rn "sse_manager\|sse_starlette\|SSEManager\|ServerSentEvent\|EventSourceResponse\|broadcast_sse_msg\|build_sse_event" app/ tests/ --include="*.py" | grep -v __pycache__`
Expected: no output. (If any remain, fix them before deleting.)

- [ ] **Step 2: Delete the files**

```bash
rm app/api/sse_manager.py tests/test_sse_manager.py
rm -r app/external/sse_starlette
```

- [ ] **Step 3: Run full suite**

Run: `devenv shell -- bash -c 'uv run python -m pytest -q'`
Expected: PASS

- [ ] **Step 4: Lint**

Run: `devenv shell -- bash -c 'ruff check --isolated --select F app/api/utils.py app/api/ws_manager.py app/main.py'`
Expected: All checks passed (no unused imports).

- [ ] **Step 5: Commit**

```bash
jj commit -m "chore(api): remove SSE transport (replaced by WebSocket)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>" app/api/sse_manager.py tests/test_sse_manager.py app/external/sse_starlette
```

---

## Phase 2 — WebUI (`web/`)

### File Structure (Phase 2)

- Rename: `src/context/sse-context.tsx` → `src/context/realtime-context.tsx`; `src/hooks/use-sse.tsx` → `src/hooks/use-realtime.tsx`.
- Modify: ~24 consumer files + `src/utils/test-utils.tsx` + tests (mechanical import/usage rename).
- Modify: `src/hooks/use-realtime.tsx` — WebSocket client + auth + dispatch + reconnect.
- Rewrite: `backend-mock/` SSE emitter → WebSocket server.
- Test: `src/hooks/__tests__/use-realtime.test.tsx`.

Run WebUI tasks from `web/`. Use a Node with npm on PATH (e.g. `export PATH=<nodejs>/bin:$PATH`).

---

### Task 5: Rename context/hook (mechanical, behavior-preserving)

**Files:**
- Rename: `src/context/sse-context.tsx` → `src/context/realtime-context.tsx`
- Rename: `src/hooks/use-sse.tsx` → `src/hooks/use-realtime.tsx`
- Modify: all importers (see grep below), `src/utils/test-utils.tsx`, tests

**Interfaces:**
- Produces: `RealtimeContext`, `RealtimeProvider`, `realtimeContextDefault`, `WS_URL`, `useRealtime`. (Exports rename from `SSEContext`/`SSEContextProvider`/`sseContextDefault`/`SSE_URL`/`useSSE`.)

- [ ] **Step 1: List every file referencing the old names**

Run:
```bash
grep -rln "sse-context\|use-sse\|SSEContext\|useSSE\|sseContextDefault\|SSE_URL\|SSEContextProvider" src --include="*.ts*"
```

- [ ] **Step 2: Move the files** (`git mv`/`jj` tracks moves via delete+add):
```bash
mv src/context/sse-context.tsx src/context/realtime-context.tsx
mv src/hooks/use-sse.tsx src/hooks/use-realtime.tsx
```

- [ ] **Step 3: Rename symbols across `src/`** (verify each replacement is correct; these are the exact mappings):
  - `sse-context` → `realtime-context` (import paths)
  - `use-sse` → `use-realtime` (import paths)
  - `SSEContextProvider` → `RealtimeProvider`
  - `SSEContext` → `RealtimeContext`
  - `sseContextDefault` → `realtimeContextDefault`
  - `SSE_URL` → `WS_URL`
  - `useSSE` → `useRealtime`

- [ ] **Step 4: Type-check**

Run: `npm run tsc`
Expected: no errors.

- [ ] **Step 5: Run tests**

Run: `npm test`
Expected: same pass count as before the rename (no behavior change).

- [ ] **Step 6: Commit**

```bash
jj commit -m "refactor(web): rename SSE context/hook to Realtime

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 6: WebSocket client in `use-realtime.tsx`

**Files:**
- Modify: `src/context/realtime-context.tsx` (`WS_URL`, `socket` state)
- Modify: `src/hooks/use-realtime.tsx` (WebSocket + auth + dispatch + reconnect)
- Test: `src/hooks/__tests__/use-realtime.test.tsx`

**Interfaces:**
- Consumes: `RealtimeContext` state setters (`setBtcInfo`, `setLnInfo`, `setSystemInfo`, `setBalance`, `setHardwareInfo`, `setSystemStartupInfo`, `setAppStatus`, `setInstallationStatus`, `setTransactions`, `setAvailableApps`) — unchanged from today.
- Produces: a WebSocket that authenticates on open and dispatches `{event,data}` frames.

- [ ] **Step 1: Set `WS_URL` in `realtime-context.tsx`.** Replace the `SSE_URL`/`WS_URL` constant with a runtime-derived URL:
```ts
export const WS_URL = `${
  window.location.protocol === "https:" ? "wss" : "ws"
}://${window.location.host}/api/ws`;
```
And change the context field from `evtSource: EventSource | null` to `socket: WebSocket | null` (+ `setSocket`), keeping all other fields.

- [ ] **Step 2: Write the failing test**

```tsx
// src/hooks/__tests__/use-realtime.test.tsx
import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// Minimal mock WebSocket
class MockWebSocket {
  static instances: MockWebSocket[] = [];
  onopen: ((e?: unknown) => void) | null = null;
  onmessage: ((e: { data: string }) => void) | null = null;
  onclose: ((e: { code: number }) => void) | null = null;
  onerror: ((e?: unknown) => void) | null = null;
  sent: string[] = [];
  closed = false;
  constructor(public url: string) {
    MockWebSocket.instances.push(this);
  }
  send(d: string) {
    this.sent.push(d);
  }
  close() {
    this.closed = true;
  }
}

// The provider/hook are exercised via a thin harness; see notes.
describe("use-realtime websocket", () => {
  beforeEach(() => {
    MockWebSocket.instances = [];
    vi.stubGlobal("WebSocket", MockWebSocket as unknown as typeof WebSocket);
    localStorage.setItem("access_token", "tok");
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    localStorage.clear();
  });

  it("sends an auth frame on open", () => {
    // render the provider + a component that calls useRealtime (harness below)
    renderRealtimeHarness();
    const ws = MockWebSocket.instances[0];
    act(() => ws.onopen?.());
    expect(JSON.parse(ws.sent[0])).toEqual({ type: "auth", token: "tok" });
  });

  it("dispatches an incoming event into context", async () => {
    const { getBtcInfo } = renderRealtimeHarness();
    const ws = MockWebSocket.instances[0];
    act(() => ws.onopen?.());
    act(() =>
      ws.onmessage?.({
        data: JSON.stringify({ event: "btc_info", data: { blocks: 42 } }),
      }),
    );
    await waitFor(() => expect(getBtcInfo().blocks).toBe(42));
  });

  it("logs out on 4401 close", () => {
    const { logout } = renderRealtimeHarness();
    const ws = MockWebSocket.instances[0];
    act(() => ws.onclose?.({ code: 4401 }));
    expect(logout).toHaveBeenCalled();
  });
});
```

Provide `renderRealtimeHarness()` in the test file: render `RealtimeProvider` wrapping a component that calls `useRealtime()` and exposes `btcInfo`, plus an `AppContext` whose `logout` is a `vi.fn()`. Mirror the existing `test-utils.tsx` provider composition.

- [ ] **Step 3: Run test to verify it fails**

Run: `npx vitest run src/hooks/__tests__/use-realtime.test.tsx`
Expected: FAIL — still using `EventSource`, no auth frame / no dispatch / no logout-on-4401.

- [ ] **Step 4: Rewrite the effect in `use-realtime.tsx`.** Replace the `EventSource` creation and the ~13 `addEventListener` calls with a WebSocket + dispatch map + reconnect. Reuse the existing handler bodies (`setBtcInfo`, etc.) — build a map keyed by event name:

```tsx
const DISPATCH: Record<string, (data: unknown) => void> = {
  system_info: setSystemInfo,
  btc_info: setBtcInfo,
  ln_info: setLnInfo,
  wallet_balance: setBalance,
  hardware_info: setHardwareInfo,
  system_startup_info: setSystemStartupInfo,
  app_state_update_message: handleAppStateUpdateMessage,
  app_manage_message: handleManageAppMessage,
  apps: setApps,
  install: setInstall,
  transactions: setTx,
};

useEffect(() => {
  let socket: WebSocket | null = null;
  let closedByUs = false;
  let backoff = 1000;

  const connect = () => {
    socket = new WebSocket(WS_URL);
    setSocket(socket);
    socket.onopen = () => {
      backoff = 1000;
      const token = localStorage.getItem("access_token");
      socket?.send(JSON.stringify({ type: "auth", token }));
    };
    socket.onmessage = (e) => {
      try {
        const { event, data } = JSON.parse(e.data);
        DISPATCH[event]?.(data);
      } catch (err) {
        console.error("bad ws frame", err);
      }
    };
    socket.onclose = (e) => {
      if (closedByUs) return;
      if (e.code === 4401) {
        appCtx.logout();
        return;
      }
      setTimeout(connect, backoff);
      backoff = Math.min(backoff * 2, 30000);
    };
    socket.onerror = () => socket?.close();
  };

  connect();
  return () => {
    closedByUs = true;
    socket?.close();
  };
  // deps: the setters/handlers are stable; match existing lint expectations
}, [/* same deps shape as today */]);
```

Adapt the handler names to whatever the current hook calls them (`setApps`, `setInstall`, `setTx`, `handleManageAppMessage`, `handleAppStateUpdateMessage` already exist in `use-sse.tsx`). Each handler currently takes a `MessageEvent<string>` and does `JSON.parse(event.data)`; refactor each to take the already-parsed `data` object (the dispatch passes `data` directly), OR wrap: `DISPATCH[event]?.({ data: JSON.stringify(data) } as MessageEvent<string>)` to avoid touching handler bodies. Prefer refactoring handlers to take `data` for clarity.

- [ ] **Step 5: Run test to verify it passes**

Run: `npx vitest run src/hooks/__tests__/use-realtime.test.tsx`
Expected: PASS

- [ ] **Step 6: Type-check + full test suite**

Run: `npm run tsc && npm test`
Expected: no type errors; all tests pass.

- [ ] **Step 7: Commit**

```bash
jj commit -m "feat(web): connect realtime updates over WebSocket with reconnect

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 7: WebSocket backend-mock

**Files:**
- Modify: `backend-mock/index.js` (and `backend-mock/sse/*.js` wiring)
- Modify: `backend-mock/package.json` (add `ws` if not present)

**Interfaces:**
- Produces: a `/api/ws` (or mock root `/ws`) WebSocket that, after an auth frame, streams `{event, data}` frames using the existing mock payloads.

- [ ] **Step 1: Add the `ws` dependency** (if missing):
```bash
cd backend-mock && npm install ws
```

- [ ] **Step 2: Replace the SSE stream handler with a WebSocket server.** Where `index.js` sets `Content-Type: text/event-stream` and writes events, mount a `WebSocketServer` on the same HTTP server at path `/ws` (and `/api/ws`). On connection: wait for the first message; if it parses as `{type:"auth"}` with any non-empty token, start the interval emitters; otherwise `ws.close(4401)`. Reuse each `sse/*.js` payload, sending `ws.send(JSON.stringify({ event, data }))`.

```js
// sketch — adapt to existing structure
const { WebSocketServer } = require("ws");
const wss = new WebSocketServer({ server, path: "/ws" });
wss.on("connection", (ws) => {
  let authed = false;
  ws.on("message", (raw) => {
    if (authed) return;
    try {
      const m = JSON.parse(raw.toString());
      if (m.type === "auth" && m.token) {
        authed = true;
        startEmitters((event, data) => ws.send(JSON.stringify({ event, data })));
      } else ws.close(4401);
    } catch {
      ws.close(4401);
    }
  });
});
```
`startEmitters(send)` wraps the existing periodic mock payloads (system_startup_info first, then system_info/btc_info/ln_info/wallet_balance/hardware_info/app_state_update_message on their current intervals).

- [ ] **Step 3: Manual smoke test**

Run: `npm run dev:local` from `web/`, open `http://localhost:3000`, log in with `password`. Expected: dashboard populates (BTC/LN/hardware cards) — same as with SSE.

- [ ] **Step 4: Commit**

```bash
jj commit backend-mock -m "feat(web): serve mock realtime data over WebSocket

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 8: Final verification

- [ ] **Step 1: API** — `devenv shell -- bash -c 'uv run python -m pytest -q'` → all pass; `grep -rn "sse\|SSE\|EventSource" app/ --include="*.py" | grep -v __pycache__` → only incidental/none.
- [ ] **Step 2: WebUI** — `npm run tsc` clean; `npm test` all pass; `grep -rn "EventSource\|text/event-stream\|SSEContext\|useSSE" src backend-mock` → none.
- [ ] **Step 3: Manual device test** (out of this environment): sync API to a RaspiBlitz, load the WebUI, confirm live BTC/LN/hardware updates, wallet-locked handling, and reconnect after an API restart.
- [ ] **Step 4:** Update `api/CLAUDE.md` / `web/CLAUDE.md` notes that mention "SSE-first" to reference the WebSocket channel. Commit.

---

## Self-Review

- **Spec coverage:** endpoint/auth handshake (Task 1,3) ✓; envelope (Task 1) ✓; `Event`/`broadcast_msg` rename (Task 2) ✓; warmup port (Task 3) ✓; delete SSE (Task 4) ✓; realtime rename (Task 5) ✓; WS client + reconnect + 4401 logout (Task 6) ✓; backend-mock (Task 7) ✓; tests (Tasks 1,3,6) ✓; docs (Task 8) ✓.
- **Type consistency:** `ws_mgr.send_to_single(id, event, data)` / `broadcast_to_all(event, data)` used consistently in Tasks 1/3; `broadcast_msg(event, data)` façade in Tasks 2/3; WebUI `RealtimeContext`/`useRealtime`/`WS_URL` consistent Tasks 5/6.
- **Placeholders:** dispatch map and handler-refactor note in Task 6 are explicit; mock emitter sketch references existing payloads. No TBD/TODO.
