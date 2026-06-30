# Council Plan: Trade Enrich — Layer A (live open-trade risk, backend single source of truth)

**Scope:** Make a pure Python backend module the single source of truth for the **price-dependent** open-trade risk overlay (live price, unrealized P&L $ and %, R-multiple, distance-to-stop % and in R), expose it read-only, migrate the frontend consumers onto it, and enrich the Home "Open Book" zone + `PortfolioStatusBar`. Display only — no orders/modifications/broker actions.

**Context:** The risk math lives today entirely in `webapp/frontend/src/utils/tradeTableUtils.js::deriveTradeRow`, consumed by 6 surfaces. The backend already owns both live-price sources (the existing IBKR snapshot + the yfinance provider), and a clean read-only thin-service template exists (`services/engine_edge.py` + `routers/engine_edge.py`). This is additive enrichment over `models.TradeLog` — **no new tables, no migration** (`planned_stop` already ships in the model and the live DB).

**Boundaries:** Out of scope — Layer B (plan↔fill binding), Layer C (alerts/notifications), any broker action, any `core/` change. Off-limits files: `core/structure/metrics.py`, `tests/test_market_structure.py`, `tools/l2_staircase_*`, `tools/fidelity/l2/`.

**Council dispatched (all 9 returned recommendations):** Hunt (security), Fowler (structure), Dodds (frontend), Ramírez (backend), Leach (data), Performance, McKinney (numerical), Saarinen (UI), Friedman (UX).

---

## ⚠️ Load-bearing finding that reshapes the mandate (Fowler, confirmed in code)

"Migrate ALL frontend consumers and retire the JS risk math" must be read precisely. `summarizeFillLedger` (the **price-independent** fill ledger) is **not only display math** — `useTradeFills.js:173` reuses it to compute the **save payload** (`entry_price`/`quantity`/`commissions`/`exit_price`/`pnl`) PUT on fill edits, and `useTradeCellEditing.js` computes `position_size` inline on cell edits. Those are **write paths**; a read-only GET cannot serve a synchronous pre-save computation. Therefore:

- **Retire from JS:** only the **price-dependent risk overlay** (`currentExit`, `pnl`, `rValue`, `rToStop`, `distToStopPct`, stop tone, target-ladder distances) — this becomes single-source in Python.
- **Keep in JS:** the price-independent `summarizeFillLedger` + `parseActions` + the pure formatters (`fmtMoney`/`fmtInt`/`fmtDateShort`) — they back the save path and closed/draft-row display.
- The backend **ports the ledger internally** to derive open-trade risk, making it an unavoidable cross-language twin of the JS ledger — reconciled by the **parity test**, the house pattern for twins that cannot share one implementation. Fully centralizing the ledger (write side included) would require a write endpoint and is explicitly a later layer, not Layer A.

---

## Task Sequence

### 1. Pure risk-overlay module (the single source of truth)

| | |
|---|---|
| **Domain** | Ramírez × Carmack — Backend P4 (keep the pure layer pure) · Fowler P6 (earn the boundary) |
| **Ref** | `references/quality-backend.md` → P4 ; `references/refactoring.md` → P6 |
| **Depends on** | — |

Add `webapp/backend/services/trade_risk.py` as a **stdlib-only** pure module: a port of `summarizeFillLedger` plus the price-dependent overlay, taking a plain trade dict + a single live price and returning a derived dict. Zero FastAPI/SQLAlchemy/pandas/`config` imports and no module-level settings reads, so it resolves identically from the backend cwd (`webapp/backend`, bare imports) and the repo-root pytest gate. **Chair note:** placed under `services/`, **not** `core/` (Fowler suggested `core/`; the task forbids touching `core/` — this respects that boundary and keeps shadow/seed-recall out of play). Cross-ref: McKinney owns the port's numerical fidelity (Task 2 / Risks).

---

### 2. Parity test under `tests/` — the cutover gate

| | |
|---|---|
| **Domain** | McKinney × Carmack — Numerical P7 (byte-parity is the contract) · Fowler P8 (capture→parity method) |
| **Ref** | `references/quality-llm.md` → P7 ; `references/refactoring.md` → P8 |
| **Depends on** | Task 1 |

Add `tests/test_trade_risk.py` (the only path `pytest.ini`'s `testpaths=tests` collects) that inserts `webapp/backend` on `sys.path` locally and imports `services.trade_risk`. Mirror every existing `tradeTableUtils.test.js` case with a float-tolerant comparison (`pytest.approx(abs=1e-6)`) and identity checks for `None` (`rValue=0.5`, price-based `rToStop=1.5`, the partial-position `rValue=0.75`/`rToStop=1.5`, the SHORT case, the no-stop→`None` case), then add the new `planned_stop`-basis R, `pnl_pct`, and dist-to-stop-in-R cases. This test must be green before any consumer is swapped; it is the cutover gate, not a permanent cross-language job (it retires once the JS overlay is deleted).

---

### 3. Read-only price-resolution helper (snapshot + provider, coalesced)

| | |
|---|---|
| **Domain** | Performance × Carmack — Perf P5 (cache what's stable) / P2 (IO batching) · Ramírez P2 (never block the loop) |
| **Ref** | `references/quality-backend.md` → P2/P5 |
| **Depends on** | — |

Add an impure helper (separate from the pure math) that reads `get_ibkr_service().snapshot()` **exactly once**, projects it down to a per-ticker `market_price` map (discarding account/connection fields), and falls back to a **single de-duped** `get_provider().latest_price([missing])` call. Mirror `prices.py` precedence (IBKR first, then provider) and its `_scan_is_running` skip, carry a per-ticker `source`/`stale` flag, and wrap the whole resolution in the short-TTL+lock coalesce pattern from `engine_edge.py` (compute outside the lock). Cross-ref: Hunt (snapshot info-shape), Leach (read outside any transaction) — see Risks.

---

### 4. Read-only `/live-risk` endpoint + Pydantic contract

| | |
|---|---|
| **Domain** | Ramírez × Carmack — Backend P3 (thin route, explicit response model, degrade don't 500) |
| **Ref** | `references/quality-backend.md` → P3 ; cross-ref `references/quality-postgres.md` → P4 |
| **Depends on** | Tasks 1, 3 |

Add `routers/trade_risk.py` registered in `main.py`: a **plain `def`** GET (Starlette → threadpool, never `async def` around the blocking snapshot/provider calls) returning `{rows: {trade_id: RiskRow}, summary: OpenRiskSummary}` for **OPEN/partial trades only** — do not fold the price-independent full journal through the price path. Load open trades with an `IS NULL`-correct bounded query (mirror the FE predicate: `closing_date` null/empty AND `pnl` null AND ticker present; final open/partial refinement in the pure ledger). Parse `actions_json` with the FE's three-layer tolerance (non-array/malformed/bad-cell → empty/skip, never raise). Declare explicit `Optional[float]` response models and run every numeric through a `_finite`→`None` coercion. Keep the endpoint structurally read-only (read accessors only; no order-capable import; no mutating sibling in the router). Cross-ref: Hunt P2/P4/P7, Leach P4.

---

### 5. One shared `useLiveRisk` data hook

| | |
|---|---|
| **Domain** | Dodds × Carmack — Frontend P2/P7 (server state owned once, reuse the right primitive) · Fowler P5 (no twin fetches) |
| **Ref** | `references/quality-frontend.md` → P2/P7 |
| **Depends on** | Task 4 |

Add a single `useLiveRisk(trades)` hook that owns the `/live-risk` fetch, built on the existing visibility-gated `usePollingInterval` (compute `delayMs` 60s/20s from IBKR-connected state, exactly as `useTradeLivePrices` does), keyed off a stable joined open-ticker string so the timer doesn't reset every render, sending only open/partial tickers. It checks `response.ok` before `.json()`, surfaces one `status` value (`idle|loading|ready|stale|error`), and exposes a memoized `riskFor(tradeId)` accessor (returns a well-defined "no risk yet" shape, never `undefined`) plus the server-derived `summary`. Mount it once at the trades-data owner (`AppShell`) and thread `riskFor`/`summary` down as props exactly where `priceFor` is threaded today — never per-consumer fetches.

---

### 6. Migrate + enrich the live cockpit zones (Open Book + Action Center)

| | |
|---|---|
| **Domain** | Saarinen × Friedman × Dodds × Carmack — UI P1–P5 · UX P2/P6/P9 |
| **Ref** | `references/quality-ui.md` → P1–P5 ; `references/quality-ux.md` → P2/P6/P9 |
| **Depends on** | Task 5 |

Swap `deriveTradeRow`→`riskFor` in `OpenBookZone` and `ActionCenter`, and add the three new figures to Open Book (live price, P&L %, dist-to-stop in R). Apply the visual spine: a 3-tier read order (stop risk → signed P&L → context), each new figure **proximity-paired** as a sub-unit under its primary (P&L% under P&L$, distR under dist%) rather than new equal columns, **green/red reserved for sign only** (tier color stays on the flag), null/stale rendered as a quiet em-dash on faint ink (**never a colored zero**), and every live cell mono + tabular at fixed width so the poll never jitters the grid. Apply the UX states: distinguish a slow first poll (loading skeleton) from an empty book, make "no stop recorded → —" self-explaining and distinct from "no quote yet," surface per-row price provenance (live vs stale) even on flagged rows, and keep the refresh from re-sorting the row out from under the eye mid-glance.

---

### 7. Migrate RiskCockpit + the portfolio-position join

| | |
|---|---|
| **Domain** | Dodds × Carmack — Frontend P1 (kill the dual source) · Fowler P5 |
| **Ref** | `references/quality-frontend.md` → P1 |
| **Depends on** | Task 5 |

Point `RiskCockpit.jsx` at the shared `riskFor` (one consistent number, no second poll) instead of its own `useTradeLivePrices(trade)` + `deriveTradeRow`. In `portfolioPlanUtils.js`, the only risk use is `isOpenJournalTrade` reading a `status`; serve that status from the new derived row (or the retained price-independent ledger helper) so the JS overlay isn't kept alive for one field. The broker-position↔trade join logic (normalized-symbol + OPT/STK key) stays in the FE — it is a join, not risk math.

---

### 8. TradeTable seam — closed local, open server, optimistic echo

| | |
|---|---|
| **Domain** | Dodds × Fowler × Carmack — Frontend P2/P5 (derive what you can; no per-keystroke round-trip) · Refactoring P3 (contain state) |
| **Ref** | `references/quality-frontend.md` → P2/P5 |
| **Depends on** | Tasks 5, 7 |

`TradeTable` derives every row and re-derives synchronously on inline cell edits, so it must not block on a 20–60s poll. Split by status: closed/draft/win/loss rows derive **client-side** from the retained price-independent ledger (no live price needed); open/partial rows read `riskFor` from the server. On an inline edit, keep the optimistic local echo for the immediately-visible fields (entry/stop/qty/status) so the cell stays instant, then let the authoritative backend row replace it on the next poll / a targeted refresh — never round-trip the whole page before showing the edit, and never hold the derived row in a second `useState` mirror of server data.

---

### 9. Retire the JS risk overlay; keep ledger + formatters; fix the test surface

| | |
|---|---|
| **Domain** | Fowler × Hunt × Carmack — EC-3 (fold twin paths) · Security P5 (shrink the surface) |
| **Ref** | `conventions.md` → EC-3 ; `references/security.md` → P5 |
| **Depends on** | Tasks 6, 7, 8 |

Once all consumers read `riskFor`, delete the **price-dependent** risk math from `deriveTradeRow` (currentExit/pnl/R/dist/tone/ladder) so no dormant second risk engine can disagree with the backend. **Keep** `summarizeFillLedger`, `parseActions`, and the pure formatters (write/save path + closed-row display). Trim `tradeTableUtils.test.js` to drop the now-deleted risk assertions while retaining ledger/formatter coverage (no orphaned tests). Decide the home of `buildTradeAlerts`/`deriveTradeAlerts` deliberately — they currently call `deriveTradeRow`; rewire them to read `riskFor` rows (alerts proper are Layer C, out of scope).

---

### 10. PortfolioStatusBar aggregate open-risk strip

| | |
|---|---|
| **Domain** | Friedman × Saarinen × Carmack — UX P6 (metrics drive attention) · UI P1/P3 (ambient, one-accent) |
| **Ref** | `references/quality-ux.md` → P6 ; `references/quality-ui.md` → P1/P3 |
| **Depends on** | Task 5 |

Add an aggregate readout to `PortfolioStatusBar` from the server `summary` (total unrealized P&L, an "N at risk" count) so the most time-critical fact about the book is glanceable from the cockpit, not only inside the Open Book rows. Render it as **ambient muted text** beside the existing `Stream:`/`Updated` spans — not a third bordered pill that competes with the Live/Paper and IBKR-connection pills — with sign color on the P&L figure only, and suppress it to nothing (not "0 at risk") when the book is clean. Take the totals straight from `summary`; never re-sum per-trade R/$ on the client.

---

## Risks & Watchpoints

- **Fowler — write-path ledger boundary (EC-3 nuance):** `summarizeFillLedger` backs the fill-save payload and `position_size`; it is **not** retired. "Retire the JS risk math" = retire only the price-dependent overlay. The Python ledger is an unavoidable cross-language twin — parity-guard it (Task 2), don't claim EC-3 requires deleting it. Watch for a half-ported `deriveTradeRow` where some callers get server rows and some still compute risk.
- **McKinney — JS→Python idiom traps (highest-leverage correctness):** Port `Number(x)||0` / `parseFloat(x)||0` as one explicit `num_or()` helper (not `float()`/`or`), reproduce JS truthiness where **`0` is falsy** (`riskDistance && >0`, `&& currentExit`, `&& riskQty`, `&& openQty`) as explicit `is not None and != 0`, make every division degrade to `None` (no `ZeroDivisionError`), preserve the ledger `EPS=1e-9` comparisons and avg-cost reduction **order** bit-for-bit, anchor `\Z`/`fullmatch` on the three `isOptionSymbol` regexes (the 100× multiplier rides on them), keep the target ladder order-stable, and replicate the null-price fallback ladder exactly. Pair with a focused parity pass when building Task 1.
- **Leach — SSE writer starvation:** do the snapshot/yfinance reads **outside** any open SQLite transaction; a read held across a multi-second provider call can make the live execution-import writer hit the 30s busy-timeout. Pure read — no `.commit()`, no ORM mutation.
- **Performance — cold-Yahoo serial latency:** `latest_price` is internally sequential (up to ~12s bounded per symbol); the TTL coalesce (Task 3) + scan-skip + plain-`def` threadpool are what cap a multi-symbol cold poll from stalling the worker. De-dup tickers to a set before the provider call.
- **Hunt — snapshot info-shape leak:** `snapshot()` returns host/port/client_id/account_summary/full positions; project to per-ticker price inside the service and let only the declared `RiskRow`/`OpenRiskSummary` fields reach the response. Validate any client-supplied ticker/trade-id at the route (reuse the `prices.py` regex / typed `int`).
- **Saarinen — null-as-colored-zero is the single most dangerous visual item:** a missing quote must render `—`/`·` on faint ink, never a green/red `0`, or the trader reads "no data" as "flat, no risk" on a risk surface.
- **Friedman — slow-first-poll false negative:** a first-poll blank must not look like "No open positions"; and a through-stop flag computed from a stale quote needs visible provenance.
- **Live-cadence note:** IBKR position P&L shifts from SSE-push to the `/live-risk` poll cadence (20–60s). Acceptable for a discretionary swing trader, but it is a behavior change from the current SSE-driven Open Book; the existing `/stream/portfolio` SSE stays untouched for the Portfolio tab.

---

## External Setup Required

No external setup required. All tasks can be implemented within the codebase (read-only over existing models + the already-running IBKR snapshot; no API keys, no migration, no service signup).

---

## Summary

| # | Task | Domain | Depends on |
|---|------|--------|------------|
| 1 | Pure risk-overlay module (stdlib-only) | Ramírez / Fowler | — |
| 2 | Parity test under `tests/` (cutover gate) | McKinney / Fowler | 1 |
| 3 | Read-only price-resolution helper (coalesced) | Performance / Ramírez | — |
| 4 | Read-only `/live-risk` endpoint + Pydantic | Ramírez / Hunt / Leach | 1, 3 |
| 5 | Shared `useLiveRisk` hook | Dodds / Fowler | 4 |
| 6 | Migrate + enrich Open Book & Action Center | Saarinen / Friedman / Dodds | 5 |
| 7 | Migrate RiskCockpit + portfolio join | Dodds / Fowler | 5 |
| 8 | TradeTable seam (closed local / open server) | Dodds / Fowler | 5, 7 |
| 9 | Retire JS overlay; keep ledger + formatters | Fowler / Hunt | 6, 7, 8 |
| 10 | PortfolioStatusBar aggregate strip | Friedman / Saarinen | 5 |

## Verdict

The most important architectural decision is **the parity-gated split between the price-dependent risk overlay (centralize to Python) and the price-independent fill ledger (stays in JS for the write path)** — the council surfaced, and code confirmed, that the original "retire ALL the FE math" framing collides with the fill-save path, and getting this seam right is what keeps the migration honest (EC-3) without breaking optimistic editing. The most critical domain is **McKinney's numerical port**: this is a JS→Python translation where the live JS is the oracle, and a literal `float()`/truthiness port silently diverges on exactly the zero/blank boundary cases the trader's R and distance-to-stop depend on — so Task 2's float-tolerant parity test under `tests/` is the non-negotiable gate, and nothing downstream is trustworthy until it is green. **Start at Tasks 1–2** (pure module + parity test) and do not swap a single consumer until parity holds; then the backend (3–4) and the shared hook (5) unlock the consumer migration. The single highest-risk build moment is Task 8 (TradeTable's edit seam) — keep optimistic edits client-derived and let the server row be the post-save truth. A pair reviewer on McKinney's lane during Task 1 and on Saarinen's null-state rule during Task 6 would be well spent.
