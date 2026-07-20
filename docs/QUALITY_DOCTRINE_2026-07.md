# Chrollo — Quality Doctrine & Audit (captured 2026-07-03)

_Source: 8-agent product-quality audit against `main` @ `23bef2c` (roadmap-delta verification +
7 subsystem deep reads over actual code). Companion to `docs/ROADMAP_2026-06.md` — that doc's
structural-debt findings are re-verified here and largely CLOSED; this doc records what the
quality frontier is now and how to work it. Operator question that produced it: "how do we turn
this into the highest quality product possible?" (reference bar: TradingView / Finviz / IBKR /
TraderSync, scoped to a single-operator local instrument)._

---

## 1. Verdict

The June "brilliant engine, fragile periphery" diagnosis is outdated — the periphery got fixed.
Verified in current code: live/seed evaluation runs through one shared chain (`_run_eval_chain`,
AST-enforced by test); the archive schema is single-sourced (`archive_row_from_result` +
model-derived migrations at every entry point); the frontend has exactly ONE `createChart` site
(`useLightweightChart` / `CandleChart`), a real router + AppShell; the test god-file is split
(51 files, pytest.ini, committed guard fixtures); the freeze manifest exists and stamps
`engine_config_version` on every archived row.

**What remains is not an architecture problem — it is a trust problem**, concentrated in the
sensitive seams: data ingest, engine precision, IBKR runtime, journal math, backup, and the
ops last mile. Several findings were failing silently at audit time (see §4: broken backup,
unwired alerts, IBKR heartbeat churn).

### Roadmap-delta summary (June items → status today)

| June item | Status | Evidence |
|---|---|---|
| Unify live/seed eval twins | **DONE** | `_run_eval_chain` + `test_eval_twins_share_the_folded_core` |
| Provider seam (non-price data) | partial | Protocol is multi-capability + timeout-bounded; `archive_models.py` sector/market/sector_trend scrapes still raw yfinance; durable reference store deferred |
| Single-source setup schema | **DONE** | `archive_row_from_result`; migrations = model-derived diffs; SetupOut drift-guarded by tests |
| `<CandleChart>` fold | **DONE** | one `createChart` site, 6 consumers |
| react-router + AppShell | **DONE** | `App.jsx` = 31-line Routes tree |
| Scorer → 3 normalized axes | open | superseded by the TA_SCORE_V2 track (`specs/ta-score-rework*.md`); Phase 0 flag+tripwire shipped |
| Centralize ATR eval bar | partial | engine path uses `STRUCTURE_ATR_SAMPLE_OFFSET`; still hardcoded `-6` in 4 tools (backtest_watchlist, htf_audit, structure_case_audit, phase_a_pip_diff) |
| Hidden weights + manifest | partial | manifest = ~180-key allow-list, stamped on rows, IS/OOS keyed on it; hidden weights remain in `core/structure/metrics.py:206` (0.40/0.35/0.25) and `core/structure/scope.py:290`; TA_SCORE_V2 not yet in allow-list |
| Test god-file split etc. | **DONE** | 228-line residue, fixtures committed, dead tools pruned, `tools/_bootstrap.py` |
| Four swing skeletons | partial | scipy family consolidated into `core/structure/pivots.py`; `pip.py` deliberately dark; `classify_window_descent` still inline |

---

## 2. The doctrine

TradingView/IBKR earn trust **at scale**; Chrollo must earn trust **unattended**. For a
one-operator instrument, "highest quality possible" means exactly three promises:

1. **It never shows a wrong number.** Data integrity at ingest, engine precision, and ONE
   rendering of every structural read (card and modal must be incapable of disagreeing).
2. **It never loses a byte of history.** The archive + journal are the moat — the only data
   that cannot be regenerated. Backups must be provably restorable and off-disk.
3. **It never fails silently.** Every detected failure reaches the operator (push), not a log.

**The central principle: Chrollo's real architecture is its verification system** — the
measure-first flag lifecycle, byte-parity shadow gate, seed-recall, frozen-config manifest,
and the single-source folds. That system is worth more than any folder layout. The doctrine is
to EXTEND it to the four places it doesn't reach yet, not to invent new structure:

- the **precision direction** (guards currently only catch lost winners, never junk fires),
- the **data layer** (both hard CI gates bypass `core/pipeline/` entirely),
- the **frontend** (34 tests exist but don't gate; structural drawing duplicated),
- the **ops last mile** (detection without delivery is silence).

**Scope discipline (what we keep saying no to):** no microservices/Postgres/TypeScript
rewrites, no Finviz 67-filter forest, no framework adoption for the backtester, no provider
migration without a concrete adjusted-OHLC + cost answer, no engine loosening without a
cluster + census. Geometry stays the only veto; new signals stay measure-first.

---

## 3. Report card (2026-07-03)

| Subsystem | Grade | Headline |
|---|---|---|
| Engine change-safety | A- | Guard net is one-directional: no precision gate |
| Backend service | A- | SSE-disconnect scan orphan; 1s misfire grace loses nights |
| Data pipeline | B+ | Forming-bar persistence; 30-sample split probe |
| Frontend | B+ | Live-money confirm duplicated+drifted; 13MB payload per surface |
| Testing / CI / ops | B+ | Alerts unwired; FE tests not in CI; no boot smoke test |
| Archive + journal | B | Backup broken/same-disk/never restored; 3 ledger implementations |
| IBKR | C+ | Safety structural = A; runtime: heartbeat churn, unprimed orders, CSV double-count P0 |

---

## 4. Findings by subsystem

Severity: **P0** = can corrupt data / wrong reads today · **P1** = bites within months ·
P2 = friction/debt · P3 = polish. File refs are as of `23bef2c`.

### 4.1 Data download pipeline — B+

Strengths worth protecting: regime tag + mismatch→cold guard at every downloader consumer
(`price_auto_adjust` single source, locked by `tests/test_price_regime.py`); atomic PID-temp +
`os.replace` writes with conservative failure directions; depth-corruption self-repair without
ping-pong; cross-process file lock; throttling as a system (token bucket, shared 429 cooldown,
healthy-gated quarantine); loud decision-seam failures (`StaleMarketDataError`, watchdog).

- **P1 — Intraday cold refetch persists forming bars; the evening scan archives them.**
  `_full_refetch` (core/pipeline/downloads.py:474) includes the current partial session when
  run during market hours and never drops rows `> expected_session`. An afternoon "Refresh
  Data" click → evening scan evaluates AND permanently archives partial H/L/C/V on the decision
  bar. The incremental + repair paths cap their windows; the cold path is the one hole.
  **Fix: cap every persisted panel at `expected_session` in `_cold_fetch`.**
- **P1 — Split probe samples 30 of ~5.5k tickers** (`_detect_splits`, downloads.py:402): an
  unsampled split ticker carries a fake price gap for up to 7 days (weekly cold refresh). Both
  panels are already in memory during incremental fetch — make the overlap-ratio check
  exhaustive and vectorized. In the as-traded regime splits are the ONLY series-shifting
  corporate action, so this probe is the entire defense.
- P2 — Health surface is regime-blind: `compute_market_data_health` never reads
  `meta['price_series']`; after a regime flip the UI says "healthy" while eval refuses, and the
  download-only repair path early-returns without rebuilding. Add a `regime_mismatch` state.
- P2 — `os.replace` vs unlocked readers on Windows can kill a multi-minute download at its final
  step (status endpoint reads parquet without the lock). Bounded retry (5×200ms); also replace
  the `_try_current_cache` full-parquet rewrite (downloads.py:833) with `os.utime`.
- P2 — Quarantine/admission ledgers shared by all three universes with non-PID temp writes →
  torn-JSON resets state silently. PID-suffix + lock.
- P3 — `_recover_missing_data` can swap deeper history for a shallower fallback; `_try_fresh_cache`
  reads parquet unguarded at line 724; twin retry helpers drifting; provider UI calls bypass the
  throttle; hand-rolled NYSE calendar can't represent one-off closures (add an operator
  `extra_closures` override).

### 4.2 Engine change-safety — A-

Strengths: manifest with completeness meta-tests + row stamping + IS/OOS keying; two independent
offline HARD CI gates (shadow byte-parity on 37 frozen tickers via `_evaluate_ticker`; hermetic
seed-recall via the *other* twin) with bite-proof meta-tests; flag-off byte-identity as a tested
convention; geometry invariants; calibration evidence written into settings comments.

- **P1 — The net is one-directional.** Shadow fixture holds only past-firing tickers; seed-recall
  never fails on MORE fires; invariants don't judge quality. Every gate permits loosening drift.
  The prime directive (tight-structure precision) is the least-guarded direction — currently
  protected by operator eyeballs only. **Fix: freeze a negative corpus (~20 dissected
  must-NOT-fire cases — CHCT, DGII, BMRN, FRPH, OHI, other dead-space rejects) as a third hard
  gate that fails when any starts firing.** Single biggest guard-net upgrade available.
- **P1 — Manifest completeness scan covers 4 modules, not `core/structure/`** (168 settings reads
  across 12 detector files). A future knob read only inside e.g. `lps.py` changes fires without
  bumping `engine_config_version` — silent provenance corruption. Fix: glob the package in
  `_ENGINE_EVAL_PATH_MODULES` (tests/test_invariants.py); verified zero current fallout.
- **P1 — Flag-lifecycle debt: 9 dark flags, evidence decaying.** PIP_PIVOTS_ENABLED (already
  eyeball-REJECTED — delete it), PIP_MACRO_PHASE_A, LPS_REQUIRE_PEAK_DOWN, CANDLE_SPREAD_AWARE,
  PUZZLE_SCORE_ENABLED, TA_SCORE_V2 + 3 Lane-C flags. All baselines are captured flags-at-default;
  the live engine moved under them (backext re-measures every base window), so pre-backext A/B
  evidence no longer describes what a flip does. Fix: a committed flag ledger (flag, built date,
  blocking decision, evidence path, kill-by date) + re-run A/Bs before any flip.
  - > **Resolved by engine-α (2026-07-06).** The committed flag ledger ([flag_ledger.md](flag_ledger.md))
    > now tracks every dark flag with a dated kill-by; `LPS_REQUIRE_PEAK_DOWN` and `PIP_PIVOTS_ENABLED`
    > were deleted, `PIP_MACRO_PHASE_A` / `CANDLE_SPREAD_AWARE` / `PUZZLE_SCORE_ENABLED` flipped live, and
    > the manifest-completeness scan (the P1 above) now globs `core/structure/` plus the regime /
    > fundamentals eval modules. The inventory in these two bullets is the 2026-07-03 snapshot.
- P2 — strategy_alpha.md drift is discipline-only; its hand-maintained Settings Quick-Reference
  (~130 lines) is guaranteed rot. Generate that block from `config/settings.py` (or assert
  values match by test) + grep-test that every manifest key appears in the doc.
- P2 — Both hard gates bypass the data layer (frozen frames straight into the twins) — the
  as-traded-cutover bug class would sail through CI again. Golden fetch→cache→load fixtures.
- P2 — Baseline recapture at flip-time is an atomic overwrite; concurrent regressions can be
  laundered in. Recaptures should emit a committed expected-delta report.
- P3 — TA_SCORE_V2 not in the manifest allow-list (self-corrects when scoring.py reads it; cheap
  to add now). Dev(Win/3.14) vs CI(Linux/3.12) float-parity skew.

### 4.3 IBKR integration — C+ (safety A, runtime broken)

Strengths: the live gate is STRUCTURAL (confirmation is a transient call parameter, never
persisted; `IBKR_LIVE_CONFIRMED` read nowhere in code); boot broker-free by double guard; ZERO
order-API call sites repo-wide (grep-verified), raw `_ib` never exposed; sound threading (IB
loop thread, snapshot lock, single DB-writer thread); session-competition detection for the
TradingView conflict; exec_id-deduped ingestion with journal-owned fields preserved.

- **P0 — CSV import double-counts fills already captured live.** Live fills key on real execIds;
  `csv_import.py` synthesizes `csv:<sha1>` ids — the keyspaces can never collide, so importing
  an Activity Statement covering live-connected days inserts every overlapping fill TWICE →
  wrong VWAPs/quantities/phantom round-trips. This is the natural workflow given the same-day
  `reqExecutions` window. **Fix: match candidates on (account, symbol, side, qty, price,
  tz-normalized time window) against non-csv rows and skip, with an import-summary count;
  normalize both sources to UTC at ingest** (fixes the P2 mixed-timezone FIFO mis-ordering too).
- **P1 — Heartbeat is structurally broken:** `service.py:374` calls blocking `reqCurrentTime()`
  inside the running loop → `RuntimeError` every ~30s → logged as "connection likely dead" →
  full teardown/reconnect churn all session (masked by re-priming). **Fix: one line —
  `await self._ib.reqCurrentTimeAsync()`** (+ `asyncio.wait_for` for a real timeout).
- **P1 — Open orders never primed:** `readonly=True` skips the startup order fetch AND the
  compensating `reqAllOpenOrders()` (service.py:451) is the blocking variant → RuntimeError
  swallowed by `except: pass`. Also `reqAccountUpdates(True,'')` is a TypeError and
  `reqPositions()` fails the same way — dead theater masked by connectAsync's own priming.
  The Open Orders pane silently shows nothing while stops ARE working in TWS.
- P2 — Rebuild leaves ghost TradeLogs when round-trip boundaries shift (keys on opener exec_id,
  no reaper). P2 — snapshot shares `account_summary` dicts across threads (rare iteration 500s;
  deep-copy). P2 — broadcaster wakes uvicorn-loop queues from the IB thread + `bind_loop` drops
  all subscribers (degrades to 15s poll). P2 — the per-click human gate is browser-side only;
  any localhost process can POST `/ibkr/reconnect` — matters the moment a local agent exists.
- P3 — `readonly=True` is advisory in ib_async 2.1.0; **recommendation: neuter
  placeOrder/cancelOrder/reqGlobalCancel on the IB instance after connect (raise
  ReadOnlyViolation) + a test asserting zero order-API call sites** — makes read-only survive
  any future feature reaching the service. Add reconnect/heartbeat telemetry to `/ibkr/status`
  (the churn ran invisibly because nothing counts reconnects).

### 4.4 Archive + journal — B

Strengths: single-commit atomic writes on all three archive paths; self-healing model-derived
migrations at every entry point (backend boot, writer, forward_returns, seed) with test guards;
provenance stamping + the cross-regime rescale seam; orphaned-'running' reconcile; graduated
freshness gating; bias-disciplined reads (protected purge, screener-basis edge, episode dedup);
pure single-home outcome math; a nightly backup task that exists and runs.

- **P1 — Backup snapshots are hot file-copies of a live WAL DB** (`C:\Users\User\ChrolloBackup.ps1`):
  db/-wal/-shm copied sequentially (observed mtimes 15 min apart), restorability not guaranteed
  by SQLite, never test-restored, failures silenced (`-ErrorAction SilentlyContinue`).
- **P1 — Same-disk + attachments not covered.** Backups live on the same C: drive as the
  originals; `webapp/backend/uploads/` (journal chart attachments) absent entirely. Disk death
  today = journal + matured archive + all 14 snapshots + attachments gone. Only code (pushed)
  and re-downloadable market data survive.
- **P2 — The deployed script has drifted from the doc:** it copies `market_data_cache_2y.parquet`
  — a file that no longer exists — i.e. the parquet leg has failed silently every night; the
  multi-universe metas and `sector_etf_cache.json` are absent; stray `.bak` clutter is swept in.
- P2 — Journal derived columns (pnl/entry/exit/commissions) are computed in browser JS
  (`useTradeFills` → `summarizeFillLedger`) and persisted through a zero-validation PUT
  (`routers/trades.py` setattr's whatever arrives), while `auto_import.py` and `trade_risk.py`
  re-derive the same math in Python — three ledger implementations, no parity test. Stored pnl
  can disagree with actions_json depending on last writer.
- P2 — Price regime on archive rows is inference, not a stamp; the `_price_scale_factor` clamp
  ([0.2, 5.0] → snap 1.0) mislabels >5:1 post-scan splits with no flag. Add a `price_regime`
  column + persist the manifest JSON to a `manifests(hash, json, first_seen)` table + stamp git
  SHA (today: hash-only, content unrecorded, code version unrecorded).
- P3 — boot reconcile can mislabel an in-flight OS-task maturation run; manual-add existence
  check ignores universe_type; execution ingest warn-and-drops on a full writer queue inside a
  same-day-only recovery window; legacy migration runner string-sniffs exceptions.

**Fix package (the highest-trust upgrade in the whole audit):** snapshot via
`sqlite3 ... "VACUUM INTO"` (or `.backup`) → `PRAGMA integrity_check` on the copy → one off-disk
leg (cloud-synced folder / second drive) → correct the file list (5y parquet or drop it, metas,
uploads/) → restore-drill script (restore to temp, open read-only, compare row counts, pass/fail
line) → re-sync `docs/deploy.md` §4 + write a restore section.

### 4.5 Backend service — A-

Strengths: 129-line composition root, real layering in the scan/status/health stack;
crash-restart hygiene (boot reconcile, atomic artifact writes, WAL+busy_timeout via one shared
factory); layered failed-scan visibility (per-run rows, watchdog both kinds, pure alert-decision
function); config-shadow structurally addressed (broker_config rename + lazy `load_core_settings`);
careful subprocess handling (UTF-8 forced, structured result payload); API hygiene (path-traversal
defense, upload containment, NaN scrubbing, request-ID middleware).

- **P1 — SSE client disconnect mid-scan orphans the subprocess:** GeneratorExit at a yield in
  `_stream_process` skips `finish_run` (row stuck 'running'), never terminates the
  `run_screener.py` child, and `finally` releases SCAN_LOCK while the child still evaluates and
  writes the archive → a second scan can interleave. **Fix: catch GeneratorExit in try/finally,
  terminate/kill the child, `finish_run(status='aborted')`.**
- **P1 — Scheduled scan silently skipped on any misfire >1s** (APScheduler default grace): a
  sleeping machine or mid-restart service at 18:00 ET discards the night's scan; no catch-up.
  **Fix: `misfire_grace_time` in hours + a boot-time catch-up check.**
- P2 — No log rotation anywhere (NSSM AppRotate unset; every request logged at INFO incl.
  polling; scan stdout re-logged line-by-line; maturation.log append-forever) — multi-GB over a
  year. P2 — config-shadow fixed by convention but unguarded: no test asserts
  `webapp/backend/config.py` stays absent / that `import main` with backend cwd resolves root
  config. P2 — broadcaster loop-affinity (see 4.3). P2 — `archive_calibration.py` (488 lines of
  numpy in a router) et al. violate routers-thin where the app grows fastest.
- P3 — dead PRAGMA per status call; unbounded skip/limit; download jobs don't gate the live-price
  fallback; SPA catch-all masks API 404s.

### 4.6 Frontend — B+

Strengths: router migration landed; chart layer exemplary (one createChart, tested pure
geometry); house rules actually followed (44 guarded toFixed sites, 55 fetches with catch,
best-in-class useSSE); sophisticated hook hygiene (stale-response tokens, per-universe cache,
ErrorBoundary per Home zone); real token source of truth; deliberate UX craft (keyboard nav,
honest empty states).

- **P1 — The live-money IBKR confirm/reconnect flow is implemented twice and has drifted:**
  `PortfolioTab.jsx:22-48` hand-rolls what `hooks/useIbkrActions.js` owns; wording already
  diverged and the copy lacks the in-flight guard (double-click → two reconnect POSTs). One
  path for the single most safety-critical FE flow.
- P2 — Three independent `/ibkr/status` pollers (AppShell, useLiveRisk, PortfolioTab) at ~1
  req/s in the NORMAL (disconnected) state — make it single-owner via outlet context.
- P2 — 13MB `screener_data.json` fetched per surface instance, re-downloaded on every
  Home↔Screener navigation, re-parsed on the main thread; Home re-pulls it every 5 min for a
  handful of tiles. **Fix: one shared store + a slim `/screener-summary` endpoint — this is a
  direct dependency of the sector health board.**
- P2 — Two color vocabularies (GitHub palette in JS/chart-land vs DESIGN.md tokens in CSS —
  two different "success" greens); 6 hand-copied chartOptions blocks; **R/S/mid + inner-box rail
  drawing duplicated between mini and modal charts** — the display of the engine's read must be
  drawn by ONE function (`chartTheme.js` + `addBoxRails()`), or card and modal can show
  different structure for the same setup (= a wrong read, by this product's standards).
- P2 — 8 formatter dialects (null glyph already diverges). P3 — 17 `alert()`/`confirm()` sites
  (build toast/confirm on ui/Modal.jsx); modal ticker + drilldown not URL-addressable; index.css
  2,025-line monolith + 427 inline style objects.

### 4.7 Testing / CI / ops — B+

Strengths: CI is a real gate (compileall + 737 tests + shadow --check + hermetic seed-recall as
HARD fails; advisory fresh-recall honestly documented); bite-proof guard meta-tests; ~114s suite;
deploy safety net (build-gated restart + /health poll); the maturation tick and nightly backup
tasks registered and running; thoughtful fixture gitignore discipline.

- **P1 — The entire alerting net terminates in a log file:** `ALERT_WEBHOOK_URL` is not set on
  the NSSM service (verified: service env has only IBKR_AUTO_CONNECT=false). Every watchdog
  finding is a log.warning. **Fix: set the env (ntfy/Discord/Telegram), test-fire one alert
  end-to-end. Without this, every other reliability investment is silent.**
- **P1 — Frontend regressions ship undetected:** 34 existing node:test tests never run in CI
  (one-line addition); zero component tests beyond the three util files.
- **P1 — No service-boot smoke test** despite the config-shadow class having bitten before:
  no test imports `main` with cwd=webapp/backend. Automate the check AGENTS.md prescribes:
  subprocess `python -c "import main; assert len(main.app.routes) > 70"` with backend cwd.
- **P1 — Backup drift/restore** (see 4.4 — counted once).
- P2 — CI is ubuntu/3.12 vs prod Windows/3.14 (the encoding class is proven real); add a
  windows-latest pytest job. P2 — only yfinance pinned; commit a `constraints.txt` freeze of the
  working env so a bare-clone rebuild reproduces the parity environment. P2 — both scheduled
  tasks are "Interactive only" (skip when parked at the login screen) — re-register
  run-whether-logged-on. P2 — `update_dashboard.ps1` has no backend preflight and no rollback
  dist. P3 — baselines lack captured_at/refresh policy; vestigial markers; `.bak` clutter.

---

## 5. The plan — work packages for parallel sessions

**Parallelize by CONFLICT DOMAIN (files), not by tier.** Tiers share files; the packages below
don't. Rules of engagement for every working session:

1. Read this doc §for-your-package + `AGENTS.md` first. Engine-touching work additionally reads
   `docs/strategy_alpha.md` (house law).
2. One branch per package off `main`; small PRs; run the gates before handoff
   (`pytest`, `tools/shadow_diff --check`, seed-recall hermetic, FE build).
3. **Only ONE session at a time may touch `core/structure/`, `core/scoring/`,
   `config/settings.py`'s engine regions, or the shadow/seed baselines** — the byte-parity
   gates make concurrent engine edits un-mergeable. WP-E below is that lane.
4. Merge serially, gates green each time. Don't let two packages edit
   `.github/workflows/quality.yml` in the same window (WP-D owns it).
5. Do not restart the service / register tasks / set service env — hand the operator the exact
   commands (house law). Loading changes = operator runs `update_dashboard.bat`.

### WP-A — Backup & disaster recovery (T0) — S/M
`C:\Users\User\ChrolloBackup.ps1` (deployed, outside repo) + `docs/deploy.md`.
VACUUM INTO snapshot + integrity_check + off-disk leg + correct file list (drop the dead 2y
parquet line; add uploads/, multi-universe metas) + stop sweeping .bak clutter + restore-drill
script + restore section in deploy.md. Hand operator: re-register both tasks
run-whether-logged-on (elevation).

### WP-B — IBKR runtime (T0) — M
`webapp/backend/ibkr/service.py`, `services/csv_import.py`, `services/auto_import.py`,
`webapp/frontend/src/components/PortfolioTab.jsx` (+`hooks/useIbkrActions.js`).
Heartbeat async fix; fix/delete the dead prime calls + `await reqAllOpenOrdersAsync()`;
CSV-overlap guard + UTC normalization; deep-copy snapshot dicts; neuter order methods
post-connect + zero-order-API test; reconnect telemetry in `/ibkr/status`; dedupe the FE
confirm flow onto useIbkrActions.

### WP-C — Data-pipeline integrity (T0) — M
`core/pipeline/downloads.py`, `market_data_health.py`, `cache.py`, `fetch_health.py`.
Forming-bar cap at expected_session; exhaustive vectorized split probe; regime-aware health
state; os.replace retry + os.utime touch; PID-suffix + lock the shared ledgers; guard the
line-724 read; fold the twin retry helpers. Engine-neutral but data-adjacent: run the full gate
set; a shadow/recall diff here means a bug, not a flip.

### WP-D — Backend ops + CI (T0) — M
`webapp/backend/services/scan_runner.py`, `scheduler.py`, tests/, `.github/workflows/quality.yml`,
`requirements.txt`/`constraints.txt`, `update_dashboard.ps1`, `docs/deploy.md` (NSSM rotation).
SSE-orphan fix (terminate child + finish_run aborted); misfire_grace_time + boot catch-up;
FE tests in CI; boot smoke test; config-shadow tripwire test; windows-latest pytest job;
constraints.txt; deploy preflight + kept previous dist; log-rotation commands for the operator;
demote per-poll request logs to DEBUG. Hand operator: `nssm set ... ALERT_WEBHOOK_URL` +
AppRotate commands (elevation) + one end-to-end alert test-fire.

### WP-E — Engine guard net (T1) — M — **solo lane, engine-adjacent**
`tests/` fixtures + `tools/shadow_diff.py`-style third gate, `tests/test_invariants.py`,
`config/settings.py`, `core/freeze/manifest.py`, `core/structure/pip.py`+`segmentation.py`
(flag deletion), `docs/strategy_alpha.md`.
Negative-corpus precision gate (~20 frozen must-NOT-fire cases as a hard gate); glob the
manifest-completeness scan over all of core/structure/; add TA_SCORE_V2 to the allow-list;
committed flag ledger with kill-by dates; DELETE PIP_PIVOTS_ENABLED (eyeball-rejected);
generate/assert strategy_alpha's settings quick-reference; captured_at on baselines. Read
strategy_alpha.md first; update it in the same change; all gates must stay green (these changes
are behavior-neutral — any shadow/recall diff is a bug).

### WP-F — Frontend folds (T2) — M/L — after or alongside, low conflict
`webapp/frontend/src` only. Shared screener-data store + slim `/screener-summary` endpoint
(coordinate the one new backend route with WP-D timing); `chartTheme.js` + shared
`addBoxRails()`; formatter fold into `utils/format.js`; toast/confirm primitive replacing the
17 alert() sites; single-owner IBKR status via outlet context; modal ticker + drilldown into
searchParams. This package unblocks the sector health board.

### Deferred (tracked elsewhere, not this doc's scope)
TA-score rework (`specs/ta-score-rework*.md`), sector health board
(`specs/market-sector-health-board.md`), provider-seam phase 2 (archive_models reroute +
durable reference store), seeded backtests on cherry-picked setups, dark-flag flips
(operator-gated), EODHD/Polygon migration, alerts-engine / portfolio-manager / local-agent
(ROADMAP_2026-06 Phase 5 — the no-auto-trade guardrail section there stays binding).

---

## 6. Operator-action checklist (things only you can do)

- [ ] Set `ALERT_WEBHOOK_URL` on the service (WP-D hands you the command) and confirm one test alert arrives.
- [ ] Re-register "Chrollo Forward Returns" + "Chrollo Daily Backup" run-whether-logged-on (WP-A hands you the command).
- [ ] Pick the off-disk backup destination (cloud-synced folder / second drive / NAS).
- [ ] Run `update_dashboard.bat` after each merged package that touches backend/frontend.
- [ ] Run the first restore drill once WP-A lands (script provided; ~2 minutes).
