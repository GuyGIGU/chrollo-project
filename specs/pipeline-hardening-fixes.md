# Pipeline Hardening — Critical-Bug Fix Spec

Source: adversarially-verified multi-agent bug-hunt (2026-06-30), the follow-up to the
multi-universe cache-contamination incident. Six verified landmines of the SAME class as the
fixed bug: silent data corruption, success-masking (health checks that pass on broken data),
a corrupting cross-process race, and read-side cross-universe leakage. All six confirmed by
≥1 adversarial verifier tracing the real code.

## Hard constraints (non-negotiable — this is engine periphery)
- **Byte-parity MUST hold.** After every change: `python -m tools.shadow_diff --check`
  (live engine byte-identical), `python -m core.archive.seed_recall --check` (recall 54.5%
  baseline, no new miss), `python -m pytest -q` (590 baseline). Any drift is a bug to diff,
  NOT to re-baseline.
- **Small, evidence-driven steps.** One fix at a time, gated, committed surgically. No big
  blind redesign.
- **Out of scope / do NOT touch:** the L2-staircase WIP files (`core/structure/metrics.py`,
  `tests/test_market_structure.py`, `tools/l2_staircase_audit.py`, `tools/l2_staircase_render.py`,
  `tools/fidelity/l2/`) and the parked `ActionCenter` frontend.
- The slow cold-refetch is **NOT a bug** (deliberate 20 req/sec rate-limit safety) — leave it.

---

## ① Depth-aware market-data health — HIGH (the unfixed "second half")
**Files:** `core/pipeline/market_data_health.py:309-330` (`_classify`),
`core/pipeline/data_freshness.py:40-91`, `core/pipeline/scan_job.py:215-219`
(`refresh_market_data_cache`), `core/pipeline/downloads.py:1097-1104` (incremental merge gate).

**What's wrong:** `can_archive`/`can_evaluate` are decided ENTIRELY from latest-session facts
(index closes on `expected_session` + single-row `eligible_coverage`). No term consults
per-ticker bar DEPTH. So the exact corruption we hit (recent bars survive, deep history
NaN-wiped to <100 bars) reports `status='healthy', can_archive=True`, and
`refresh_market_data_cache` reads `before_health['can_archive']` and NO-OPs the repair — the
cache blocks its own recovery (why manual cache deletion was required).

**Fix:** Add a per-symbol historical-depth term to the `can_archive`/`can_evaluate`
classification. `bar_counts` are already computed in `_latest_close_facts` (currently only
fed to the human `missing_summary`) — require eligible coverage at a sane depth (e.g.
`>= ADMISSION_MIN_HISTORY_BARS` over a recent window), not just one session. Make
`refresh_market_data_cache` treat a depth failure as a FORCED full refetch instead of a
no-op. Guard: must NOT reject a genuinely-healthy full-history cache (shadow/seed-recall green).

## ② Universe-aware market-data health — HIGH (commodities_etf is dead-on-arrival)
**Files:** `core/pipeline/market_data_health.py:44-47` (`build_symbol_scope`),
`core/pipeline/universe.py:107,119,131`, `core/pipeline/screener.py:126,166`,
`core/pipeline/scan_job.py:100-111,194-204`.

**What's wrong:** `build_symbol_scope` hardcodes `index_symbols = settings.INDEX_SYMBOLS`
(`['SPY','QQQ']`) and takes no universe arg; `compute_market_data_health` never threads a
universe. But the download path IS universe-aware — commodities_etf has `index_symbols=()`,
so its parquet never carries SPY/QQQ → `index_missing` always `['SPY','QQQ']` →
`stale_session`/`can_archive=False` on EVERY run → the universe can never archive a setup
(swallowed as a tolerated `None`, exit 0, no alert). us_sectors is spared only because its
descriptor carries `('SPY','QQQ')`.

**Fix:** Thread the universe (or its `index_symbols`) into
`compute_market_data_health`/`build_symbol_scope`; source index symbols from
`resolve_universe(universe).index_symbols`, NOT `settings.INDEX_SYMBOLS`. An empty index set
must yield `index_missing=[]` and fall back to the panel-max reference date (the
`cache_last_session` path at `health.py:117-118` already does this), so an index-less universe
is gated only on its own coverage. This also fixes ⑥ at the same call site (pass `meta_file`).

## ③ Empty-results scan must not clobber the live dashboard unguarded — HIGH
**Files:** `core/pipeline/scan_job.py:132-138`, `core/pipeline/screener.py:163-164`,
`output/dashboard.py:344-366`, `webapp/backend/services/scan_runner.py:79-96,132`.

**What's wrong:** `_assert_fresh_for_archive` runs ONLY in the non-empty branch of
`run_scan_and_export`. The empty branch (`results_df.empty`) calls `generate_dashboard` then
returns `n_setups=0` with NO health/coverage check — in download mode there's also no
pre-eval health gate. A degraded fetch → 0 results → the live `screener_data.json` is
atomically overwritten with an EMPTY payload (wiping the prior day's real setups) and the run
reports `status=ok`. `ALERT_ON_ZERO_RESULTS` is a config backstop, not an integrity gate.

**Fix:** In the empty branch, run `compute_market_data_health` (or a coverage assertion)
before treating zero results as a legitimate ok scan; do NOT overwrite the live artifact with
an empty payload when coverage is below the archive target. Mirror the non-empty branch's
`_assert_fresh_for_archive`. (A genuine zero-setup day on HEALTHY data must still write the
valid empty artifact — only degraded-data zeros are blocked.)

## ④ Cross-process lock around the cache fetch/write window — HIGH
**Files:** `webapp/backend/services/scan_runner.py:18,35-59,186,252,262`,
`core/pipeline/scan_job.py:210-286`, `core/pipeline/downloads.py:749-886`,
`core/pipeline/cache.py:39-78` (`_atomic_write_parquet`).

**What's wrong:** `SCAN_LOCK` is an in-process `threading.Lock`. The scheduler-triggered scan,
manual SSE scans, and a standalone CLI `run_screener.py` are SEPARATE processes that share no
lock, yet all read-modify-write the same `market_data_cache_5y.parquet` + `cache_meta.json`.
Parquet and meta are two independent atomic writes → an interleave produces a torn
cache/meta mismatch (which can then mislead the depth-blind health check above). No file lock
exists anywhere in the fetch path. Operationally live: the daily scheduler fires at 18:00 ET;
a long manual refetch overlapping it can re-corrupt.

**Fix:** Add a real cross-process advisory lock (e.g. `portalocker`, or OS lock via `msvcrt`
on Windows / `fcntl` elsewhere) around the whole read-fetch-write-meta sequence in
`refresh_market_data_cache`/`fetch_data`, keyed per universe-cache path. Give
`_atomic_write_parquet` a PID/random temp suffix so two writers can't share one `.tmp`.
A second holder should skip/wait, not corrupt.

## ⑤ Universe-scope the archive read surfaces — MEDIUM
**Files:** `webapp/backend/services/archive_queries.py:16-72` (`_apply_setup_filters`),
`core/archive/episodes.py:89-91` (`build_episodes`), plus `archive_browse.py`,
`archive_reviews.py`, `archive_calibration.py`.

**What's wrong:** Tasks 3/6 made us_sectors/commodities archive under `source='screener'`,
separated only by `universe_type`. `_apply_setup_filters` supports tier/setup_type/source/etc.
but NOT `universe_type`; `build_episodes` groups on `(ticker, setup_type)` with no universe
dimension. So `/setups`, `/episodes`, `/missed-winners`, and the calibration `/stats`/`/health`
aggregates pool ETF/sector rows into the equities population (inflated counts/win-rate);
a ticker in two universes on near dates merges into one episode. DB rows stay physically
separate (3-col unique key), so this is read-side only. `engine_edge` is already pinned.

**Fix:** Thread a `universe_type` filter (default `'us_equities'`) through
`_apply_setup_filters` and add `universe_type` as a grouping key in `build_episodes`, mirroring
`engine_edge`/`loader.load_episodes(universe_type=...)`.

## ⑥ Universe-aware eligibility filter — MEDIUM (low confidence; latent)
**Files:** `core/pipeline/screener.py:166`, `core/pipeline/market_data_health.py:44-46,81-82`,
`core/pipeline/ticker_admission.py:199-301`.

**What's wrong:** `eligible_tickers_for(tickers)` is called with NO `meta_file` even though
`uni` is in scope (the sibling calls at `screener.py:117,164,171` ARE universe-aware). With
`meta_file=None`, `build_symbol_scope` resolves the US-Stocks meta and partitions ETF symbols
through the shared US-Stocks admission/quarantine ledger. If a us_stocks fetch ever records an
ETF symbol as `yahoo_empty`/anomaly (transient 429), every ETF-universe scan for the cooldown
window silently drops that ETF. Latent (current ledger is clean), self-healing.

**Fix:** Pass the universe's `meta_file` into `eligible_tickers_for` at `screener.py:166`
(matching the sibling calls). Largely subsumed by ②'s `build_symbol_scope` change.

---

## Suggested sequencing
1. **④ cross-process lock** — pure safety addition, no behavior change to good paths; de-risks
   the rest (and your current operational risk). Land first.
2. **② universe-aware health** (+ ⑥ at the same call site) — contained; revives commodities_etf.
3. **① depth-aware health** — highest care (changes gating); verify it rejects ONLY hollow
   caches, never a healthy full-history one.
4. **③ empty-results gate** — depends on ① health being depth-aware.
5. **⑤ archive read filter** — independent, read-side; cheap.

Acceptance: all three gates green after each step; a new regression test per fix where it
makes sense (depth-aware health on a hollow-panel fixture; universe-aware health on an
index-less universe; empty-branch coverage gate; archive read filter excludes ETF rows).
