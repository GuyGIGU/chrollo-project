# Spec: Multi-Universe Screener

**Date:** 2026-06-29
**Status:** Draft

## Objective

Run the existing Wyckoff/VCP/LPS setup engine over **three distinct universes** instead of
one, so the trader can read setups top-down — the broad market in stocks, then U.S. sectors
+ market indices, then commodities + thematic ETFs. When a sector or commodity ETF *itself*
sets up, that is the signal to drill into the tradable equities inside that theme. The
engine math does not change; the feature adds a **universe dimension** to a pipeline that
currently hardcodes a single universe everywhere.

## Context

Today the scan is hardwired to "all NASDAQ common stocks": the ticker source
(`core/pipeline/tickers.py`), the scan entry (`run_screener.py`), the output artifact
(`output/screener_data.json`), the market-data cache (`market_data_cache_5y.parquet`), the
archive uniqueness constraint (`(ticker, scan_date)`), the serving endpoint
(`GET /screener-data/`), and the scheduler all assume one universe. The same engine
(`_evaluate_frames`) already runs over *any* ticker list with no change, so this is a
**plumbing** feature: thread a `universe` dimension through those seams.

Two anchors already exist to build on: `SECTOR_ETF_NAMES` (the 11 SPDR sector ETFs, in
`output/dashboard.py`) / `SECTOR_RANKING_ETFS` (config), and the archive's existing
`source` column — the precedent to mirror for a `universe_type` column. ETFs are
*deliberately excluded* from the stock universe (`ETF == 'N'`), so the ETF universes must
come from explicit curated lists, not the NASDAQ feed. The engine's prime directive
(accurate tight-structure detection) and its byte-parity guards (`tools/shadow_diff`,
`core/archive/seed_recall`) make **non-regression of the existing stock universe** a hard
constraint. This feature feeds the cockpit (`docs/cockpit/`) — the universe switcher is the
top-down entry point.

## Scope

### In scope
- Three first-class universes: **(1) US Stocks** [existing], **(2) US Sectors + Market**,
  **(3) Commodities + ETFs** — each scanned by the same engine, stored/served/archived
  independently.
- A `universe` dimension threaded through: ticker source, scan entry + scheduler, output
  artifact path, market-data cache path, archive (`universe_type` column + constraint),
  and the serving endpoint.
- A **universe switcher** in the cockpit/screener that loads each universe's latest scan.
- **Top-down drill-down**: a firing sector ETF → its in-scan member stocks (via the
  existing sector→stock map); a firing commodity/thematic ETF → a curated related-equity
  basket.
- Correct market-relative scoring inputs for the small ETF universes (broad-market breadth/
  regime, not breadth-over-13-names).

### Out of scope
- Any change to the structure/geometry detector math or the setup-qualification logic.
- Tuning or calibrating the engine specifically for ETF price behavior.
- New external data feeds (constituents APIs, fundamentals) — the drill-down map is a
  curated static table, not a live feed.
- A configurable/user-editable universe builder (lists are curated in config).
- Backfilling historical scans for the two new universes.

### Non-goals
- Does not aim to make ETFs "qualify" — they pass or fail the same geometry veto as stocks.
- Does not optimize for adding a fourth universe cheaply, but should not preclude it.

## Stories

### Story 1: Scan three universes without them colliding

**When** the daily scan runs, **I want to** have each universe scanned by the same engine
and stored separately, **so I can** review stocks, sectors, and commodities independently
without one overwriting another.

**Acceptance Criteria:**

Given the scheduled scan time, when scans run, then all three universes are scanned by the
same engine and each result set is persisted to its own artifact and market-data cache.

Given a universe's scan completes, when its results are archived, then every row records
which universe it belongs to, and the same symbol can be archived for different universes on
the same date without a uniqueness collision.

Given the US-Stocks universe, when it is scanned through the new multi-universe path, then
its scan output is byte-identical to today's single-universe output (`shadow_diff --check`
and `seed_recall --check` stay green).

Given one universe's ticker list is empty, unreadable, or its scan errors, when scans run,
then the other universes still scan and persist and the failure is logged, without aborting
the batch or corrupting another universe's data.

Given a scan is already in progress, when another universe scan is triggered, then runs
serialize on the existing scan lock rather than racing on a shared cache.

### Story 2: Switch universes and read each screener

**When** I'm reviewing the market, **I want to** switch the cockpit/screener between the
three universes, **so I can** move top-down from the broad market to sectors to commodities.

**Acceptance Criteria:**

Given I'm on the screener/home, when I select a universe, then the grid/zones reload with
that universe's latest scan and the active universe is clearly indicated.

Given I selected a universe, when I reload or re-open the app, then my last-selected universe
is restored rather than silently reset to the default.

Given a universe has no scan yet, when I select it, then I see a clearly-labeled
"no scan yet for this universe" state — never stale data from another universe or a blank
grid.

Given the backend is asked for an unknown universe value, when the request is made, then it
returns a clear error or falls back to the default universe rather than serving mixed or
empty data silently.

### Story 3: Drill down from a firing ETF into its equities

**When** a sector or commodity ETF itself sets up, **I want to** jump from that ETF to the
related tradable equities, **so I can** find stocks riding a strong theme.

**Acceptance Criteria:**

Given a sector ETF (e.g. XLK) appears as a setup, when I drill in from it, then I see the
in-scan US-Stocks that map to that sector via the existing sector→stock mapping.

Given a commodity or thematic ETF appears as a setup, when I drill in from it, then I see its
curated related-equity basket.

Given a firing ETF has no mapping or no in-scan members today, when I drill in, then I see a
clearly-labeled "no related setups in today's scan" empty state, not a broken or blank list.

### Story 4: Keep scoring honest on small universes

**When** the engine scores an ETF universe of ~10–40 names, **I want to** have its
market-relative inputs reflect the broad market rather than the tiny universe, **so I can**
trust that the scores aren't distorted by a degenerate breadth reading.

**Acceptance Criteria:**

Given an ETF-universe scan, when setups are scored, then breadth/regime inputs reflect the
broad stock market, not breadth measured over the ETF universe itself.

Given an ETF-universe scan, when results are produced, then any score component that is
meaningless over a tiny universe is neutralized rather than applied with a degenerate value.

Given the US-Stocks universe, when it is scored under the new context-sourcing, then its
scores are unchanged (byte-identical guard stays green).

## Boundaries

### ✅ Always
- Thread a universe dimension through the **existing** scan chain, archive writer, dashboard
  generator, serving endpoint, and screener grid — never fork a parallel copy of any of them.
- After every step, run the regression guards: `python -m tools.shadow_diff --check`,
  `python -m core.archive.seed_recall --check`, `python -m pytest -q`, and the frontend
  build; the US-Stocks universe output must stay byte-identical throughout.
- Store each universe's scan artifact and market-data cache under its own path, and record
  `universe_type` on every archived row.
- Follow existing patterns: per-universe CSV like the current `tickers.csv`; a query-param
  on the existing endpoint; plain-fetch + useState React hook; config-driven lists.

### ⚠️ Ask first
- The archive schema migration — adding `universe_type` and widening the `(ticker, scan_date)`
  uniqueness constraint (SQLite cannot ALTER a constraint; this needs a guarded table rebuild).
- The exact membership of each universe (the "Market" indices, the thematic-ETF set) and the
  contents of the commodity→equity drill-down mapping table.
- Changing the scan schedule/cadence, or running universes in parallel instead of serially.
- Any change to scoring inputs (the ETF-universe breadth/regime sourcing) before it is gated
  against the byte-identical guards.

### 🚫 Never
- Modify the owner's in-progress files: `core/structure/metrics.py`,
  `tests/test_market_structure.py`, `tools/l2_staircase_audit.py`,
  `tools/l2_staircase_render.py`, `tools/fidelity/l2/`.
- Regress the US-Stocks universe — no change that alters its scan output. If shadow/seed-recall
  drift, STOP and diff; do not re-baseline to make it pass.
- Change the structure/geometry detector math to make ETFs "qualify" — geometry stays the only
  veto; this feature adds a universe, not new setup logic.
- Place orders or execute trades from any screener surface — read-only context only.
- Leave any hardcoded single-universe path that lets one universe's artifact, cache, or
  archive rows overwrite another's.

## Success Metrics

- All three universes scan on the schedule; each serves its own latest result via the
  universe-parameterized endpoint; switching universes in the UI shows distinct, correct
  result sets with zero cross-contamination.
- US-Stocks output is byte-identical: `shadow_diff --check` and `seed_recall --check` green
  before and after; full `pytest -q` suite green; frontend build green.
- A firing sector ETF resolves to its in-scan member stocks in one click; a firing
  commodity/thematic ETF resolves to its curated basket or a labeled empty state.
- No archived row is universe-ambiguous — every row carries `universe_type`, and the same
  symbol+date can coexist across universes.

## Assumptions

- (confirmed) Three universes — (1) US Stocks [existing], (2) US Sectors + Market,
  (3) Commodities + ETFs — all run the same engine; built via the Council spec→plan pipeline;
  drill-down covers sectors **and** commodities.
- (confirmed) Universe #3 = the commodity list (GLD/SLV/COPX/WEAT/CORN/UNG/PALL/PPLT/UGA/USO/
  CANE) **plus** major thematic/industry ETFs (e.g. SMH / XBI / IBB / KRE / ITB-class).
- (unconfirmed) Universe #2 "Market" = SPY / QQQ / IWM (+ DIA) alongside the 11 SPDR sector
  ETFs. Override if you want more indices or sub-sector ETFs.
- (unconfirmed) Storage = one artifact + one cache file per universe (multi-file); scans run
  sequentially on the existing daily cadence and shared scan lock. Override for a single merged
  artifact or staggered/parallel runs.
- (unconfirmed) The commodity→equity drill-down ships with a **seeded starter mapping**
  (e.g. GLD → GDX/NEM/GOLD; COPX → FCX/SCCO; USO/UNG → energy E&Ps), expandable later.
  Override the seed contents.
- (unconfirmed) ETF-universe scoring anchors breadth/regime to the broad stock market and
  neutralizes the breadth bonus over tiny universes. Override if you want per-universe breadth.

---

*After implementing, compare results against each acceptance criterion above and list any unmet requirements.*
