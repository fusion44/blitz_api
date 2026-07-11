# Design: Replace SSE with WebSockets

- **Issue:** blitz_api#252 (prior art: PR #268, not reused — predates current code)
- **Date:** 2026-07-05
- **Repos:** `api` (blitz_api, FastAPI) and `web` (raspiblitz-web, React)
- **Strategy:** clean cut — remove SSE entirely, coordinated API + WebUI change that deploys together

## Goal & scope

Replace the Server-Sent-Events realtime channel with a WebSocket channel.

**In scope:** a pure server→client push transport swap. Same ~20 events, same
payloads, new envelope, WebSocket auth. Client→server messaging is explicitly
**out of scope** (the envelope leaves room for it later); actions stay on REST
(e.g. `POST apps/update-cache`).

**Why a clean cut is safe:** the WebUI is the only consumer of the realtime
stream. The generated client libraries are REST/OpenAPI and never touched SSE,
so there is no third-party consumer to keep SSE alive for. The raspiblitz
installer pins matching API/WebUI versions, so a coordinated deploy is the
normal model (same as the recent JWT change).

## Wire protocol (shared contract)

**Endpoint:** `@app.websocket("/ws")` → externally `/api/ws` (nginx already
proxies `/api`; mirrors how `/sse/subscribe` was served). The client derives the
scheme from the page protocol: `https:` → `wss`, else `ws`.

**Auth handshake (first-message):**
1. Client connects; server `accept()`s but streams nothing yet.
2. Server awaits the first frame for ≤ 5 s: `{"type": "auth", "token": "<jwt>"}`.
3. Valid token → connection marked authed, current state replayed (warmup),
   then streaming begins.
4. Invalid / missing / malformed → `close(4401)`. Timeout → `close(4408)`.

JWT validation reuses the existing `decodeJWT` path (so the standard-`exp`
claim fix carries over).

**Envelope (server→client):** JSON text frames, one shape for everything:

```json
{ "event": "btc_info", "data": { ... } }
```

The `event` values are **identical to today's SSE event strings** (`btc_info`,
`ln_info`, `hardware_info`, `system_startup_info`, …), so payloads and the
WebUI dispatch map 1:1. No event is added, removed, or renamed.

**Close codes:** `4401` unauthorized, `4408` auth timeout, `1000`/`1001` normal
shutdown.

## API design (`api`)

**New `app/api/ws_manager.py` — `WebSocketManager`** (replaces `SSEManager`):

- `async connect(websocket) -> (id, authed)`: `accept()`, run the auth
  handshake (await first frame ≤ 5 s, validate JWT), register the socket under a
  new integer id on success.
- `async send_to_single(id, event, data)` / `async broadcast_to_all(event, data)`:
  JSON-encode the `{event, data}` envelope and `send_text` to one / all authed
  sockets. Each send is wrapped in try/except; a socket that raises is
  unregistered rather than breaking the loop.
- No global broadcast queue or background consumer task — WebSocket sends go
  directly to each socket. This deletes the SSE lazy-broadcast-task machinery
  (and the `asyncio.get_event_loop()` usage that went with it).
- `disconnect(id)` / `WebSocketDisconnect` handling removes the id.

**`app/api/utils.py`:** keep a façade the domain code calls, renamed
`broadcast_sse_msg` → `broadcast_msg(event, data)`; internally
`ws_mgr.broadcast_to_all(event, data)`. The `SSE` event enum → `Event`
(transport-neutral), string values unchanged. The 56 call sites across 10 files
change only by the rename.

**`app/main.py`:**
- Replace `@app.get("/sse/subscribe")` with `@app.websocket("/ws")`. Handler:
  `id, authed = await ws_mgr.connect(ws)`; if not authed, return (already
  closed). Else send `system_startup_info`, register as a new connection,
  schedule `warmup_new_connections()`, then loop `await ws.receive_text()` to
  detect disconnect (inbound frames are ignored — server-push only). On
  `WebSocketDisconnect`, unregister.
- `warmup_new_connections()` and the `_send_*` helpers keep their exact logic
  (including the recent warmup fixes: correct event name, `warmup_running`
  reset); only the underlying transport call changes to `send_to_single`.

**Deletions:** `SSEManager`, `app/external/sse_starlette/`, `build_sse_event`,
`EventSourceResponse` usage, the `/sse/subscribe` route.

## WebUI design (`web`)

**Honest, transport-neutral rename** (opted in):
- `context/sse-context.tsx` → `context/realtime-context.tsx`:
  `SSEContext`→`RealtimeContext`, `SSEContextProvider`→`RealtimeProvider`,
  `sseContextDefault`→`realtimeContextDefault`, `SSE_URL`→`WS_URL`.
- `hooks/use-sse.tsx` → `hooks/use-realtime.tsx`: `useSSE`→`useRealtime`.
- ~24 consumer files + `utils/test-utils.tsx` + tests: update imports/usages
  (mechanical; no behavior change — they read the same context fields).

**`WS_URL`** derived at runtime:
`` `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/api/ws` ``.

**`use-realtime.tsx`** replaces `new EventSource(...)` + the per-event
`addEventListener` calls with:
- `new WebSocket(WS_URL)`.
- `onopen` → send `{type:"auth", token}` (token from `localStorage`
  `ACCESS_TOKEN`).
- `onmessage` → parse `{event, data}`, look the handler up in a **dispatch map**
  (`{ btc_info: setBtcInfo, ln_info: setLnInfo, … }`) built from the same
  handler bodies used today, updating the same context state.
- `onclose` → code `4401` → `appCtx.logout()`; otherwise **reconnect with
  exponential backoff** (1 s → 30 s cap), re-running the auth handshake on
  reconnect. No give-up (a node UI should keep retrying).
- `onerror` → falls through to `onclose`.
- Logout / unmount → `socket.close()`.

This reconnect loop is the one genuinely new behavior: `WebSocket` does not
auto-reconnect the way `EventSource` did.

## backend-mock (`web/backend-mock`)

Rewrite the SSE emitter (`text/event-stream` + `res.write`) to a WebSocket
server (`ws` npm lib, or `express-ws`). On connect: await the
`{type:"auth", token}` frame (mock accepts any non-empty token), then stream the
same event payloads the current `sse/*.js` emitters produce, wrapped in the
`{event, data}` envelope. `npm run dev:local` keeps working unchanged.

## Testing

**API (pytest, `TestClient.websocket_connect`):**
- Auth handshake: valid → receives `system_startup_info` + warmup frames;
  invalid / missing / timeout → close `4401` / `4408`.
- Envelope shape `{event, data}`.
- `broadcast_msg` reaches a connected authed client.
- A dead socket is pruned without breaking a broadcast to others.

**WebUI (vitest, mock `WebSocket`):**
- Sends `{type:auth,token}` on open.
- Dispatches an incoming `{event, data}` into the correct context state.
- Reconnects with backoff on close.
- Logs out on `4401`.

**Not testable in this environment:** real end-to-end against LND/bitcoind —
manual verification on a device at the end.

## Delivery

Two coordinated changes that merge/deploy together:
1. **API** — `ws_manager` + `/ws` + auth handshake + `broadcast_msg`/`Event`
   rename + warmup port + delete SSE. Unit-tested.
2. **WebUI** — realtime rename + WebSocket client + reconnect + backend-mock.
   Unit-tested.

Implement API first, then WebUI + mock.

## Out of scope / follow-ups

- Client→server commands over WS (envelope is ready for it).
- Any change to the ~20 event names or payloads.
- Reworking the generated client libraries (unaffected — REST/OpenAPI only).
