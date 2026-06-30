# Council Review: Multi-Universe Screener — Architecture Verdict

**Scope:** The `universe_type` architecture holistically (per-universe descriptor / cache / identity-key /
read-side scoping) on the current working tree — i.e. AFTER the 0041 council fixes (`e8da04f`+`39766b6`)
and the 13 uncommitted follow-up fixes, including the NaN-coercion bug an adversarial pass caught mid-review.
**Question asked:** refactor/rebuild, or keep fixing surgically?
**Council dispatched:** all 10 — Hunt (4), Dodds (4), Ramírez (5), Leach (3), Performance (4), Saarinen (7),
Friedman (5), Fowler/LEAD (6), McKinney (5), Beck (8). 51 raw → 17 after dedup/Carmack-filter.
**Automated gates:** pytest **604 passed** (incl. seed-recall + shadow baselines — engine output unchanged);
compileall clean. yfinance pin verified exact (`==1.2.1`).

---

## VERDICT FIRST: Surgical, not a rebuild — with one targeted refactor

**All ten seats independently returned "sound — keep fixing surgically."** The load-bearing decision is right:
one immutable `Universe` descriptor that owns ticker source + cache paths + regime set + archive tag, resolved
at call time (dodging the config-vs-cwd shadow), with a closed-set allowlist (`resolve_universe` → `ValueError`),
project-root path anchoring (no cwd cross-write), per-universe cache isolation (the prior P1 is closed), and a
correctly-modeled 3-col identity key (`NOT NULL` + `CHECK` + `server_default` — verified to survive the migration
rebuild, so there is **no NULL/identity ambiguity at the DB layer**). Adding a fourth universe is genuinely one
registry entry. The engine is byte-parity-locked and green.

**The "leaks at a different seam each round" pattern is NOT one bug recurring — it is distinct boundaries
(cache write → archive scope → episode identity → health scope → metadata lock) each being closed once as the
descriptor's reach extended outward from the engine core to the read surfaces.** That is normal hardening of a
young abstraction reaching its edges, not a leaky design thrashing.

**BUT there is exactly ONE genuine cross-cutting inconsistency worth a targeted refactor** (Finding 1): the
read-side "equities is the default scope" policy is a hand-typed string literal `"us_equities"` re-pinned at ~9
independent sites, while the *write* side correctly derives it from `default_universe().universe_type`. This is
the one place the `us_stocks`-key / `us_equities`-type vocabulary split actually bites, it is the root the last
two rounds kept chasing, and **no test pins the invariant** that all those literals agree. Centralize it + add
one invariant test (~2-4h). Then close the single missed write surface (the seed writer, Finding 2). Do those two
and the seam is shut for good. Everything else is hygiene/polish on a shippable feature. **Do not migrate the
archive tag and do not rebuild `fetch_data`** — both were explicitly assessed as sound (Fowler: "leave the state
machine alone").

---

## P1 — Fix Now

### 1. The equities-scope policy is a scattered string literal with no drift guard

| | |
|---|---|
| **File** | `services/archive_queries.py:26,117,161`, `routers/archive_browse.py:30`, `routers/archive_calibration.py:88`, `services/engine_edge.py`, `tools/backtest_engine.py:458`, `core/backtest/loader.py`, `core/archive/episodes.py:43`; backfill at `services/startup.py:290` |
| **Council** | Fowler (LEAD) × Ramírez × Beck × Hunt — Inconsistent Vocabulary / Shotgun Surgery + "test what might break" |
| **Ref** | `references/refactoring.md` → P4/P5 · `references/quality-testing.md` → P4/P8 |

**Finding:** The "default population is equities" policy is expressed as the bare string `"us_equities"` typed
independently at ~9 read sites (and the migration backfill), none deriving from `default_universe().universe_type`
the way `engine_edge` correctly does — and `test_universe_descriptor` never even asserts that the default
universe's `universe_type` *is* `"us_equities"`. There is no single test that says "the value the migration
writes is the value the read side filters on."

**Consequence:** A renamed tag, an added 4th equities-class universe, or a single missed site silently
mis-scopes a stats/edge surface (pooling ETF rows into the equities population, or orphaning every equities row
from a read surface) — the exact scope-mix the last two rounds chased — and **every per-site test still passes
green** because each is internally consistent. False confidence over a broken seam.

**Fix:** Introduce one named symbol (e.g. `DEFAULT_EQUITIES_UNIVERSE_TYPE = default_universe().universe_type`)
exported from the universe module; replace the literal at every read site with it. Add ONE invariant test
asserting the migration backfill value == `default_universe().universe_type` == the `_apply_setup_filters`
default == the `_latest_episode_first_seen` literal, plus pin each universe's `universe_type` in the descriptor
test. Do NOT migrate the archive tag to match the key — not worth a live-SQLite migration for cosmetics.

---

## P2 — Fix Soon

### 2. Seed writer is not universe-aware — the one missed write surface

| | |
|---|---|
| **File** | `core/archive/seed.py:296,331-490` |
| **Council** | Leach × Carmack — Constraints are assertions / upsert matches the identity key (P1/P4) |
| **Ref** | `references/quality-postgres.md` → P1/P4 |

**Finding:** The live screener writer was widened to upsert on `(ticker, scan_date, universe_type)`, but the seed
writer still does `filter_by(ticker=ticker, scan_date=eval_date_str).first()` and never stamps `universe_type`
(it falls through to the server default). **Fix:** Thread the resolved `universe_type` into the seed writer's
`values` and existence check, mirroring `core/archive/writer.py` — this completes the surgical pass the last
round started on the write side.

### 3. Split-probe ratio is poisoned by `inf` when a Close is zero — a drifted ticker escapes the probe

| | |
|---|---|
| **File** | `core/pipeline/downloads.py:404-411` |
| **Council** | McKinney × Carmack — NaN/inf propagate silently; quarantine at the boundary (P2) |
| **Ref** | `references/quality-llm.md` → P2 |

**Finding:** `ratios = (f / c).dropna()` does not drop `inf` — a zero/halt Close yields `inf`, which makes
`ratio_mean`/`ratio_std` `inf`, so `is_constant` becomes `inf < inf` = False and the ticker is silently NOT
flagged as split-drifted. **Consequence:** A genuinely split-drifted name with one bad overlap bar never gets
re-fetched, so the screener reads pre-split (mis-scaled) prices on it — a real, if narrow, correctness bug.
**Fix:** `replace([inf,-inf], nan)` before `.dropna()` on the ratio series (the pattern the metrics code already
uses).

### 4. `_weekly_refresh_due` is a true twin — two divergent implementations

| | |
|---|---|
| **File** | `core/pipeline/downloads.py:726-735` and `core/pipeline/scan_job.py:351-360` |
| **Council** | Fowler × Carmack — Shotgun Surgery / twin code paths (P5) |
| **Ref** | `references/refactoring.md` → P5 |

**Finding:** Two separately-maintained `_weekly_refresh_due(meta)` functions decide the same thing from the same
`last_full_refresh` key but differ in tz handling and interval-default sourcing — the exact eval-twins shape the
project already fought. **Fix:** Hoist one shared copy (next to the other meta predicates in `data_freshness`/`cache`)
and delete the second.

### 5. Episode cache version is whole-table — any ETF insert busts the equities grouping

| | |
|---|---|
| **File** | `webapp/backend/services/archive_queries.py:59-64,99-123` |
| **Council** | Performance × Carmack — Cache-key granularity / cross-universe invalidation |
| **Ref** | general pandas/SQL caching practice |

**Finding:** `_archive_version` is `(max(id), count(id))` over the **whole** `setup_archive` table, but groupings
are cached per-`universe_type`; a commodities/sector insert moves the signature and busts the cached `us_equities`
grouping. **Consequence:** After the daily multi-universe scan, the first equities `/episodes` + `/missed-winners`
request re-runs `build_episodes` over the full equities archive despite nothing equities-relevant changing —
defeating the cache exactly when wanted. **Fix:** Scope the version aggregate by the same `universe_type` as the
cache key.

### 6. `close_coverage_on` does a per-symbol scalar `.loc` loop over the ~5.5k panel, several times per fetch

| | |
|---|---|
| **File** | `core/pipeline/data_freshness.py:40-63` (callers in `downloads.py:676,750,953,1101,1153`) |
| **Council** | Performance × Carmack — Vectorization over per-row loops |
| **Ref** | `references/quality-backend.md` → perf |

**Finding:** Coverage is `sum(1 for symbol in symbols if data.loc[row_label, (symbol,'Close')] …)` — ~5.5k
individual MultiIndex scalar lookups (the slowest pandas access) per call, and `fetch_data` calls it on the
fast path AND after repair/cold/incremental. **Fix:** Slice the row once via `xs('Close',level=1).reindex(columns=
symbols).loc[row_label].notna().sum()`, the shape `deep_history_ratio` already uses.

### 7. `useDrilldown` unmount guard is inert

| | |
|---|---|
| **File** | `webapp/frontend/src/hooks/useDrilldown.js:16,24,29,41` |
| **Council** | Dodds × Carmack — Effects clean up what they create (P8) |
| **Ref** | `references/quality-frontend.md` → P8 |

**Finding:** `mountedRef.current = true` runs in the render body every render with no cleanup, so the
`!mountedRef.current` checks can never short-circuit on a real unmount — a drill-down fetch resolving after the
grid unmounts still calls `setDrilldown` on a dead component. **Fix:** Move to `useEffect(() => { mountedRef.current
= true; return () => { mountedRef.current = false; }; }, [])`, as `useScreenerData` already does.

### 8. Universe switch still leaks `tierFilter` and `searchTerm` — prior filter-persistence fix only half-applied

| | |
|---|---|
| **File** | `webapp/frontend/src/components/ScreenerGrid.jsx:35-41` + `hooks/useScreenerFilters.js:51-56` |
| **Council** | Dodds × Carmack — Make misleading states unrepresentable (P3) |
| **Ref** | `references/quality-frontend.md` → P3 |

**Finding:** `handleUniverseChange` calls `resetFilters()`, but that clears only setup/tag/sort/page — NOT
`tierFilter`/`searchTerm`, the exact two the prior review (#8) named. A stale `WATCHLIST`/`S` tier or typed
search carries into a universe where it matches nothing → a populated universe renders "No setups match" and
reads as broken. **Fix:** Clear tier + search on universe switch too.

### 9. Toolbar matched-count line contradicts the grid's screen states

| | |
|---|---|
| **File** | `webapp/frontend/src/components/ScreenerGrid.jsx:101-113` + `ScreenerToolbar.jsx:35-37` |
| **Council** | Friedman × Carmack — Design all five screen states; inconsistent messaging destroys trust (P2/P9) |
| **Ref** | `references/quality-ux.md` → P2/P9 |

**Finding:** The toolbar always prints "{N} setups matched your constraints"; on a `never_scanned`/`loading`/
`error`/`empty` universe that becomes "0 setups matched your constraints" sitting directly above the grid's
"No scan yet" / "Couldn't load" — two contradictory explanations. Most acute on freshly-switched ETF universes
(scheduled-only, often no artifact yet). **Fix:** Suppress/rephrase the count line unless `status === 'ready'`.

### 10. No data-freshness stamp on the grid — acute now that ETF universes are scheduled-scan-only

| | |
|---|---|
| **File** | `webapp/frontend/src/components/ScreenerGrid.jsx:89-204` |
| **Council** | Friedman × Carmack — Missing data-freshness indicators (P6) |
| **Ref** | `references/quality-ux.md` → P6 |

**Finding:** Nothing shows when the displayed scan was produced. The two ETF universes refresh only on the
scheduled daily scan (the trader never triggers them), and the `MarketDataStatus` strip reports cache health,
not scan recency — so the trader can bridge a 3-day-old ETF rank to TWS with no cue. **Fix:** Surface a "scanned
at HH:MM · DD MMM" stamp from the screener payload, primary for the ETF universes.

### 11. The per-universe `persist_scan_metrics` routing (this round's fix) is never exercised

| | |
|---|---|
| **File** | `tests/test_scan_metrics.py:14-27` |
| **Council** | Beck × Carmack — Test what might break; mocks that hide the seam (P3/P4) |
| **Ref** | `references/quality-testing.md` → P3/P4 |

**Finding:** The only test calls `persist_scan_metrics(metrics)` with no universe and monkeypatches `_cache_paths`
to a fixed path that ignores its argument — so the universe→path routing and the per-universe lock target are
untested; the test passes identically if `universe` were dropped. **Fix:** Add an ETF-universe case asserting the
metrics land in *that* universe's `cache_meta` (and not the default's), letting `_cache_paths` actually branch.

---

## P3 — Consider (grouped)

### 12. Data-status surface under-signals action — `shallow_history`, switcher rank, repair hue (Saarinen)
`ScreenerToolbar.jsx` / `UniverseSwitcher.jsx`. The new `shallow_history`/"Rebuild data" state matches no color
branch → renders as the *quietest* (muted grey) treatment despite demanding action; the universe switcher (changes
the whole dataset) shares the exact visual rank as the second-order tier chips; `needs_repair` borrows Categorical
Rose with a Tier-A-violet literal fallback. Map the data-statuses onto the green/amber/red ramp and lift the
switcher one tier in the hierarchy (no new hue).

### 13. Structural duplications worth one helper each (Fowler)
The `~columns.duplicated(keep='last')` torn-merge dedupe is repeated 8× across `downloads.py`+`data_freshness.py`
→ extract one named `_dedupe_columns`. The `SetupRow`→episode projection is written 3× (`archive_queries` ×2,
`loader`) and only the loader copy NaN-cleans → lift one `setup_row_from(obj)` adapter that NaN-cleans inside.

### 14. Migration branch coverage + the over-broad swallow (Beck × Leach)
The migration rebuild test exercises only the clean legacy path; the `COALESCE(universe_type,'us_equities')`
preserve-vs-overwrite branch (must not clobber already-tagged rows on re-run) and the row-count-drift rollback are
untested. Separately, `startup.py:215` swallows ANY `"no such column"` as "already applied" for the
`score_oscillation` DROP — scope it to the known retired statement so a genuine failure stays loud.

### 15. Backend boundary hardening (Ramírez)
`sort_by`/`sort_dir` are free strings fed to `getattr(SetupArchive, sort_by, …)` → constrain to a `Literal` of
sortable columns (422 not 500). `PATCH /setups/{id}/label` commits with no `try/except`+rollback. `_resolve_universe_type`
double-defaults the scope (Query default + helper default) — pick one home.

### 16. Numerical robustness edges (McKinney)
On a transient mixed-NULL archive, a NULL `universe_type` defaults into `us_equities` and could merge a NULL-tagged
row into the wrong universe (the inverse of the split the fix prevents) — use a `__unknown__` sentinel if a
mixed-NULL window is ever possible. `deep_history_ratio`'s `keep='last'` dedupe can keep the hollow duplicate column
(prefer the max-non-NaN-count column so the depth verdict is conservative toward refetch). The split-probe
constant-ratio `std` floor (`0.001`) has an unstated absolute basis — document or scale it to `ratio_mean`.

### 17. Frontend/UX polish (Dodds × Friedman × Saarinen)
Drill-down has no Esc exit (the modal taught Esc one level up); switching universes mid-scan strands the in-flight
job against the old universe (disable the switcher while a job runs, or cancel it); generic scan/error copy doesn't
name the dominant real failures (rate-limit/429, quarantine, partial coverage) so the trader re-clicks into the
same throttle; the branded Signal-Blue focus ring is missing on switcher/toolbar buttons; off-grid spacing (14/10/7px)
and a third button radius (16px) drift from the scale; `useScreenerData` keeps the payload in both state and a ref
mirror; the earnings cache isn't universe-scoped (document as intentional or key it).

---

## Summary

| # | Finding | Severity | Council | Fix effort |
|---|---------|----------|---------|------------|
| 1 | Equities-scope literal scattered ×9 + no invariant test | **P1** | Fowler/Ramírez/Beck/Hunt | ~2-4h (constant + 1 test, ~9 sites) |
| 2 | Seed writer not universe-aware (missed write surface) | P2 | Leach | ~10 lines |
| 3 | Split-probe ratio poisoned by inf → drifted ticker escapes | P2 | McKinney | ~1 line |
| 4 | `_weekly_refresh_due` divergent twin | P2 | Fowler | ~10 lines (hoist+delete) |
| 5 | Episode cache version is whole-table | P2 | Performance | ~3 lines (scope the aggregate) |
| 6 | `close_coverage_on` per-symbol `.loc` loop | P2 | Performance | ~5 lines (vectorize) |
| 7 | `useDrilldown` unmount guard inert | P2 | Dodds | ~3 lines |
| 8 | Universe switch leaks tier/search filters | P2 | Dodds | ~3 lines |
| 9 | Matched-count line contradicts screen states | P2 | Friedman | ~5 lines |
| 10 | No scan-freshness stamp on the grid | P2 | Friedman | ~15 lines |
| 11 | `persist_scan_metrics` per-universe routing untested | P2 | Beck | ~15 lines (1 test) |
| 12 | Data-status under-signals (shallow_history/switcher/hue) | P3 | Saarinen | ~20 lines CSS |
| 13 | Dedupe idiom ×8 + SetupRow adapter ×3 → helpers | P3 | Fowler | ~30 lines |
| 14 | Migration COALESCE/drift untested + over-broad swallow | P3 | Beck/Leach | ~20 lines |
| 15 | sort_by whitelist / label rollback / double-default | P3 | Ramírez | ~15 lines |
| 16 | NaN-sentinel / dedupe-keep / std-basis robustness | P3 | McKinney | ~10 lines |
| 17 | Drill-down Esc / mid-scan / error copy / focus / spacing | P3 | Dodds/Friedman/Saarinen | ~40 lines |

## Verdict

**Keep fixing surgically — do not rebuild.** Every seat concurred, and the data-layer seats (Leach, McKinney,
Fowler) — the ones whose "no" would have mattered most — were the most emphatic: the identity key is clean by
construction, the descriptor is the right abstraction, `fetch_data` is a well-factored state machine, and the
recurring per-round leaks are distinct edges being closed, not one design flaw resurfacing. The single thing that
genuinely *is* cross-cutting is Finding 1 — the read-side equities-scope literal with no drift guard — and it is
cheap to close for good (one constant + one invariant test). Pair it with Finding 2 (the seed writer, the last
universe-blind write surface) and the seam is shut. The most critical domain right now is **test strategy**
(Beck): the architecture is fixable surgically, but the pattern of "patch the site that broke" is what let the
NaN bug and the scope literals accumulate — one deliberate invariant-test pass over the seam is what prevents a
fourth round. After 1–2, everything is P2/P3 hardening and UI polish on a shippable, sound feature.

---

## Findings Breakdown by Expert

| Expert | P1 | P2 | P3 | Total | Key Areas |
|--------|----|----|----|----|-----------|
| Hunt (Security) | 0 | 2 | 2 | 4 | yfinance pin (verified exact), ticker charset, vocab split |
| Dodds (Frontend) | 0 | 2 | 2 | 4 | inert unmount guard, filter leak, state/ref dup |
| Ramírez (Backend) | 0 | 1 | 4 | 5 | scope literal ×5, sort_by, label rollback |
| Leach (Data Integrity) | 0 | 1 | 2 | 3 | seed writer, upsert race, migration swallow |
| Performance | 0 | 2 | 2 | 4 | cache version granularity, coverage loop, repeated depth scan |
| Saarinen (UI) | 0 | 3 | 4 | 7 | status under-signal, switcher rank, hue/ramp, spacing |
| Friedman (UX) | 0 | 3 | 2 | 5 | screen-state contradiction, freshness stamp, error copy |
| Fowler (Refactoring) | 0 | 2 | 4 | 6 | scope literal (LEAD), weekly twin, dedupe/adapter |
| McKinney (Numerical) | 0 | 1 | 4 | 5 | split-probe inf, NaN-sentinel, dedupe-keep |
| Beck (Test Quality) | 2 | 4 | 2 | 8 | unpinned invariant, migration/routing coverage |
| **TOTAL** | **2** | **21** | **28** | **51** | |
