# Backend Quality Reference — Carmack × Ramírez × FastAPI

Philosophy: John Carmack. Runtime expertise: Sebastián Ramírez (FastAPI, Pydantic, Starlette). Patterns: FastAPI service layer wrapping a deterministic `core/` engine.
Stack context: Python 3.11+ / FastAPI + uvicorn / Pydantic v2 / SQLite via SQLAlchemy / parquet market-data cache / a CPU-bound pandas/numpy detector engine in `core/`.

Every finding must describe the **concrete failure mode** — not just "this is bad practice."
Security patterns are in security.md (Hunt). Data-store depth (SQLite/SQLAlchemy/parquet) is in quality-postgres.md (Brandur). Numerical/detector correctness is in quality-llm.md (McKinney). This doc covers: async correctness, error-handling discipline, Pydantic boundary design, dependency injection, configuration loading, and the service layer that wraps `core/`.

---

## Principle 1: Programmer errors are assertion failures — crash, don't recover

*Carmack: assertions are tripwires. When an invariant is violated, halt execution.*
*Ramírez: a request that violated an invariant should fail loudly with a 500 and a logged traceback — not return a half-computed setup list.*

Classify every error into two categories:

**Operational errors** — run-time problems a correct program must expect: yfinance returns an empty frame, a ticker is delisted, the market-data cache is stale, IBKR is disconnected. Action: handle, degrade gracefully, or surface to the caller as a typed result (e.g. `StaleMarketDataError`, fetch-health "degraded").

**Programmer errors** — bugs: indexing a column that doesn't exist, passing a `Series` where a scalar is required, a detector returning `None` where the caller assumes a box. Action: let it crash. The process is in an unknown state and the worst outcome is a *plausible-looking wrong answer* in a screener a human will trade on.

The argument for crashing is sharp on this stack: the engine is deterministic and the prime directive is *accurate* tight-structure detection. A swallowed programmer error doesn't crash — it ships a setup card that looks fine but was computed from corrupt intermediate state. The trader eyeballs it, trusts it, and the bug is now in a position.

The real `scan_runner` models this well: a scheduled scan that raises is recorded as `status="failed"` and re-raised, but the **forward-return backfill runs anyway** in a `finally` — because it matures already-archived rows and a crashing scan must not silently starve outcome maturation. Operational independence is explicit; the programmer error still propagates.

### What to check

**Swallowed exceptions**
- Bare `except Exception: pass` or `except: return None` around detector or fetch calls. If you can't name what the exception means and what state the engine is in afterward, let it propagate.
- `except Exception:` that only logs and continues processing the *next* ticker is acceptable in a batch scan loop — one bad ticker must not abort the universe — **but** the swallowed ticker must be recorded (quarantine / fetch-health), not silently dropped. A silent drop is a recall regression nobody will notice.
- Ramírez: a FastAPI route should let unexpected exceptions reach the framework's handler, which returns a clean 500 and logs the traceback. Catching to return `{"ok": true}` disables the tripwire.
- Severity: **P1** when the swallow touches detector output, archive writes, or shared cache state. **P2** otherwise.

**`assert` used for runtime validation**
- `assert` statements are stripped under `python -O`. Use them for *programmer-error* invariants (internal consistency the engine guarantees), never for validating untrusted input — that's Pydantic's job (Principle 3).
- Severity: **P2** for `assert` on request/input data.

**Retry storms across layers**
- The frontend SSE client retries the scan, the scan subprocess retries the fetch, yfinance retries internally. A single transient 429 becomes an exponential pile-up. If a layer retries, it must be documented and the layers above it must NOT.
- Severity: **P2** when retries aren't coordinated across the fetch → engine → SSE stack.

---

## Principle 2: Never block the event loop — the engine scan is CPU-bound

*Carmack: if you can't see the cost, you can't reason about correctness.*
*Ramírez: "If you don't know, use `async def`. If you're calling something blocking, either don't make the path async, or push the blocking work to a threadpool."*

FastAPI runs `async def` routes directly on the event loop and dispatches plain `def` routes to a threadpool. The single most damaging mistake on this codebase is putting **CPU-bound pandas/numpy detector work, or a blocking subprocess/`urlopen`, inside an `async def` route**. While a universe scan crunches, every other request — health checks, the SSE heartbeat, the watchlist toggle — is frozen.

### What to check

**Blocking work inside `async def`**
- A pandas vectorized detector pass, `scipy` call, or `subprocess`/`urllib.request.urlopen` invoked directly in an `async def` route. This blocks the loop for the whole scan.
- Two correct fixes: (a) define the route as plain `def` so Starlette runs it in the threadpool, or (b) keep it `async def` and offload with `await anyio.to_thread.run_sync(...)` / `run_in_executor`. The real `run-scan-stream` route is a plain `def` returning a `StreamingResponse` whose generator drives a subprocess — exactly right: no `await`, no false `async`.
- Ramírez: **"Making a path `async def` and then calling blocking code inside it is worse than not using async at all — you've taken the one thread that serves everyone and stalled it."**
- Severity: **P1** for the engine scan, fetch, or subprocess inside `async def`. **P2** for incidental blocking (sync file read, `time.sleep`) in an async path.

**Synchronous I/O on the loop**
- `open(...).read()` on the parquet cache or `cache_meta.json`, blocking SQLAlchemy queries, `requests`/`urlopen` — all block when called from `async def`. SQLAlchemy's classic engine is synchronous; route handlers that touch the archive DB should be `def` (threadpool) unless you've adopted the async engine throughout.
- Severity: **P2**.

**Heavy work hidden behind a dependency**
- A FastAPI `Depends(...)` that loads settings, opens the DB, or reads a parquet file looks free at the call site but runs on every request to that route. Know what each dependency costs; cache what's stable (see Principle 5).
- Severity: **P3** — transparency. Escalate to **P2** if a dependency does I/O on a hot path.

**Long jobs that own the whole process**
- The scan holds a module-level `SCAN_LOCK` (`threading.Lock`, acquired non-blocking). A second scan request returns "another scan is already running" instead of queueing or deadlocking. Good. Flag any long job that takes a lock *blocking* on the event loop, or that has no single-flight guard at all.
- Severity: **P2** for missing single-flight on the scan/download jobs.

---

## Principle 3: Validate at the boundary with Pydantic — the model IS the tripwire

*Carmack: deploy assertions as tripwires — catch assumption violations before they propagate.*
*Ramírez: the request model is the contract. If it parsed, the rest of the function can trust its shape.*

Every request body and every typed query parameter is a place an assumption can be wrong. A Pydantic model at the boundary converts "I hope the caller sent a list of tickers" into a guarantee — and a malformed request fails with a 422 *at the edge*, before any engine code runs on garbage.

### What to check

**Loose or absent input models**
- A POST body read as a raw `dict`, or `ticker: str` where the field should be constrained. The real `EarningsBatchIn(BaseModel)` with `tickers: list[str]` is the right shape; the route then normalizes (`.upper().strip()`) and guards empties. Tickers especially want validation — an unconstrained string flows straight into a file path (cache) and a DB query.
- Use Pydantic constraints (`Field(min_length=...)`, `conlist`, pattern for ticker symbols, date validators) rather than hand-written `if` checks scattered in the route.
- Severity: **P2** for mutation/POST routes without a request model. **P3** for loose constraints on otherwise-validated input.

**Raw exception detail leaking through the response**
- An unhandled SQLAlchemy or pandas error propagating to the client exposes internals — table/column names, file paths, a stack of the archive query. FastAPI returns a generic 500 body by default *only if you let it*; a route that catches and does `raise HTTPException(detail=str(exc))` leaks the raw message.
- Fix: catch known operational failures and raise `HTTPException` with a **curated** `detail`; let programmer errors hit the default 500 (which logs the traceback server-side and returns a generic body). The SSE path does this well — it yields `data: ERROR: stale market data ...` (a known, sanitized signal) rather than dumping a traceback to the stream.
- Severity: **P1** — information disclosure; cross-reference security.md.

**Response models that over-share**
- Returning a SQLAlchemy ORM row (or a full internal detector dict) straight from a route ships *every* column/key, including internal scoring intermediates the frontend shouldn't depend on. Declare `response_model=...` with `model_config = {"from_attributes": True}` (as `TagOut` does) so the response is a deliberate projection, not "whatever the ORM had."
- This is also a coupling guard: without a response model, adding an internal column silently changes the API contract.
- Severity: **P2** for routes returning ORM/internal objects without a response model.

**`None`/empty as a silent success**
- A route that returns `{}` or `[]` for both "no setups today" and "the scan never ran / data was stale" makes the two indistinguishable to the frontend. The real `scan-status/latest` route returns an explicit `status: "never"` sentinel — model the *absence* explicitly rather than overloading empty.
- Severity: **P2** when empty masks an error/degraded state the UI must show.

---

## Principle 4: The service layer — keep `core/` pure, keep routes thin

*Carmack: make the wrong thing impossible rather than trusting humans to do the right thing.*
*Ramírez: routes are adapters. Business logic lives in plain functions you can call from a test without an HTTP client.*

The architecture here is deliberate and worth defending: `core/` is a deterministic, framework-free engine; `webapp/backend/services/` wraps it; `routers/` are thin FastAPI adapters. The detector math must never import FastAPI, and a route must never reimplement engine logic inline.

### What to check

**Logic in the route instead of a service**
- A router that builds boxes, filters setups, or computes scores in the handler body. That logic is now untestable without spinning up the app and can drift from the engine's own copy — the exact failure the "eval-twins fold" exists to prevent (live and seed paths must route through shared helpers or they diverge silently).
- Routes should call `services.*`, which calls `core.*`. The `screener` router calling `scan_runner.stream_manual_scan()` and `read_screener_data(...)` is the pattern.
- Severity: **P2** for non-trivial engine logic embedded in a route. **P1** if it duplicates logic that already exists in `core/` (divergence risk).

**`core/` reaching back into the web layer**
- Anything under `core/` importing from `webapp/backend`, FastAPI, or Starlette inverts the dependency and couples the deterministic engine to the server. The engine must run identically from `run_screener.py`, a pytest, and the backend.
- Severity: **P1** — this breaks the byte-parity/seed-recall guarantees the whole validation story rests on.

**Pure decision functions buried in I/O**
- `_alert_decision(...)` in `scan_runner` is pure (no I/O) precisely so it's unit-testable, while `alert_if_needed(...)` does the webhook/logging around it. Mirror this split: extract the *decision* from the *effect*. A function that both decides and posts to a webhook can only be tested by mocking the network.
- Severity: **P2** for branching business logic welded to its side effects.

---

## Principle 5: Configuration & dependency lifecycle — the config-vs-cwd trap

*Carmack: understand the lifecycle of every resource you allocate.*
*Ramírez: settings are a dependency like any other — load them deliberately, not as an import side effect.*

This codebase has a real, documented hazard worth memorializing: the backend's working directory (`webapp/backend`) contains a `config.py` that **shadows the repo-root `config/` package**. A module-level `from config import settings` in anything under `core/` resolves to the wrong module when imported by the backend — tests pass (run from repo root), the service crashes on boot. The fix that lives in `core_settings.py` loads the root `config/settings.py` *by explicit file path* via `importlib`, and is called **lazily** (`load_core_settings()` inside the function that needs it), never at import time.

### What to check

**Settings read at import time**
- A module-level `settings = load_core_settings()` (or `from config import ...`) runs during import, before cwd/path is known, and is the literal cause of the boot crash above. Read settings *inside* the function/dependency that uses them.
- Severity: **P1** for module-level root-config reads in `core/` imported by the backend. **P2** elsewhere.

**Config accessed three different ways**
- Some code does `getattr(settings, "ALERT_ON_ZERO_RESULTS", True)`, some imports a constant directly, some reads `os.environ`. The `getattr(..., default)` pattern in `alert_if_needed` is the resilient one — a missing setting degrades to a sane default instead of `AttributeError` mid-scan. Standardize on it for optional settings.
- Severity: **P3** — consistency, unless a hard import-time read can crash the path.

**Secrets via environment, not constants**
- The alert webhook URL is read from `os.environ[...]` (indirected through a settings-named env var), never hardcoded. IBKR credentials and any webhook/API URL belong in the environment and must never be logged. See security.md.
- Severity: **P1** for secrets in source or in log lines.

**Dependencies with the wrong scope**
- A `Depends(...)` that opens a DB connection or reads a parquet file *per request* when the resource is process-stable should be cached (module-level singleton or `lru_cache`). Conversely, a request-scoped resource (DB session) cached at module level leaks state across requests. Match `Depends` scope to the resource's real lifecycle, and ensure session-style dependencies clean up in a `finally`/`yield`.
- Severity: **P2** for lifecycle mismatches that leak connections or serve stale handles.

---

## Principle 6: Streaming, subprocesses, and resource cleanup

*Carmack: understand the lifecycle of every resource you allocate.*
*Ramírez: a generator response owns its resources until the last byte — clean up in `finally`, not on the happy path.*

The scan, evaluation, and download endpoints are **SSE `StreamingResponse`s driving a subprocess**. This is the most resource-heavy pattern in the backend and every failure mode here is a slow leak or a stuck lock.

### What to check

**Cleanup only on the success path**
- A streaming generator that releases the `SCAN_LOCK`, closes `process.stdout`, or invalidates the screener cache *after* the loop but not in a `finally`. If the client disconnects (closes the SSE tab) or the subprocess raises mid-stream, the lock is never released and **every future scan is permanently blocked**. The real code is correct: `SCAN_LOCK.release()` and `invalidate_screener_cache()` are in `finally`.
- Severity: **P1** for lock/handle/cache cleanup outside `finally` on a streaming path.

**Unwaited / unreaped subprocesses**
- Launching `subprocess.Popen` and not calling `.wait()` (zombie process) or not closing `stdout` (leaked pipe). Long-running scans must reap the child even when the stream is abandoned.
- The Windows/UTF-8 handling in `_create_process` (forcing `PYTHONUTF8`/`PYTHONIOENCODING`, `errors="replace"`) is a real correctness fix, not ceremony: without it a single emoji tag in the pipeline output crashes the child under the service's cp1252 locale. Don't "simplify" it away.
- Severity: **P1** for unreaped subprocesses. **P2** for missing encoding hardening on piped children.

**Status records that don't close**
- `scan_status.start_run(...)` must be paired with `finish_run(...)` on **every** exit path — success, failure, and exception. An orphaned "running" row makes the watchdog think a scan is stuck forever. The real code finishes the run in both the `except` and the normal path.
- Severity: **P2** for run/status records not finalized on the error path.

**Client-disconnect awareness**
- A long stream with no `await request.is_disconnected()` check (for async streams) keeps generating work for a client that left. Less critical here because the subprocess is the real cost and the lock guards concurrency — but worth noting for any future async generator.
- Severity: **P3**.

---

## Principle 7: Structured logging — observability as correctness

*Carmack: automate what can be checked mechanically.*
*Ramírez: in an unattended scan, the log is the only witness. If it isn't structured, you can't query "why did Tuesday's scan find zero setups?"*

The scan runs unattended on a schedule. When it produces a wrong or empty result, the log is the entire forensic record — there's no user watching.

### What to check

**Logging architecture**
- Use the stdlib `logging` module with named loggers (`logging.getLogger("chrollo.scan")`, as the real code does), configured once at startup — not bare `print()` scattered through services. `print` can't be filtered, leveled, or routed, and competes with the SSE stdout the subprocess pattern depends on.
- Attach request context (the `request_id` middleware exists for this) so a failing request's logs are correlatable. Log scan outcomes as fields (status, n_setups, trigger), not prose, so degraded runs are queryable.
- Severity: **P3** for `print`-based logging in services. **P2** for unattended jobs that fail with no leveled log record.

**Don't log secrets or full payloads**
- IBKR credentials, webhook URLs, and tokens must never reach `error.log`. Truncate large error tails (the real `_tail_error` caps at 1000 chars; the alert truncates the error to 300) so a stack dump doesn't bury the signal or leak a path.
- Severity: **P1** for secrets in logs. **P3** for unbounded log payloads.

**Alert on degraded, not just failed**
- `_alert_decision` alerts on `failed`/`stale_data`, on **zero results when enabled**, and on a **healthy=False fetch** — an early warning before degradation escalates to a hard stale-data failure. Observability that only fires on a crash misses the slow rot of a thinning data fetch. Mirror this: warn on the leading indicator, not only the outage.
- Severity: **P2** for jobs that alert only on hard failure when a degraded-but-running state is detectable.

---

## Gaps: What This Doc Doesn't Cover

- **Security patterns**: SQL injection via `text()`, untrusted path/ticker handling, parquet/pickle deserialization trust, the yfinance pin and supply chain, secrets. Covered by **security.md (Hunt)**.
- **Data-store depth**: SQLite WAL/single-writer, type affinity, migration safety on the live archive, transaction boundaries, parquet atomic writes and adjusted-OHLC integrity. Covered by **quality-postgres.md (Brandur)**.
- **Numerical/detector correctness**: lookahead bias, NaN/inf propagation, float equality, rolling-window off-by-one, pandas index alignment, determinism/byte-parity. Covered by **quality-llm.md (McKinney)** — the highest-value doc.
- **Frontend patterns**: React 19 + Vite hooks, chart integration, render performance. Covered by **quality-frontend.md (Dodds)**.
- **Pipeline performance**: pandas vectorization, fetch/IO batching, chart render cost. Covered by the **pipeline performance skill**.
- **DevOps/scheduling**: the unattended scan scheduler, lock files, deploy hardening. Out of scope here — see the automation roadmap.

---

## Quick Reference: Severity Guide

| Severity | Pattern | Examples |
|----------|---------|----------|
| **P1 — Fix Now** | Errors that corrupt state, leak data, block the loop, or deadlock | Swallowed errors on detector/archive/cache; CPU-bound scan or subprocess inside `async def`; raw exception detail in the response; `core/` importing the web layer; module-level root-config read (boot crash); lock/handle cleanup outside `finally`; unreaped subprocess; secrets in source or logs |
| **P2 — Fix Soon** | Patterns that hide behavior, leak slowly, or diverge | Sync I/O on the loop; POST routes without a Pydantic model; ORM/internal objects returned without a response model; empty-as-success masking errors; logic duplicated from `core/`; decision welded to side effect; missing single-flight on scan/download; dependency lifecycle mismatch; status record not finalized on error; retry storms; alert only on hard failure |
| **P3 — Consider** | Transparency and hygiene | Heavy work hidden behind a dependency; inconsistent config access; `print`-based logging; unbounded log payloads; missing client-disconnect check |

### The Overriding Filter

Before writing any finding, apply the Carmack–Ramírez synthesis:

1. **Is this error handled or swallowed?** A silent swallow on detector or cache state ships a plausible wrong answer into a screener a human trades on — worse than a crash. Flag it.
2. **Is the event loop free?** If a CPU-bound scan, fetch, or subprocess runs inside `async def`, it stalls the one thread that serves everyone. Flag it.
3. **Is validation at the boundary?** If a route trusts an unvalidated body or a raw `dict` instead of a Pydantic model, flag it.
4. **Does `core/` stay pure?** If the engine imports the web layer, or a route reimplements engine logic, the byte-parity/seed-recall guarantees are gone. Flag it.
5. **Does every resource clean up on the error path?** Locks, subprocesses, status rows, and cache invalidation must release in `finally`, or the next unattended scan is wedged. Flag it.
