# Design: Consistent error responses

- **Issues:** blitz_api#148 (better /apps errors) + #123 (consistent error shape)
- **Date:** 2026-07-12
- **Repos:** `api` (blitz_api, FastAPI) and `web` (raspiblitz-web, React)

## Goal & current state

Give every API error response one consistent shape so clients (the WebUI and
generated libraries) can read errors uniformly, and stop leaking verbose /
sensitive detail by default.

Much of the machinery already exists:
- `ErrorMessage` model (`app/api/models.py`): flat `{detail, error_code, report, trace}`.
- `ApiErrors` enum of error codes.
- `Report` (`app/api/error_report/`) with `format()` / `format_verbose()`.
- `valid_e_handler` already turns FastAPI's `RequestValidationError` array into an
  `ErrorMessage` (first error → `detail`, full array → `report`).
- The apps code raises rich `HTTPException(detail=ErrorMessage(...).model_dump())`.

**The gap.** `http_e_handler` returns `JSONResponse(content=e.detail)` verbatim.
So the ~56 `raise HTTPException(detail="<string>")` sites across 17 files emit a
**bare JSON string** body (e.g. `"old password format invalid"`), while the apps
code emits the structured object. Two shapes. Worse, a bare-string body has no
`detail` key, so the WebUI's `checkError` falls through to a generic
"unknown error" — the exact `{"detail": "Unknown error"}` symptom #148 opened
with. Separately, `BAPI_SEND_TRACE` / report gating is documented on the model
but read nowhere (unimplemented), and one handler emits `trace` unconditionally.

## The error envelope (contract)

Every error response body is the existing flat `ErrorMessage`:

```json
{ "detail": "human-readable message", "error_code": "invalid_request_input", "report": ..., "trace": ... }
```

- **`detail`** — always a string; the primary message the WebUI displays.
- **`error_code`** — an `ApiErrors` value when the raiser set one, else `""`.
  We do NOT back-fill codes into the 56 string raises; they stay `""` and codes
  are added incrementally where useful.
- **`report`** — verbose/structured extra; included **only when
  `BAPI_SEND_REPORT=true`** (default false). Exception: the request-validation
  field-error array (echoes the client's own bad input, non-sensitive) is
  **always** included.
- **`trace`** — stack trace; included **only when `BAPI_SEND_TRACE=true`**
  (default false).

By default a client sees just `{detail, error_code}` — no paths/traces leaked.

Flags are read once via `python-decouple` like other `BAPI_*` settings.

## API design (`api`)

**Shared builder.** Add `build_error_response(...) -> JSONResponse` (in
`app/api/error_report/response.py`, a new focused module):

```python
def build_error_response(
    status_code: int,
    detail: str,
    error_code: str = "",
    report=None,
    trace=None,
    report_sensitive: bool = True,
) -> JSONResponse:
    """Build the canonical ErrorMessage JSONResponse, applying report/trace gating."""
```

Behaviour:
- Always sets `detail` (str) and `error_code`.
- Includes `report` only if `report is not None` AND (`not report_sensitive` OR
  `BAPI_SEND_REPORT` is true).
- Includes `trace` only if `trace is not None` AND `BAPI_SEND_TRACE` is true.
- Returns `JSONResponse(status_code, content=ErrorMessage(...).model_dump())`.

The two flags are read via `config("BAPI_SEND_REPORT", default=False, cast=bool)`
and `config("BAPI_SEND_TRACE", default=False, cast=bool)` at call time (so tests
can monkeypatch).

**Handlers in `main.py`** all route through the builder:

1. `http_e_handler(HTTPException)` — normalize `e.detail`:
   - `str` → `build_error_response(e.status_code, detail=e.detail)`.
   - `dict` with a `"detail"` key (already an `ErrorMessage` shape, e.g. the apps
     path) → `build_error_response(e.status_code, detail=d["detail"],
     error_code=d.get("error_code",""), report=d.get("report"),
     trace=d.get("trace"), report_sensitive=True)` — so its `Report`-derived
     report and any trace get gated.
   - any other `dict`/`list` (defensive) → `detail=str(e.detail)`.
2. `valid_e_handler(RequestValidationError)` — happy path:
   `build_error_response(422, detail=errors[0]["msg"],
   error_code=ApiErrors.INVALID_REQUEST_INPUT, report=errors,
   report_sensitive=False)` (field array always kept). The existing 500 fallback
   uses `report_sensitive=True` + `trace=tb` (both gated).
3. **New** `@app.exception_handler(Exception)` catch-all — an uncaught error
   currently yields FastAPI's default 500 (inconsistent). Handle it:
   `build_error_response(500, detail="Internal server error",
   error_code=ApiErrors.UNKNOWN, report=Report(...).format_verbose(),
   trace=traceback.format_exception(exc))` (report/trace gated). Log the full
   error server-side regardless.

The 56 `raise HTTPException(detail="…")` sites are **untouched** — they keep
raising strings; the handler normalizes.

**`.env_sample`** — add `# BAPI_SEND_REPORT=false` and `# BAPI_SEND_TRACE=false`
with a comment that they may expose file paths / traces.

## WebUI design (`web`)

Error handling funnels through one place (`checkError`, 15 callers); no component
parses the error shape directly.

- `src/utils/checkError.ts` — read `detail` as a string directly; drop the array
  and `detail.msg` branches and the `#123` comment; keep the "unknown error"
  fallback for missing / non-JSON responses. Update the `ApiError` type to
  `{ detail: string; error_code?: string; report?: unknown; trace?: string[] }`
  and remove `ApiErrorDetails`.
- `src/utils/__tests__/checkError.test.ts` — remove the `detail.msg`-object and
  array cases (that shape no longer occurs); assert a string `detail` is shown
  and the fallback fires when there is no `detail`.

Non-breaking (API keeps returning a string `detail`); the repos deploy together.

## Testing

**API (pytest, `TestClient` with tiny throwaway routes on a test `FastAPI` app
wired with the same handlers):**
- `HTTPException(detail="str")` → body is `{"detail":"str","error_code":""}`
  (a JSON object, not a bare string — the core regression).
- `HTTPException(detail=ErrorMessage(..., report=r, trace=t).model_dump())` →
  `report`/`trace` present only when the respective flag is set (test both
  states via monkeypatched config).
- validation error → `{detail:firstMsg, error_code:"invalid_request_input",
  report:[array]}`; field array kept, `trace` gated.
- uncaught `Exception` → 500 `ErrorMessage` with `error_code:"unknown"`.

**WebUI (vitest):** the updated `checkError` cases.

## Delivery

Two coordinated changes:
1. **API** — `build_error_response` + the three handlers + `.env_sample` + tests.
2. **WebUI** — `checkError` simplification + tests.

## Out of scope / follow-ups

- RFC 9457 `application/problem+json`.
- Back-filling `error_code` into the 56 string raises.
- Nested `detail.detail` shape.
