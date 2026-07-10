# Project Conventions

Accepted patterns and enforced conventions from council reviews. The council reads this file before every
review to avoid re-flagging resolved decisions.

---

## Accepted Patterns

These are intentional — do not flag as findings.

### AP-1: `us_stocks` key vs `us_equities` universe_type split
**Pattern:** The default universe's `key` is `us_stocks` (API/cache token) while its archive `universe_type` is
`us_equities`; the other two universes use one token for both. Do NOT propose migrating the archive tag to match
the key.
**Origin:** Fowler / Hunt — Council Review 2026-06-30-1124
**Rationale:** Renaming the live archive tag is a live-SQLite migration for cosmetic gain; the boundary leak it
caused is closed by EC-1 instead (the split lives, correctly, only inside `universe.py`).

### AP-2: `fetch_data` cold/incremental/repair state machine
**Pattern:** `core/pipeline/downloads.py` `fetch_data` is a ~70-line lock→scope→fresh?→current?→incremental?→cold
sequence of named `_try_*`/`_*_result` helpers with IO/mutations visible at the helper boundaries. Do NOT
"simplify" or split it further.
**Origin:** Fowler (LEAD) — Council Review 2026-06-30-1124
**Rationale:** It is a well-factored state machine, not a god-function; the sequencing is clear and the state is
contained.

### AP-3: Per-call `Universe` registry build + lazy settings reads
**Pattern:** `core/pipeline/universe.py` rebuilds the registry per call and reads settings at call time (not
module-level attribute reads). Do NOT hoist the registry to a module-level materialization.
**Origin:** universe.py design — Council Review 2026-06-30-1124
**Rationale:** Avoids the config-vs-cwd shadowing trap (the backend cwd shadows the repo-root `config` package).

### AP-4: `yfinance==1.2.1` exact pin
**Pattern:** `requirements.txt` pins yfinance to an exact `==1.2.1`. Never bump it as a "stale dependency" finding.
**Origin:** Hunt — Council Review 2026-06-30-1124
**Rationale:** An unattended scan breaks (and silently archives wrong setups) if a yfinance release changes
Yahoo's scraper / OHLC adjustment — it is a supply-chain + byte-parity control, upgraded only deliberately.

### AP-5: The price-independent fill ledger is a necessary JS↔Python twin
**Pattern:** `summarizeFillLedger` (and the price-independent half of `deriveTradeRow`) stays in
`webapp/frontend/src/utils/tradeTableUtils.js` even though `webapp/backend/services/trade_risk.py`
ports the same ledger. The JS copy backs a WRITE path (the fill-save payload in `useTradeFills` +
inline `position_size` in `useTradeCellEditing`) that a read-only GET cannot serve. Do NOT flag this
as a dual implementation / EC-3 violation — it is a deliberate cross-language twin reconciled by the
parity test (`tests/test_trade_risk.py`).
**Origin:** Fowler / McKinney — Council Review 2026-06-30-1338
**Rationale:** Only the price-DEPENDENT live overlay was centralized; the ledger twin is forced by the write path.

### AP-6: `_js_number(None) == 0.0` in `trade_risk.py` is intentional
**Pattern:** `services/trade_risk.py` maps `None`→`0.0` (mirroring JS `Number(null)`), which differs from
JS `Number(undefined)=NaN` only on a literally key-absent `entry_price`. Do NOT "fix" `infer_direction`
to treat `None` as not-knowable: the router always materializes `entry_price` present-as-None (the
agreeing case), so the current code matches JS on every reachable input, and the proposed fix would
INTRODUCE a divergence on the reachable present-null case.
**Origin:** McKinney — Council Review 2026-06-30-1338
**Rationale:** Parity is correct on the whole reachable input domain; the divergence is unreachable.

---

## Enforced Conventions

These must be followed — flag violations as findings.

### EC-1: One source for the equities-default scope
**Convention:** Any universe-scoped archive read that defaults to the equities population MUST derive its default
from `core.pipeline.universe.DEFAULT_UNIVERSE_TYPE` (or `default_universe().universe_type`) — never a bare
`"us_equities"` string literal re-typed at the call site.
**Origin:** Fowler / Ramírez — Council Review 2026-06-30-1124
**Principle:** `references/refactoring.md` → P4/P5 (Inconsistent Vocabulary / Shotgun Surgery)

### EC-2: NaN-coerce archive cells at the pandas boundary
**Convention:** When projecting archive rows read via pandas (e.g. `read_sql_query` → `itertuples`), coerce
possibly-missing cells with `pd.isna(...)` (or an explicit `is None` check), NEVER a truthiness test — `bool(np.nan)`
is `True`, so a SQL `NULL` leaks the literal `"nan"` into grouping/identity keys.
**Origin:** McKinney / Beck — Council Review 2026-06-30-1124
**Principle:** `references/quality-llm.md` → P2 (NaN/dtype at the boundary)

### EC-3: Fold twin code paths, never copy
**Convention:** Logic that must agree across call sites (eval-twins, `_weekly_refresh_due`, depth/coverage/scope
predicates) must live in ONE shared implementation that both sites import — not two separately-maintained copies.
**Origin:** Fowler — Council Review 2026-06-30-1124
**Principle:** `references/refactoring.md` → P5 (twin code paths)

### EC-4: A widened identity key must be threaded through EVERY writer
**Convention:** When the archive identity key is widened (e.g. adding `universe_type`), every writer — live
screener, seed, forward-returns/manual — must stamp the new column AND include it in its existence/upsert check,
not just the primary writer.
**Origin:** Leach — Council Review 2026-06-30-1124
**Principle:** `references/quality-postgres.md` → P1/P4 (constraints are assertions; upsert matches the key)

### EC-5: Live open-trade risk is derived once, server-side
**Convention:** The price-dependent live-trade risk overlay (live price, unrealized P&L $/%, R-multiple,
distance-to-stop %/R, stop tone, target distances) is derived ONLY in `webapp/backend/services/trade_risk.py`
(the single source of truth); the frontend consumes it via the `riskFor` accessor. Never re-add a live-risk
computation in JS. R-multiple/`riskDistance` anchor 1R to `planned_stop`→`stop_loss`→None (never fabricated);
distance-to-stop and the stop tone use the CURRENT working `stop_loss` on both sides.
**Origin:** Fowler / McKinney — Council Review 2026-06-30-1338
**Principle:** `references/refactoring.md` → P5 (twin code paths) ; `conventions.md` EC-3

### EC-6: `/live-risk` degrades, never 500s
**Convention:** The read-only `GET /live-risk/` must degrade to null-price rows on any operational failure,
never raise: parse `actions_json` tolerantly (drop non-dict cells), coerce the live price at the boundary,
read only the EXISTING IBKR snapshot (no new connection) and release the DB read before the price fetch.
Programmer errors may still surface (do not blanket-swallow); operational failures log + degrade.
**Origin:** Leach / Ramírez / Hunt — Council Review 2026-06-30-1338
**Principle:** `references/quality-backend.md` → P1 (operational vs programmer errors)

### EC-7: Operator-marks corpus files are immutable test specs
**Convention:** Files under `docs/marks/` are operator ground truth and acceptance specs: grow them
append-only; corrections land only as explicit operator source-upgrades (extraction→operator), never
silent in-place edits; a failing corpus case is fixed in the ENGINE — never by editing a mark, widening
a matcher's date window, or reinterpreting trigger rules. Harnesses consuming a corpus must validate it
loudly (malformed/unrecognized marks fail the run, never skip) and detect unsanctioned edits.
**Origin:** Beck / Leach — Council Plan 2026-07-09-2200 (whole-chart event read); operator-confirmed 2026-07-10
**Principle:** `references/quality-testing.md` → P10 (the test spec is the constraint); `references/quality-postgres.md` → P1

### EC-8: Every new engine flag ships with the full flag protocol in one change
**Convention:** A new engine behavior flag must land in the SAME change as: registration in the frozen
settings manifest (`core/freeze`) AND the dark-flag ledger (`tests/test_invariants.py`); a unit-level
inert test in its home module; one flag-off frozen-fixture pipeline replay asserting equality with the
shadow baseline; and an agreed scan-metrics evaluation-phase cost bound measured before the operator
flips it live. Flag-off must be byte-identical and compute-free.
**Origin:** Beck / Leach / Performance — Council Plan 2026-07-09-2200 (whole-chart event read); operator-confirmed 2026-07-10
**Principle:** `references/quality-testing.md` → P5; `references/quality-postgres.md` → P1; `references/quality-performance.md` → P1

---
