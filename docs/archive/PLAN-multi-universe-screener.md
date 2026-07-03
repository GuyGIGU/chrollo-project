# Council Plan: Multi-Universe Screener

**Scope:** Run the existing setup engine over three universes — US Stocks (existing), US Sectors + Market, Commodities + ETFs — each scanned, stored, served, and archived independently, with a universe switcher and top-down ETF→equities drill-down. The engine math does not change; a single `universe` dimension is threaded through the plumbing.
**Context:** Today the universe is hardcoded at six seams (ticker source, scan entry, output artifact, parquet cache, archive constraint, serving endpoint). The engine (`_evaluate_frames`) already runs over any ticker list. The hard constraint is non-negotiable: the US-Stocks scan output must stay **byte-identical** (`shadow_diff --check` + `seed_recall --check` green) throughout.
**Boundaries:** No detector/geometry math changes; no ETF-specific calibration; no live constituents feed (drill-down is a curated static map); no configurable universe builder; no historical backfill of the new universes; read-only (never places trades); the owner's 5 WIP files are off-limits.
**Council dispatched:** All 9 seats returned recommendations — Hunt (Security), Fowler (Structure), Dodds (Frontend), Ramírez (Backend), Leach (Data Integrity), Performance, McKinney (Numerical), Saarinen (UI), Friedman (UX).

---

## Task Sequence

### 1. Universe descriptor — thread one object through, lock US-Stocks byte-parity

| | |
|---|---|
| **Domain** | Martin Fowler × Carmack — Primitive Obsession / Data Clumps; Two Hats (refactoring.md → P5, P8) |
| **Ref** | `references/refactoring.md` → P5, P8 |
| **Depends on** | — |

Replace the five scattered single-universe string literals (ticker-CSV path, parquet `CACHE_FILENAME`, the `screener_data.json` artifact name, the archive tag, the index/breadth symbol set) with one immutable Universe descriptor defined once in config — key, display name, ticker source, artifact path, cache path, context-source field, index set, `universe_type`. Widen `run_screener` / `scan_job` / `generate_dashboard` / `archive_scan_results` / the serving read to accept that descriptor (never fork an `_etf` copy), and resolve the literal-to-path mapping in exactly one place. The US-Stocks descriptor must resolve to the **exact current literals** so routing the existing universe through the new chain is a pure refactor — land this behavior-preserving step **first**, validated green by `shadow_diff --check` + `seed_recall --check`, before any ETF universe exists. Cross-ref: this closed descriptor set IS the security allowlist (Hunt) and the single canonical key-set (Leach); anchor each resolved path under the project root, not cwd (Hunt — see Risks).

---

### 2. Curated universe lists + commodity→equity map as inert config data

| | |
|---|---|
| **Domain** | Martin Fowler × Carmack — Speculative Generality / YAGNI (refactoring.md → P1) |
| **Ref** | `references/refactoring.md` → P1 |
| **Depends on** | Task 1 |

The two ETF universes and the commodity→equity drill-down are explicitly curated static tables, so they belong as flat config data files mirroring the existing `tickers.csv` / `SECTOR_ETF_NAMES` precedent — **not** a pluggable resolver, universe-registry, or builder abstraction. Author: the Sectors+Market list (11 SPDR sectors + the market indices), the Commodities+ETFs list (the commodity set + thematic/industry ETFs), and the static commodity→equity basket map. The descriptor plus three flat lists is the entire abstraction that pays off at three universes. (Contents are a domain decision — see External Setup.)

---

### 3. Archive migration — widen identity to (ticker, scan_date, universe_type)

| | |
|---|---|
| **Domain** | Brandur Leach × Carmack — Migrations are production operations; Constraints are assertions (quality-postgres.md → P3, P1) |
| **Ref** | `references/quality-postgres.md` → P3, P1 |
| **Depends on** | Task 1 |

Adding `universe_type` to the UNIQUE key is the one SQLite migration that cannot be done in place — it requires the explicit table-rebuild (create new-schema table with the 3-column constraint, `INSERT…SELECT` all rows across, drop old, rename) inside **one transaction**, registered as a one-off in `_MIGRATIONS` (never via the ADD-only model-diff auto-migrator, which would silently leave the old narrow constraint in force). In the same transaction, backfill every existing row to `us_equities` and declare the column `NOT NULL` with a constant default + a `CHECK` constrained to the three known keys (the CHECK can only be attached at table-creation, i.e. during this rebuild). Add an index whose leading column serves the universe-filtered reads (recall, forward-return backfill, browse). **Dry-run discipline:** run the rebuild against a file copy of `trading_journal.db` first, assert post=pre row count and that the only schema delta is the new column + widened constraint, and take a backup before touching the live DB. Cross-ref Hunt (atomic + backed-up).

---

### 4. Broad-market context sourcing for ETF universes (Story 4 correctness)

| | |
|---|---|
| **Domain** | Wes McKinney × Carmack — Units/scale consistency; lookahead; NaN quarantine (quality-llm.md → P10, P1, P2) |
| **Ref** | `references/quality-llm.md` → P1, P2, P5, P10 |
| **Depends on** | Task 1 |

`_compute_breadth` counts Close>SMA over the scanned frames — meaningful over ~6000 stocks, degenerate over 10–40 ETFs (a coarse 0/13…13/13 step). For ETF universes, source breadth and regime-breadth from the **broad stock panel** (computed once during the stocks scan, which runs first) — never recomputed over the ETF members — and neutralize the breadth-derived score component with a single explicit sentinel that `_ramp` maps to **0.0 bonus** (not a NaN, not a partial-denominator ratio). The SPY-based inputs (`spy_6m_return`, per-name `excess_return_6m`) stay as-is — SPY is a real benchmark, only universe-counted breadth is degenerate. Namespace the `market_context.json` cache per universe (stocks keeps its exact current filename so its key/contents are unchanged), gate the broad-market borrow on the stock panel and ETF panel sharing the **same as-of bar date** (fall back to neutral when they disagree — no lookahead), and harden every per-ETF index/ratio read with the existing length guards (`> RS_LOOKBACK_BARS`, 50/200-bar SMA/slope) so a young thematic ETF degrades to None/neutral rather than throwing or producing a silent NaN. Cross-ref Performance (compute-once-and-share is the same seam) + Fowler (context-source is a descriptor field distinct from scan membership).

---

### 5. Scan orchestration — three sequential universe runs, isolated failure

| | |
|---|---|
| **Domain** | Sebastián Ramírez × Carmack — Streaming/subprocess cleanup; programmer-vs-operational errors (quality-backend.md → P6, P1) |
| **Ref** | `references/quality-backend.md` → P1, P6 |
| **Depends on** | Tasks 1, 2, 4 |

Run the three universes **sequentially** in the existing scan subprocess under the single `SCAN_LOCK`, ordered **stocks first** so its broad-market context (Task 4) and already-fetched SPY/QQQ index frames feed the ETF scans (no redundant index re-fetch, no parallel contention on the CPU pool or the Yahoo rate budget). One universe's empty/unreadable list or scan error must be isolated (log it, mark that universe's scan-status, continue) and every exit path must finalize the run-status record and release the lock in a `finally`. Each universe writes its own parquet cache atomically (tmp-then-`os.replace`, tmp beside target) and never invalidates another's; worker-pool sizing flows through the existing `min(cpu, n)` clamp in `_evaluate_frames` (no fork, no fixed pool) so the ~15/25-name scans don't pay a disproportionate spawn tax. Cross-ref Performance (serial/ordering/pool/cache) + Leach (short per-universe write).

---

### 6. Archive writer — universe-aware upsert + per-universe transactions

| | |
|---|---|
| **Domain** | Brandur Leach × Carmack — Transactions are the unit of correctness; upsert races (quality-postgres.md → P2, P4) |
| **Ref** | `references/quality-postgres.md` → P2, P4 |
| **Depends on** | Tasks 3, 5 |

Stamp `universe_type` on every archived row, and make the writer's upsert resolve conflict on the widened 3-column key (push it onto an `ON CONFLICT` against the new UNIQUE rather than the current non-atomic SELECT-then-INSERT/UPDATE), so a symbol that legitimately exists in two universes on the same date (e.g. SPY in Stocks and Market) inserts alongside instead of clobbering. Each universe's archive write is its own short transaction with fetch/compute/sector-resolution done **outside** the open transaction (keep the existing deferred-commit posture); a failure mid-universe must never roll back a sibling universe that already committed cleanly.

---

### 7. Serving endpoint — universe-parameterized read, closed set

| | |
|---|---|
| **Domain** | Sebastián Ramírez × Carmack — Validate at the boundary; dependency/cache lifecycle (quality-backend.md → P3, P5, P4) |
| **Ref** | `references/quality-backend.md` → P3, P4, P5 |
| **Depends on** | Task 1 |

Add a `universe` query param to `GET /screener-data/` typed as a closed Enum/Literal of the three keys, **defaulting to US-Stocks** so a param-less request returns today's exact payload from today's exact path (byte-identical contract preserved, no parallel route). FastAPI rejects unknown universes with a 422 at the edge before any value touches a filename; a **valid** universe whose artifact doesn't exist yet returns an explicit "not scanned yet" sentinel (like `scan-status/latest`'s `status:"never"`), distinct from a genuinely empty scan. Re-key the module-level cache in `services/screener_data.py` per universe (mtime+data per key; `invalidate` clears one universe without nuking the others), keep the route a plain `def` over the service layer, and resolve universe→path through the single descriptor mapping (Task 1) — not inlined in the handler. Cross-ref Hunt (the Enum is the allowlist; route the `universe_type` archive filter through the parameterized ORM expression, never a text()/f-string clause) + Performance (cache holds all three).

---

### 8. Frontend data layer — universe in the URL, parameterized fetch, status model

| | |
|---|---|
| **Domain** | Kent C. Dodds × Carmack — Eliminate derivable state; server state ≠ UI state; status model (quality-frontend.md → P2, P3, P6) |
| **Ref** | `references/quality-frontend.md` → P2, P3, P6 |
| **Depends on** | Task 7 |

The active universe's single source of truth is the **URL** (route segment / query param), so ScreenerGrid and HomeView agree by construction and Story-2 restore-on-reload comes for free. `useScreenerData` takes the universe as an argument and refetches on change, **clearing the prior universe's payload instantly** so a slow fetch can't paint stale data under the new label, and exposes one explicit `status` (loading / ready / empty / error) — the not-scanned sentinel maps to `empty`, non-200 to `error` — that the grid switches on instead of inferring from null. Hold a small client-side map of already-loaded universe payloads so switching back is instant and tier/score/tag filtering stays the existing client-side operation (switching is a load, never a re-scan). Build the small switcher helpers inline/colocated — resist a universe Context/registry abstraction for three fixed universes. Cross-ref Performance (client cache) + Friedman (switch=load).

---

### 9. Frontend — switcher, active-universe disambiguation, per-universe states

| | |
|---|---|
| **Domain** | Karri Saarinen + Vitaly Friedman × Carmack — Reduce noise/One-Accent; five screen states; trust (quality-ui.md → P1,P3,P5; quality-ux.md → P1,P2,P9) |
| **Ref** | `references/quality-ui.md` → P1,P3,P5,P8,P10 · `references/quality-ux.md` → P1,P2,P9 |
| **Depends on** | Task 8 |

One calm, always-visible 3-way segmented control (Stocks / Sectors+Market / Commodities+ETFs) near the top of the screener/home content — a dimension **of** the screener, not a third nav tier or a buried dropdown — reusing the existing toolbar-pill grammar; **Signal Blue marks the active segment only** (no per-universe categorical hues — that would break the blue=interactive contract). A visible "which universe" label on the grid, the freshness stamp, the card detail modal, and the Home Fresh-Setups tile so a setup is never misattributed across universes. Design all five states **per universe independently**: the "no scan yet for this universe" empty state must be distinct from "scan ran, zero qualified" and from "stale," reuse the existing muted `EmptyState` grammar, and never fall through to another universe's grid. On the two ETF universes, quietly signal that breadth is anchored to the broad market and the breadth component is neutralized (honest instrument — the number must not look more authoritative than it is). Tier badges go through the existing `tierColor()`/`--tier-*` tokens and mini-charts through the unchanged whitewashed-bar model — zero per-asset-class theming. (Saarinen owns the visual execution; Friedman owns the IA/state completeness — kept together as one build.)

---

### 10. Frontend — top-down drill-down (ETF → equities)

| | |
|---|---|
| **Domain** | Vitaly Friedman × Carmack — Progressive disclosure needs visible triggers; honest empty states (quality-ux.md → P4, P2) |
| **Ref** | `references/quality-ux.md` → P4, P2 · `references/quality-ui.md` → P1 · `references/quality-frontend.md` → P2 |
| **Depends on** | Task 9 |

A firing sector/commodity ETF card carries **one explicit, labeled drill affordance** ("Members →" / "Related stocks →") that is visually separate from the card's existing chart-open click, and appears **only** on ETF cards that actually resolve to in-scan members — so its presence is itself the signal that drill-down exists. Drilling is **derived navigation**: compute the member set at render from the sector→stock map (or the static commodity map) intersected with the loaded scan — not stored state that goes stale on the next scan — landing in the same `ScreenerCard` grid with a quiet lineage header naming the parent ETF and a back path. Make the cross-universe hand-off explicit (a Sectors-universe ETF drills into **stock-universe** results, with its own freshness stamp). Empty results render an honest labeled state that distinguishes "no curated mapping for this ETF" from "mapped names exist but none fired today." Cross-ref Saarinen (drill chip + lineage header visual) + Dodds (derived nav, no stored member list).

---

## Risks & Watchpoints

- **McKinney — Determinism / byte-parity is the contract:** Capture `screener_data.json` + `seed_recall` output **before** any edit; through Tasks 1, 3, 4, 5, 6 any drift on the stock path is a bug to *locate*, never a baseline to refresh. Pair with the numerical lens during Task 4 — the breadth-sourcing change is the one most likely to perturb the stock path if patched in place rather than carried as descriptor data.
- **Ramírez — The config-vs-cwd trap:** The new universe config lives in the repo-root `config/` package, which the backend cwd shadows. Reach it **lazily inside the function that needs it** (`load_core_settings()` / explicit-path), never a module-level `from config import …` in `core/` or services — or it passes tests (run from root) and crashes the service on boot. Applies to Tasks 1, 2, 4, 5, 7.
- **Leach — WAL sidecars on the migration dry-run:** When snapshotting `trading_journal.db` for the Task-3 rehearsal, copy the `-wal`/`-shm` sidecars too (or checkpoint first), or you validate the rebuild against stale data that silently lost recent writes.
- **McKinney — As-of-bar misalignment:** If the stock panel and an ETF panel last-bar dates differ (one refreshed on a day the other didn't), borrowing the newer stock context is lookahead. Gate the borrow on matching dates; fall back to neutral regime. (Task 4.)
- **Performance/yfinance — Concurrent-candle hazard:** Do not parallelize universe fetches; the existing per-ticker single-symbol download path avoids the non-thread-safe `yf.download` global. The separate backend candle-race fix (spawned earlier as a background task) is independent of this plan.

---

## External Setup Required

| # | What | Why | Blocking task |
|---|------|-----|---------------|
| 1 | Confirm/finalize the **Universe #2 membership** — the "Market" indices to pair with the 11 SPDR sectors (default seed: SPY/QQQ/IWM/DIA). | Defines the Sectors+Market ticker list authored in Task 2. | Task 2 |
| 2 | Confirm/finalize the **Universe #3 thematic-ETF set** to pair with the commodity list (default seed: SMH/XBI/IBB/KRE/ITB-class). | Defines the Commodities+ETFs ticker list authored in Task 2. | Task 2 |
| 3 | Confirm the **commodity→equity drill-down map** contents (default seed: GLD→GDX/NEM/GOLD; COPX→FCX/SCCO; USO/UNG→energy E&Ps). | Drives the Task-10 commodity drill-down; the sector→stock map already exists. | Task 10 |

*These are curation decisions, not infrastructure — I can seed sensible defaults and you edit; nothing requires API keys or external services. All code lands within the repo.*

---

## Summary

| # | Task | Domain | Depends on |
|---|------|--------|------------|
| 1 | Universe descriptor + US-Stocks byte-parity lock | Fowler | — |
| 2 | Curated lists + commodity→equity map (config data) | Fowler | 1 |
| 3 | Archive migration — widen identity key (table rebuild) | Leach | 1 |
| 4 | Broad-market context sourcing for ETF universes | McKinney | 1 |
| 5 | Scan orchestration — 3 sequential runs, isolated failure | Ramírez | 2, 4 |
| 6 | Archive writer — universe-aware upsert + txns | Leach | 3, 5 |
| 7 | Serving endpoint — universe param, closed set | Ramírez | 1 |
| 8 | Frontend data layer — URL state + status model | Dodds | 7 |
| 9 | Switcher + disambiguation + per-universe states | Saarinen + Friedman | 8 |
| 10 | Top-down drill-down (ETF → equities) | Friedman | 9 |

## Verdict

The one architectural decision that carries this feature is **Task 1**: a single Universe descriptor threaded (never forked) through the chain, with US-Stocks defaulting to bit-for-bit current behavior. Get that right and everything else is additive and individually gated; get it wrong — fork an ETF copy, or expand a bare `universe` string into paths at six seams — and you reintroduce exactly the twin-path drift the eval-twins fold was created to kill, against a byte-parity guard that will fail with no obvious cause. Two domains are co-critical and both are about *not corrupting trusted state*: **Leach's** archive migration (Task 3) is the only irreversible operation here — the historical archive is the non-reconstructable forward-return ground truth, so the rebuild must be rehearsed on a copy with row-count verification before it touches the live DB; and **McKinney's** breadth-sourcing fix (Task 4) is where a careless patch silently perturbs the stock path or feeds the ETF screener a meaningless signal. Start at Task 1, land and **commit it byte-parity-proven before a single ETF universe exists** (Two Hats), then fan out 2/3/4/7 in parallel. Pair the numerical lens through Tasks 1, 4, 5; treat Task 3 as the operation you rehearse, not the one you improvise.
