# Consistent Error Responses Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every API error response the flat `ErrorMessage` shape (`{detail, error_code, report?, trace?}`), with `report`/`trace` gated behind config flags, and simplify the WebUI's `checkError` accordingly.

**Architecture:** A single gated builder `build_error_response(...)` constructs the canonical `ErrorMessage` JSONResponse. The three exception handlers in `main.py` route through it, normalizing string details, structured `ErrorMessage` details, validation errors, and (new) uncaught exceptions. The ~56 `raise HTTPException(detail="…")` sites are untouched.

**Tech Stack:** Python 3.12 / FastAPI 0.139 / Starlette 1.3 / pytest; React 19 / TypeScript / Vitest.

## Global Constraints

- Error envelope is the existing flat `ErrorMessage`: `{"detail": <str>, "error_code": <str>, "report": <opt>, "trace": <opt>}`. `detail` is ALWAYS a string.
- `error_code` is `""` when uncoded. Do NOT back-fill codes into existing `raise HTTPException(detail="…")` sites.
- `report` included only when `BAPI_SEND_REPORT=true` (default false), EXCEPT the request-validation field-error array, which is always included (`report_sensitive=False`).
- `trace` included only when `BAPI_SEND_TRACE=true` (default false).
- Flags read via `python-decouple` `config(name, default=False, cast=bool)` at call time (so tests can monkeypatch).
- API: run from `api/`; tests `devenv shell -- bash -c 'uv run python -m pytest <args> -q'`. WebUI: run from `web/`; put node on PATH `export PATH=/nix/store/49p8l3xf2xymibq6lpl1nz0czbg65a1g-nodejs-24.10.0/bin:$PATH` (run `npm install` if deps missing); type-check `npm run tsc`, tests `npm test`.
- Commits use **jujutsu** with EXPLICIT paths: `jj commit <paths> -m "..."` (NOT `git`, NOT a bare `jj commit`). Trailer last line: `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.
- API and WebUI changes deploy together.

---

### Task 1: `build_error_response` gated builder + config flags

**Files:**
- Create: `app/api/error_report/response.py`
- Modify: `.env_sample`
- Test: `tests/test_error_response.py`

**Interfaces:**
- Produces: `build_error_response(status_code: int, detail: str, error_code: str = "", report=None, trace=None, report_sensitive: bool = True) -> starlette.responses.JSONResponse`. Body is `ErrorMessage(...).model_dump()`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_error_response.py
import json

from app.api.error_report.response import build_error_response


def _body(resp):
    return json.loads(bytes(resp.body))


def test_string_detail_produces_error_message_object():
    resp = build_error_response(400, "bad thing")
    assert resp.status_code == 400
    body = _body(resp)
    assert body["detail"] == "bad thing"
    assert body["error_code"] == ""
    assert body["report"] is None
    assert body["trace"] is None


def test_sensitive_report_gated_off_by_default(monkeypatch):
    monkeypatch.setattr(
        "app.api.error_report.response.config",
        lambda name, default=False, cast=bool: False,
    )
    resp = build_error_response(500, "boom", report="/home/x/frame")
    assert _body(resp)["report"] is None


def test_report_included_when_flag_on(monkeypatch):
    monkeypatch.setattr(
        "app.api.error_report.response.config",
        lambda name, default=False, cast=bool: name == "BAPI_SEND_REPORT",
    )
    resp = build_error_response(500, "boom", report="details")
    assert _body(resp)["report"] == "details"


def test_non_sensitive_report_always_included(monkeypatch):
    monkeypatch.setattr(
        "app.api.error_report.response.config",
        lambda name, default=False, cast=bool: False,
    )
    resp = build_error_response(
        422, "bad", report=[{"msg": "x"}], report_sensitive=False
    )
    assert _body(resp)["report"] == [{"msg": "x"}]


def test_trace_gated(monkeypatch):
    monkeypatch.setattr(
        "app.api.error_report.response.config",
        lambda name, default=False, cast=bool: name == "BAPI_SEND_TRACE",
    )
    resp = build_error_response(500, "boom", trace=["l1", "l2"])
    assert _body(resp)["trace"] == ["l1", "l2"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `devenv shell -- bash -c 'uv run python -m pytest tests/test_error_response.py -q'`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.api.error_report.response'`

- [ ] **Step 3: Write the module**

```python
# app/api/error_report/response.py
from typing import Optional, Sequence

from starlette.responses import JSONResponse

from app.api.config import config
from app.api.models import ErrorMessage


def _flag(name: str) -> bool:
    return bool(config(name, default=False, cast=bool))


def build_error_response(
    status_code: int,
    detail: str,
    error_code: str = "",
    report=None,
    trace: Optional[Sequence[str]] = None,
    report_sensitive: bool = True,
) -> JSONResponse:
    """Build the canonical ErrorMessage JSONResponse.

    `report` is included only when it is non-sensitive or `BAPI_SEND_REPORT` is
    set; `trace` only when `BAPI_SEND_TRACE` is set.
    """
    include_report = report is not None and (
        not report_sensitive or _flag("BAPI_SEND_REPORT")
    )
    include_trace = trace is not None and _flag("BAPI_SEND_TRACE")

    message = ErrorMessage(
        detail=str(detail),
        error_code=error_code or "",
        report=report if include_report else None,
        trace=list(trace) if include_trace else None,
    )
    return JSONResponse(status_code=status_code, content=message.model_dump())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `devenv shell -- bash -c 'uv run python -m pytest tests/test_error_response.py -q'`
Expected: PASS (5 passed)

- [ ] **Step 5: Document the flags in `.env_sample`**

Append to `.env_sample`:
```
# Include the verbose "report" and/or "trace" fields in error responses.
# These may contain file paths and stack traces - keep off in production.
# BAPI_SEND_REPORT=false
# BAPI_SEND_TRACE=false
```

- [ ] **Step 6: Commit**

```bash
jj commit app/api/error_report/response.py tests/test_error_response.py .env_sample -m "feat(api): add gated build_error_response for consistent errors

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: Normalize the exception handlers in `main.py`

**Files:**
- Modify: `app/main.py` (the `http_e_handler` and `valid_e_handler` functions near lines 139-171; add a new `unhandled_e_handler`)
- Test: `tests/test_error_handlers.py`

**Interfaces:**
- Consumes: `build_error_response` from Task 1.
- Produces: `main.http_e_handler(request, e)`, `main.valid_e_handler(request, exc)`, `main.unhandled_e_handler(request, exc)` — all return a `JSONResponse` in the `ErrorMessage` shape.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_error_handlers.py
import json

from fastapi import HTTPException
from fastapi.exceptions import RequestValidationError

import app.main as main
from app.api.models import ErrorMessage


def _body(resp):
    return json.loads(bytes(resp.body))


async def test_string_detail_becomes_object():
    resp = await main.http_e_handler(None, HTTPException(400, detail="bad password"))
    assert resp.status_code == 400
    body = _body(resp)
    assert body["detail"] == "bad password"  # NOT a bare string body
    assert body["error_code"] == ""


async def test_errormessage_detail_gates_report_by_default():
    detail = ErrorMessage(
        detail="app failed",
        error_code="app_status_update_failed",
        report="/home/blitzapi/frame",
    ).model_dump()
    resp = await main.http_e_handler(None, HTTPException(500, detail=detail))
    body = _body(resp)
    assert body["detail"] == "app failed"
    assert body["error_code"] == "app_status_update_failed"
    assert body["report"] is None  # sensitive report gated off by default


async def test_validation_handler_keeps_field_array():
    exc = RequestValidationError(
        [
            {
                "type": "missing",
                "loc": ["body", "password"],
                "msg": "Field required",
                "input": None,
            }
        ]
    )
    resp = await main.valid_e_handler(None, exc)
    body = _body(resp)
    assert resp.status_code == 422
    assert body["detail"] == "Field required"
    assert body["error_code"] == "invalid_request_input"
    assert body["report"] is not None  # validation field array always kept


async def test_catchall_returns_error_message():
    resp = await main.unhandled_e_handler(None, ValueError("boom"))
    body = _body(resp)
    assert resp.status_code == 500
    assert body["error_code"] == "unknown"
    assert body["report"] is None  # gated off by default
```

- [ ] **Step 2: Run test to verify it fails**

Run: `devenv shell -- bash -c 'uv run python -m pytest tests/test_error_handlers.py -q'`
Expected: FAIL — `test_string_detail_becomes_object` fails (current handler returns the bare string, so `body` is the string `"bad password"` and `body["detail"]` raises/`TypeError`), and `main.unhandled_e_handler` does not exist yet.

- [ ] **Step 3: Replace the two handlers and add the catch-all in `app/main.py`**

Add the import near the other `app.api.*` imports:
```python
from app.api.error_report.response import build_error_response
```

Replace the existing `http_e_handler`:
```python
@app.exception_handler(HTTPException)
async def http_e_handler(_: Request, e: HTTPException):
    # Normalize every HTTPException into the ErrorMessage shape.
    detail = e.detail
    if isinstance(detail, dict) and "detail" in detail:
        # already an ErrorMessage-shaped dict (e.g. the apps code)
        return build_error_response(
            e.status_code,
            detail=str(detail.get("detail", "")),
            error_code=str(detail.get("error_code", "") or ""),
            report=detail.get("report"),
            trace=detail.get("trace"),
            report_sensitive=True,
        )
    return build_error_response(e.status_code, detail=str(detail))
```

Replace the existing `valid_e_handler`:
```python
@app.exception_handler(RequestValidationError)
async def valid_e_handler(_: Request, exc: RequestValidationError):
    errors = exc.errors()
    try:
        return build_error_response(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=errors[0]["msg"],
            error_code=ApiErrors.INVALID_REQUEST_INPUT,
            report=errors,
            report_sensitive=False,  # field-error array is non-sensitive
        )
    except Exception as e:
        tb = traceback.format_exception(e)
        logger.error(f"error processing RequestValidationError: {e}\n{tb}")
        report = Report("error while processing RequestValidationError", e).attach(exc)
        return build_error_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="error processing RequestValidationError",
            error_code=ApiErrors.UNABLE_TO_PROCESS_ERROR,
            report=report.format_verbose(),
            trace=tb,
        )
```

Add a new catch-all handler right after `valid_e_handler`:
```python
@app.exception_handler(Exception)
async def unhandled_e_handler(_: Request, exc: Exception):
    tb = traceback.format_exception(exc)
    logger.error(f"unhandled exception: {exc}\n{''.join(tb)}")
    report = Report("unhandled exception", exc)
    return build_error_response(
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Internal server error",
        error_code=ApiErrors.UNKNOWN,
        report=report.format_verbose(),
        trace=tb,
    )
```

Note: `status.HTTP_422_UNPROCESSABLE_ENTITY` — confirm it exists in this
`starlette.status`; if the constant name differs, use the literal `422`. The old
code used `status_code=422`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `devenv shell -- bash -c 'uv run python -m pytest tests/test_error_handlers.py -q'`
Expected: PASS (4 passed)

- [ ] **Step 5: Run the full suite**

Run: `devenv shell -- bash -c 'uv run python -m pytest -q'`
Expected: all pass. (If a test elsewhere asserted a bare-string error body, update it to read `body["detail"]` — but none are expected.)

- [ ] **Step 6: Commit**

```bash
jj commit app/main.py tests/test_error_handlers.py -m "feat(api): normalize all error responses to the ErrorMessage shape

Route HTTPException, RequestValidationError and uncaught exceptions
through build_error_response so every error body is
{detail, error_code, report?, trace?}. Fixes the bare-string body that
string HTTPException details produced.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: Simplify the WebUI `checkError`

**Files:**
- Modify: `web/src/utils/checkError.ts`
- Modify: `web/src/utils/__tests__/checkError.test.ts`

Run from `web/`. `export PATH=/nix/store/49p8l3xf2xymibq6lpl1nz0czbg65a1g-nodejs-24.10.0/bin:$PATH` first (run `npm install` if deps missing).

**Interfaces:**
- Produces: `checkError(err: AxiosError<ApiError>) -> string`; `ApiError = { detail: string; error_code?: string; report?: unknown; trace?: string[] }`.

- [ ] **Step 1: Update the tests first (they should fail against current code only where the shape changed)**

Replace the whole body of `web/src/utils/__tests__/checkError.test.ts` with:
```ts
import { checkError } from "../checkError";

vi.mock("i18next", () => ({
  t: () => "An error occurred",
}));

describe("checkError", () => {
  it("shows the string detail", () => {
    const errorMsg = checkError({
      // @ts-expect-error response is not a full AxiosResponse<ApiError> here
      response: {
        data: { detail: "old password format invalid" },
      },
    });
    expect(errorMsg).toEqual("An error occurred: old password format invalid");
  });

  it("falls back to unknown when there is no string detail", () => {
    const errorMsg = checkError({
      response: {
        status: 404,
        statusText: "Not found",
        // @ts-expect-error - testing missing detail
        data: {},
      },
    });
    // t() is mocked, so both segments render as "An error occurred"
    expect(errorMsg).toEqual("An error occurred: An error occurred");
  });
});
```

- [ ] **Step 2: Run tests to verify the removed-shape cases are gone and the new ones drive the change**

Run: `npx vitest run src/utils/__tests__/checkError.test.ts`
Expected: the two tests run; they pass against the CURRENT checkError too (its string branch already handles case 1, and `{}` falls through to unknown), so this step mainly locks the intended behavior before simplifying. Proceed to simplify.

- [ ] **Step 3: Rewrite `web/src/utils/checkError.ts`**

```ts
import type { AxiosError } from "axios";
import { t } from "i18next";

export interface ApiError {
  detail: string;
  error_code?: string;
  report?: unknown;
  trace?: string[];
}

/**
 * Returns the error's `detail` string with a translated prefix, or a generic
 * "unknown error" fallback when the response has no string detail.
 */
export function checkError(err: AxiosError<ApiError>): string {
  const detail = err.response?.data?.detail;

  if (typeof detail === "string") {
    return `${t("login.error")}: ${detail}`;
  }

  return `${t("login.error")}: ${t("login.unknown_error", {
    code: err.response?.status,
    statusText: err.response?.statusText,
  })}`;
}
```

- [ ] **Step 4: Verify no other file imported the removed `ApiErrorDetails` type**

Run: `grep -rn "ApiErrorDetails" src --include="*.ts*"`
Expected: no output. (If any, update that import to `ApiError`.)

- [ ] **Step 5: Type-check and run tests**

Run: `npm run tsc` (expected: 0 errors), then `npm test` (expected: all pass, including the two updated `checkError` tests).

- [ ] **Step 6: Commit**

```bash
jj commit src/utils/checkError.ts src/utils/__tests__/checkError.test.ts -m "refactor(web): read the consistent error detail string

The API now always returns a string \`detail\`, so drop checkError's
array / detail.msg fallbacks and the stale #123 comment. Closes #123.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Self-Review

- **Spec coverage:** envelope shape (Task 1 builder + Task 2 handlers) ✓; `BAPI_SEND_REPORT`/`BAPI_SEND_TRACE` gating + validation-array-always-on (Task 1 `report_sensitive`, Task 2 validation handler) ✓; `.env_sample` flags (Task 1) ✓; catch-all Exception handler (Task 2) ✓; `error_code:""` for uncoded (Task 1 default) ✓; WebUI `checkError` + types + tests (Task 3) ✓; testing (Tasks 1-3) ✓.
- **Type consistency:** `build_error_response(status_code, detail, error_code, report, trace, report_sensitive)` used identically in Tasks 1 and 2; `ApiError`/`checkError` signature consistent in Task 3.
- **Placeholders:** none — every step has concrete code/commands. The one conditional note (`HTTP_422_UNPROCESSABLE_ENTITY` constant name) includes the exact fallback (`422`).
