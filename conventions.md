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

---
