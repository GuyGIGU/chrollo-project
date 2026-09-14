# Engine Reference — how Chrollo is built, and why

*(Split out of `strategy_alpha.md` on 2026-07-27. That document is now the **theory**:
the operator's chart language and what a good setup IS. This one is the **implementation**:
which function does it, in which file, with which constant — plus the reasoning behind the
shape we chose, so a future change can tell a deliberate design from an accident.)*

> **RULE — read this before touching the reading engine, together with
> [`strategy_alpha.md`](strategy_alpha.md).** Theory answers *what we are trying to see*;
> this file answers *how it is currently seen*. A behaviour change lands with BOTH updated
> in the same change when it moves either. Drift is a defect, not a chore to defer.

> **Falsified levers live in [`decisions.md`](decisions.md).** Before proposing a knob,
> threshold, or heuristic, check it there — several plausible ideas in this engine have
> been built, measured, and removed, and re-proposing one costs a full A/B cycle.

Companions: [`strategy_alpha.md`](strategy_alpha.md) (theory) ·
[`decisions.md`](decisions.md) (rulings + tested-DEAD) ·
[`wyckoff_canon.md`](wyckoff_canon.md) (what Wyckoff we took / left) ·
[`structure_legend.md`](structure_legend.md) (wire vocabulary) ·
[`core/MAP.md`](../core/MAP.md) (module map).

---

## Where each step lives

| Reading step | Implementation |
|---|---|
| Trend / trend end (Phase A) | `label_market_structure()` + `segment_trends()` read the HH/HL trend model (start / climax / CHoCH — see "Trend & Change of Character"), consumed live by `bricks._cause_is_up` via `trend_terminal_floor` (its `first_reaction_after()` consumer retired 2026-09-08 with `AR_FIRST_REACTION_ENABLED`); `collect_root_anchors()` (the calibrated climax→AR anchor scan) for the root walk; `segment_swings()` (order-N pivot zigzag) for the drawn Phase-A bridge, upgraded first by the always-on macro-PIP read (`macro_bridge_zigzag`, folded 2026-07-18; abstains unless a True-Root bridge validates — see "Phase A — Macro bridge read"); |
| The cascade / Root Swing | `read_structure()` root backtracking × `collect_zigzag_candidates()` earliest-valid election (+ the always-on `backext_shared_rail` start refinement, folded 2026-07-18). The elected box is *emergent* — the same pair wins from nearly every scan origin — so the cascade and the election converge on the same anchors |
| "Works both rails" test | `_is_boundary_respected()` + `_validate_base_quality()` (worked-equilibrium occupancy) + the traversal gate |
| Phase C spring | `find_spring()` (bounded-excursion model: penetration → reclaim → significance → hold) |
| Phase D evidence | `resolve_phase_d_boundary()` (support_tests / sos_reclaim / rising_support / inner_box / v_tip; LPS fallback) |
| LPS (mandatory) | `detect_lps()` |

---

## Pipeline Overview

```
Phase 0  Universe & data acquisition          core.pipeline.data public API
Phase 1  Baseline universe filter              core.pipeline.evaluation (apply_baseline_filters)
Phase 2  Chronological structure read          core.structure           (read_structure -> bricks -> Structure)
Phase 2b Crash / extension filters             core.pipeline.evaluation (_evaluate_ticker)
Phase 3  Active LPS/Test election              core.structure           (detect_lps; latest actionable setup LPS)
Phase 3b Phase scoping + bin evidence          core.structure           (phase_d / scope_consolidation / measure_phases)
Phase 4  Scoring, grade & tier assignment      core.scoring             (score_setup, compose_ta_grade, calculate_structure_tier)
Archive  Persist + forward-return backfill     core.archive             (writer / forward_returns / seed)
```

The code is organized as two engines plus a conductor (see [core/MAP.md](../core/MAP.md)):
**`engine_alpha/structure/`** = the Visual Structure Engine (pure geometry/measurement),
**`engine_alpha/scoring/`** = the Scoring Engine (the tunable opinion layer),
**`core/pipeline/`** = the conductor that wires them together, with **`core/archive/`** as the
measuring-stick tooling. Orchestrated by `run_screener()` in
[core/pipeline/screener.py](../core/pipeline/screener.py), running per-ticker evaluation from
[engine_alpha/evaluation.py](../engine_alpha/evaluation.py) in a `ProcessPoolExecutor`.

---

## Phase 0 — Universe & Data

### Ticker universe — `get_tickers()` ([core/pipeline/data.py](../core/pipeline/data.py), implemented in [core/pipeline/tickers.py](../core/pipeline/tickers.py))

1. Read from cached `config/tickers.csv` if it exists and is younger than `TICKER_CACHE_MAX_AGE_DAYS` (1 day).
2. Otherwise download `ftp://ftp.nasdaqtrader.com/symboldirectory/nasdaqtraded.txt`, filter rows where `Test Issue == 'N'` and `ETF == 'N'`.
3. Apply the screenable-symbol filter on both cached CSV reads and fresh FTP downloads:
   alpha-only, <= 5 chars, and excluding 5th-character `R` / `U` / `W` special
   issues (rights, units, warrants) that waste Yahoo requests while still keeping
   real 5-letter common names like `GOOGL`.
4. On fresh NASDAQ directory refreshes, also read `Security Name` and reject
   obvious non-common instruments (warrants/rights/units, preferreds, notes,
   debentures, ETNs, and closed-end funds). Rejected directory facts are persisted
   to `ticker_admission.json` as `invalid_instrument` so Yahoo never has to teach
   us the same lesson with empty history requests.
5. Exclude any one-symbol-per-line entries in `config/ticker_skiplist.txt` before
   market data is requested. This is the manual escape hatch for known delisted or
   permanently broken symbols; the runtime dead-ticker quarantine still handles
   repeated empty Yahoo responses automatically.
6. Dedupe (preserving order) and write back to the CSV cache.
7. Hard fallback to a 15-stock sample if FTP fails.

### Market data — `fetch_data()` ([core/pipeline/data.py](../core/pipeline/data.py), implemented in [core/pipeline/downloads.py](../core/pipeline/downloads.py))

- Reads from `market_data_cache_5y.parquet` and applies an **incremental refresh** policy via `cache_meta.json`:
  - `TTL_FRESH_HOURS_MARKET = 1` (RTH) / `TTL_FRESH_HOURS_OFFHOURS = 12` — under TTL the cache is reused as-is.
  - `FULL_REFRESH_INTERVAL_DAYS = 7` — at least once a week, force a cold 5y refetch regardless of TTL.
  - Between those, `_incremental_fetch()` re-downloads only the last few business days (`INCREMENTAL_OVERLAP_BDAYS = 5`), with a `SPLIT_PROBE_*` guard that detects yfinance's auto-adjust silently rescaling history and falls back to a cold refetch when > 2% of probed tickers drift.
- Cold path: downloads from `yfinance` with bounded per-ticker workers through the shared Yahoo token bucket (`YAHOO_RATE_LIMIT_*`), using `period = "5y"` (`DOWNLOAD_PERIOD`) so weekly/monthly HTF context has enough history.
- The daily structure read still trims to `DAILY_STRUCTURE_PERIOD = "2y"` before `read_structure()`, so the deeper cache feeds HTF context without changing the daily root walk.
- `_recover_missing_data()` re-downloads tickers that came back missing or with < 200 bars (skipped if more than half the universe is missing — likely rate-limit). Recovered columns replace the bad columns and the merged frame is written back to Parquet.
- SPY rides in the same parquet as the screened universe but is excluded from screening — it exists only to feed `get_market_context()` (SPY 6m return + breadth).
- `ticker_admission.json` is checked before every Yahoo fetch:
  - `active_ready` downloads normally.
  - `active_young` has live history but fewer than `ADMISSION_MIN_HISTORY_BARS`
    (200), so it cannot pass the baseline history gate yet; it is skipped until
    `ADMISSION_YOUNG_RECHECK_DAYS`.
  - `yahoo_empty` returned no usable history and is re-probed after
    `ADMISSION_EMPTY_RECHECK_DAYS`.
  - `invalid_instrument` comes from directory facts and is skipped indefinitely.
  Index symbols are never skipped by admission.
- Successful healthy fetches update the admission ledger from actual Close-bar
  counts. A current-but-short symbol is **not** treated as delisted and no longer
  gets an immediate per-ticker fallback retry; it is marked/rechecked as too young.

#### When the provider loses a whole session

Measured 2026-07-27: Yahoo carries **no bar at all for 2026-07-24** — an explicit-window
fetch returns `07-20, 07-21, 07-22, 07-23, 07-27` for every symbol probed, while
`latest_completed_session()` returned `2026-07-24`.

**2026-07-24 was a completely normal trading day** (S&P 500 settled 7,411.98, Nasdaq
24,975.82, Dow 51,947.25). The NYSE calendar here was *right*; Yahoo had simply dropped a
full session across the entire US universe. So the failure class to design for is not an
exotic calendar edge — it is **the provider silently losing a day**, which no amount of
retrying fixes. Every freshness gate keys on Close (`_has_symbol_close`), so a cache 98.1%
complete through 2026-07-23 measured **0.0% coverage** on the expected session.

Consequences worth knowing: the cached panel carries a genuine **one-day hole** at 07-24
(bars go 07-23 → 07-27), no archive row for that date can ever exist, and any measure
reading consecutive bars spans it. `_prepare_ticker_frames` drops the missing bar per
ticker, so nothing breaks — the series is simply one session shorter. This is also the
strongest argument yet for the parked second-provider work: a single source that can lose a
day has no cross-check.

> **Diagnostic caution, learned the hard way.** This was first read as "the provider
> published the session with a null Close", because a probe printed the returned *index*
> and saw a `2026-07-24` row. The values told a different story: that row was the **forming
> 2026-07-27 bar under the wrong date**, which the market open confirmed when 07-27 appeared
> carrying its Open (738.510010) to six decimals. Never conclude a bar exists from its index
> alone.

The 0% verdict is *correct* — the panel genuinely is not current — but three responses to it
were pathological, and each is now bounded:

- **The cold refetch repeated forever.** A cold fetch that misses its coverage gate
  persists nothing and leaves `last_full_refresh` untouched (`_write_unhealthy_cold_result`),
  while `last_full_refresh` is written *only* on the success path — so `weekly_refresh_due`
  stayed True, the incremental path stayed disabled, and the only legal transition was the
  same ~30-minute full-universe download (measured 1709.9 s and 1813.2 s on consecutive
  days).
  A full fetch that comes back with **essentially no closes** now records the session in
  `cache_meta`'s **`absent_sessions`** ledger, and `_cold_retry_blocked()` refuses another
  cold fetch for a session on that list. Three design points, each learned the hard way:
  - **Keyed on the session, not a wall clock.** A time-bounded cooldown is dead exactly
    when it is needed — the measured repeats were ~24 h apart and a Friday loss spans the
    weekend, so any window short enough to be safe is too short to catch them.
  - **Only essentially-zero coverage counts** (`PROVIDER_ABSENT_SESSION_MAX_COVERAGE`; the
    incident recorded 0.0018). A thin or throttled response is a repair target and must stay
    retryable, and so is a shallow-history failure — which is why the record carries a
    `kind` and only the coverage branch arms the ledger. The caller cannot recover that
    distinction later: it would be inspecting the healthy panel preserved on disk, not the
    thin one just fetched.
  - **An empty full-universe pass is NOT an absent session.** It costs the same request
    volume, so it records the failure, but nobody returning anything is a total provider
    failure and marking the session absent would suppress the retry that recovers.

  Honoured **only** with a usable cache in hand — a regime mismatch or truncated history
  still goes cold. A newly completed session is not on the list, so the cache can never
  strand itself, and a human asking for data outranks the ledger: the download-only job
  clears it **immediately before contacting the provider**, not at the top of the request,
  so the override is not spent by the three branches that return without fetching.
- **The latest-session repair ran anyway.** `_repair_latest_session()` saw every symbol
  missing and chunked ~5,500 of them into 55 serial batches. When more than
  `LATEST_REPAIR_MAX_MISSING_FRACTION` of symbols lack the close the cause is the session,
  not per-symbol sparseness, so the repair is skipped — mirroring the >50% dropout guard
  already in `_recover_missing_data`.
  The guard is **opt-in** (`dropout_guard=True`) and only `_cold_fetch` sets it, for two
  reasons found in review. `repair_latest_session_cache` — the manual "Repair N" button —
  passes *only the already-missing symbols*, so `missing == symbols` by construction and a
  fraction test would fire for every N ≥ 1, silently turning that button into a no-op that
  then escalates itself to `symbol_lagging`. And `_incremental_fetch`'s repair is the
  *cheap* retry over a ~6-bar window; skipping it there merely drops through to the 5y ×
  ~5.5k-symbol cold path instead. It additionally requires the repair to span more than one
  batch, so a small universe (`us_sectors` is 13 symbols) still gets its single cheap
  attempt rather than being skipped on a fraction alone.
- **Evaluation was refused outright.** See `session_lag` under Phase 0 health below.

Deliberately **not** changed: the gate still keys on Close, OHLV-only bars are still
refused, and a Close is never synthesised from `regularMarketPrice` (a live quote, not a
settled close). Only what happens *after* the gate fails was touched.

#### The index-close gate, and the universe that names no index

Every freshness gate above asks two questions: *did enough of the universe close*, and
*did the market-regime reference symbols close*. The second half is
`has_all_closes_on(panel, index_symbols, session)` in
[core/pipeline/data_freshness.py](../core/pipeline/data_freshness.py) — the check that
stops a cold write whose SPY/QQQ bar is missing. It is applied at three places (the
cold-fetch success gate and both `_incremental_fetch` legs) and a fourth transitively,
since `last_complete_reference_date` is a loop over it.

`commodities_etf` names **no** index symbols (`index_symbols=()`): the broad-market regime
for the small ETF universes is sourced separately, so no SPY/QQQ rides in that parquet to
anchor on. The predicate read `coverage.total > 0 and coverage.present == coverage.total`,
so *nothing named* came back **False** — "the index closes are missing" — and every gate
fired on a universe that had nothing to miss. Measured: every scheduled scan in the
retained log (8 nights, 2026-08-26 → 2026-09-04) reached **29/29 (100.0%)** and was
discarded anyway. `_write_unhealthy_cold_result` persists no panel, so the parquet was
never written; `price_series` is stamped only by the two success writers, so the meta never
acquired it; and a missing `price_series` defaults to `div_adjusted`, so the regime guard
then refused evaluation *and* archiving. The universe has never written a row to
`setup_archive` **or** `near_miss_archive` since it was registered 2026-06-29. The
`absent_sessions` brake above cannot bound this loop — it arms only on essentially-zero
coverage, and this failure ran at 100%.

The fix is in the predicate, not at the call sites: **an empty symbol set is vacuously
complete** — the convention `deep_history_ratio` already states one function above. A
universe that names index symbols is untouched: `total > 0` there, and every named symbol
must still carry a non-NaN Close. Judged in the helper because the same empty set reaches
four call sites and a carve-out repairs one — `conventions.md` **EC-3** ("fold twin code
paths, never copy") names depth/coverage/scope predicates explicitly, and this class had
already escaped one sweep: `compute_market_data_health()` got its index-less branch in
2026-06-30 while the four downloader sites did not. Note `_has_all_symbols` already read
the same empty set as vacuously TRUE four lines above the `is not None` that read it as
FALSE. An index-less universe is now anchored on its own last complete session. The
`if not scope.index_symbols` branch in `compute_market_data_health()` is **kept**: it still
supplies a reference date when the helper returns `None` for a non-MultiIndex panel. An
empty *panel* is a different question and still answers `None`.

#### Cache health — `compute_market_data_health()` ([core/pipeline/market_data_health.py](../core/pipeline/market_data_health.py))

`_classify()` returns `can_evaluate` / `can_archive` / `can_download` for the cached panel.
Alongside the existing states it distinguishes:

- **`session_lag`** — the panel is complete through its *own* last session but sits behind
  the expected one. `can_evaluate=True`, `can_archive=False`. Gated by
  `_evaluable_despite_lag()` on four conditions, each load-bearing: the gap is ≥ 1 and
  ≤ `MARKET_DATA_EVALUATE_MAX_LAG_SESSIONS`; deep history is intact; coverage on the cache's
  own last session clears `MARKET_DATA_MIN_LATEST_COVERAGE` (so a panel that is *both* behind
  and sparse still blocks); **and the expected session is essentially unpublished**
  (`PROVIDER_ABSENT_SESSION_MAX_COVERAGE` — its OWN constant, deliberately not the complement
  of the trust bar, which would silently invert and admit a majority-published session if that
  bar were ever set below 0.5). That last condition is what keeps a *half*-published session
  out: the panel would carry the new session for some tickers and not others, evaluation reads
  each ticker as-of its own last bar, and the result would be a leaderboard silently mixing two
  dates. A partly-published session is a real repair target. Setting the knob to `0` restores
  the previous hard block.
  **The gap is counted in sessions the provider could plausibly have published** — sessions on
  the `absent_sessions` ledger are discounted. Without that discount a single phantom session
  consumes the whole budget: measured, the 2026-07-24 loss made the tolerance expire at 16:31
  ET the very next day and hard-block evaluation again, defeating the feature. The discount
  excludes both endpoints; excluding the *upper* one is load-bearing, since `expected` is the
  session being waited for and discounting it would cancel the lag to zero, failing the
  `1 <= lag` test on the very day the provider lost it.
  **Archiving.** `can_archive=False` here is the load-bearing block. `scan_job._archive_freshness`
  is *not* a fully independent second gate — its date compare reads the first index symbol only,
  so if the index symbols disagree it can pass. The per-ticker filter in `_fresh_result_subset`
  is the backstop: a row is only written for a ticker that individually carries the expected
  session's close.
  The **download-only** job (`refresh_market_data_cache`) treats `session_lag` as a *failed*
  refresh and raises `StaleMarketDataError`: it is readable, but that job exists to reach the
  expected session, and without this it would exit 0 / status `ok` and raise no alert on a day
  the cache never advanced. It does **not** call `record_repair_attempt` on that state — that
  helper's vocabulary is per-symbol sparseness, and on an absent session the missing set is the
  whole universe, so its signature is identical every attempt and escalates to `symbol_lagging`
  on the third, which sets `can_download=False` and disables the Refresh button until something
  unrelated heals the cache.

  **Cache-mode evaluation tolerates it.** `_archive_freshness` returns a distinct
  `"session_lag"` status (carried onto the exception as `freshness_status`, so callers need not
  re-match diagnosis prose), and `_passes_archive_freshness` treats it in cache mode exactly
  like a partial-coverage day: refresh the dashboard, skip the archive, exit 0. Without this the
  operator watched his leaderboard render and then vanish behind a red failure, while a page
  reload showed it sitting there fine. Tolerated still means **not archivable** — it is not in
  the `degraded_coverage` set, so no per-ticker subset is written either.
- `coverage["cache_last"]` reports completeness through the cache's own last session — the
  number that tells a one-session lag apart from a dead cache. The other three coverage
  figures are all measured on the *expected* session and read 0% together when the provider
  has not published it.
- The returned dict now includes `weekly_refresh_due`. It was accepted as a parameter but
  never emitted, so `scan_job._refresh_market_data_cache_locked` read `None` from
  `.get("weekly_refresh_due")` and its guard collapsed to "if archive-healthy, do nothing" —
  the Refresh button silently skipped the weekly cold refetch it was labelled for.

---

## Phase 1 — Baseline Universe Filter

`apply_baseline_filters()` ([engine_alpha/evaluation.py](../engine_alpha/evaluation.py)).

Reject the ticker entirely if any check fails. Run in this order:

| Gate | Rule | Setting |
|------|------|---------|
| History | `len(df) >= 200` bars | hard-coded |
| Price floor | `Close >= MIN_PRICE` | `MIN_PRICE = 3.0` |
| Liquidity | `Vol_50 >= MIN_VOLUME_50D` | `MIN_VOLUME_50D = 50_000` |
| Above 50d trend | `Close >= SMA_50` | hard-coded |
| Above 200d trend | `Close >= SMA_200` | hard-coded |
| 12-month return | `(Close - Close[-252]) / Close[-252] >= MIN_YEARLY_RETURN` | `MIN_YEARLY_RETURN = -0.20` (modest drawdowns OK) |

While computing baselines we attach `SMA_50`, `SMA_200`, `Vol_50`, and `Spread = High - Low` to the DataFrame for downstream use.

**The 50-day dip exception (`SMA50_DIP_EXCEPTION_ENABLED`, dark — miss program
2026-08-28).** An `sma50` refusal is admitted into chart reading when the dip
under the 50-day is a bounded, recent, already-recovered event
(`_sma50_dip_admits`): the last close at/above SMA_50 printed within
`SMA50_DIP_MAX_SESSIONS` (25), and the close sits within `SMA50_DIP_MAX_ATR`
(1.0) ATR_10 below it. The SMA_200 and YoY legs still gate behind it — a dip
exception is never a downtrend exception — and geometry stays the only veto
downstream. Built for the SKYT class (the drawn spring's own drag under the
50-day; with the door held open its 2026-04-07 session elects a complete
strict-pool structure): evidence + flip asks in
[miss_program_2026-08.md](miss_program_2026-08.md). Flag off = byte-identical.

**The bottoming-base lane (`BOTTOMING_BASE_LANE_ENABLED`, dark — operator
ruling 2026-08-29).** An `sma200` refusal is admitted when the 50-day is
reclaimed (`Close >= SMA_50`) — a bottoming base is read only once its
intermediate trend has turned. The lane's second half opens the sma200 rule's
OTHER layer under the same flag+condition: `collect_root_anchors`' 
`below_trend_sma` seeding refusal defers when the last close sits at/above the
mean of its trailing 50 closes. The two door lanes can never chain a
both-smas-under chart through (pinned): a dip-excepted frame under the 50-day
is refused at the sma200 leg. Built for MDT (fires 2026-07-14 tier S at his
drawn R 82.83); evidence in [miss_program_2026-08.md](miss_program_2026-08.md).
Flag off = byte-identical.

`_evaluate_ticker()` then attaches `ATR_10` and `ATR_50` ([engine_alpha/structure/indicators.py](../engine_alpha/structure/indicators.py): Wilder's smoothing via SciPy `lfilter`). `ADX` is implemented in `indicators.py` but **not used** — nothing in the live screener reads it today.

### Market-context broadcast — `get_market_context()` ([core/pipeline/data.py](../core/pipeline/data.py), implemented in [core/pipeline/market_context.py](../core/pipeline/market_context.py))

Before per-ticker workers fan out, the orchestrator computes two scalars once and pickles them into every worker:

- **`spy_6m_return`** — SPY close-to-close return over `RS_LOOKBACK_BARS` (126 bars). Feeds the Soft RS bonus in scoring (`excess_return_6m = stock_6m − spy_6m`).
- **`breadth_pct`** — share of the screened universe with `Close > SMA_50`. Persisted to the archive (`_breadth_pct`) and used by the market-breadth bonus in scoring; never used as a hard gate.

Cached in `market_context.json` next to the parquet with TTL 1h during market hours, 12h otherwise; invalidated when SPY's last-bar date changes.

---

## Phase 2 — Consolidation Detection

`read_structure()` ([engine_alpha/structure/narrative.py](../engine_alpha/structure/narrative.py)) is the live entry point. It assembles one Wyckoff story through pure brick validators in [engine_alpha/structure/bricks.py](../engine_alpha/structure/bricks.py):

1. `find_root_swing()` — next calibrated climax -> automatic-reaction anchor, oldest-first.
2. `validate_equilibrium()` — a real worked Phase-B box, using the existing zigzag candidate and traversal gates.
3. `find_spring()` — optional Phase-C spring / shakeout.
4. `find_inner_box()` — optional tighter Phase-D mini-consolidation in the recent half of the parent.
5. `find_lps()` — mandatory active LPS/Test, inner first when a tighter inner box exists, otherwise parent.
6. `resolve_phase_a()` — reconnects the local climax -> AR bridge whose reaction lands at the validated box start.

If any required brick fails, the reader advances to the next root swing and tries again. If no complete A -> B -> (C?) -> D/LPS narrative holds, the ticker has no setup.

**The contraction rescue (`CONTRACTION_RESCUE_ENABLED`, dark — miss program
2026-08-28).** On a FULL refusal — every root refused; never after a
cause-before-effect abstention, which is doctrinal and final —
`read_structure` re-walks once under the one scoped override with
`POWER_PLAY_STORY_FORM_ENABLED` armed, so the story pool may also admit
through the resistance-contraction form (`event_map.resistance_contraction_admission`).
Scoped to full refusals by construction, the rescue can never displace an
existing election (the WCC wider-box re-election that refused the global form
flip is unreachable), and it skips itself when the form is already armed (the
species lane's scoped read). A rescued fire elects `elected_pool='story'` with
the self-naming contraction profile. Trace records of the second pass carry
`pass="contraction_rescue"`. Evidence (EGBN 01-07 tier A on his rails, PKE
02-18 tier B; junk corpus clean) + flip asks in
[miss_program_2026-08.md](miss_program_2026-08.md). Flag off = one walk,
byte-identical.

`consolidation.detect_boxes()` / `find_outer_box()` remain for diagnostics and low-level compatibility. The live pipeline consumes the `Structure` from `read_structure()` and adapts it into the legacy parent/inner shape internally so scoring, archive, and chart payloads stay stable.

### Setup

- `eval_df = df.iloc[:-STRUCTURE_EDGE_SKIP_BARS]` (default 5) — last 5 bars are excluded from structural anchoring as trigger/edge noise.
- Require `len(eval_df) >= MIN_BASE_DAYS + 15` = 35 bars.
- ATR snapshot: take `df.iloc[-1]['ATR_10']` from `eval_df` (which equals `df.iloc[-6]['ATR_10']`) to share one volatility frame with the LPS detector.
- **Macro gate (re-asserted):** at `eval_df.iloc[-1]`, `Close > SMA_200`. (Baseline already enforced this at the latest bar; this re-asserts at the evaluation bar so the function works standalone.)

### Phase A — Anchor Discovery

Walk bars from `scan_hi = end - MIN_BASE_DAYS` down to `scan_lo = TREND_MIN_MOVE_BARS + 5`. Each bar `i` is tested as both a possible **BC (Buying Climax)** and **SC (Selling Climax)**.

**BC qualification:**
1. `highs[i]` is the maximum over the last `LOCAL_PEAK_BARS` (30) bars.
2. Within the prior `TREND_PRIOR_LOOKBACK` (100) bars there exists a low such that `highs[i] / trough_low - 1 >= TREND_MIN_GAIN_PCT` (15%) AND the rise spans ≥ `TREND_MIN_MOVE_BARS` (20) bars.
3. **Automatic Reaction:** within `AR_MAX_BARS` (15) bars after `i`, some close drops `>= AR_MIN_DROP_PCT` (5%) below `highs[i]`. Phase B starts at the **AR low** (skips the descent so it doesn't pollute boundary respect).
4. The remaining window after the AR low must be `>= MIN_BASE_DAYS` (20).

**SC qualification:** mirror — `lows[i]` is local trough over 30 bars, fell ≥ 15% from a prior peak (≥ 20 bars), validated by ≥ 5% bounce within 15 bars; Phase B starts at the **bounce high**.

### Phase A — Anchor Selection & Backtracking

`collect_root_anchors()` is built most-recent-first; `find_root_swing()` reads it oldest-first and returns the next root swing at/after the reader's search cursor. The reader then asks Phase B and Phase D to validate the story born from that root. If the box fails, the spring/LPS path fails, or no active LPS exists, the cursor advances past that climax and the reader tries the next pair of limbs. This preserves the "earliest valid cause" bias without forcing an invalid old trend top onto a newer worked base.

### Phase A — Locality Resolution

`resolve_phase_a()` ([engine_alpha/structure/bricks.py](../engine_alpha/structure/bricks.py)) repackages `segment_swings()` ([engine_alpha/structure/segmentation.py](../engine_alpha/structure/segmentation.py)) after the box is known. It returns the **local** climax -> automatic-reaction bridge whose reaction low lands within `_SEG_AR_TOL` (10) bars **at or before** `box.start_bar` (never after — Phase A ends where Phase B opens, the `ar_bar <= phase_b_start_bar` invariant); if that bridge is unavailable it falls back to the segmentation root, then to a **local synthesis**. The same worked box is reached from nearly every candidate root, so the seed root is only a *scan origin*, not the box's cause; when that seed sits more than `_SEG_LEAD_IN` (60) bars before the box — an ancient origin reaching through to a recent range — the fallback anchors the AR at the box open and the climax at the highest High in the preceding 60-bar run-up, never the stale seed climax (which would otherwise paint, e.g., a 2024 climax on a 2026 box). This fixes the "distant trend top seeds a recent box" problem: Phase A is **guaranteed local** — it belongs to the consolidation that actually validated, not the first trend climax that merely started the search. (`tools/structure_case_audit.py` is the read-only surface for confirming which root won and whether the drawn Phase A is local.)

**Climax terminality (2026-07-19).** Locality alone was not enough: a seed within the
`_SEG_LEAD_IN` window could still be a *mid-trend* pause — FLXS's 04-28 seed sat 41 bars
before the 06-26 box, so the ancient-origin synthesis never triggered, the seg bridge
found no counter-swing at the box door (the trend rips *upward* into a continuation
base), the seg root's true climax (07-02) was rightly refused for landing inside the
box, and the raw-seed fallback painted `bc + AR_MAX_BARS` — a synthetic 15-bar "AR"
while price ran +38.5% past the claimed climax. `_enforce_climax_terminality()` (wired
in `resolve_phase_a()` after the BC-down enforcement, before the AR tighten) applies
the macro bridge's True-Root rule to every calibrated path: post-climax price up to the
box open may exceed the climax by at most `PHASE_A_CLIMAX_TERMINALITY_EXCESS` (0.25) ×
bridge height (ATR floor guards degenerate heights; mirror-symmetric for down causes;
an undecidable direction passes through). A violating pair re-anchors to the
`_SEG_LEAD_IN` run-up extreme → the box open, the same local synthesis the
ancient-origin fallback uses — terminal by construction.

**Polarity re-keyed 2026-08-19 (`_cause_is_up`).** Which end of the lead-in the repair
takes was decided by `root.kind` — the seed's BC/SC label. That is the keying
`decisions.md` ruled **Tested-DEAD** on 2026-07-27 ("the root is only a scan origin, not
the box's cause"), and the same row prescribes the remedy the fix takes: the direction
now comes from the **confirmed segment covering the box-open bar**, read off
`market_structure.trend_terminal_floor`'s `direction` array (cause-wins overlap
resolution — previously carried for diagnostics only, now load-bearing). The floor is
computed lazily inside the guard, so only reads that complete a story pay for it — since
the trend-terminal gate retired (2026-09-08) that is the only path, and this guard is the
floor's ONLY consumer. The seed
label survives **only** where no confirmed segment covers the open, so a frame with no
readable trend keeps its previous repair. Evidence: the seed label contradicted the
drawn pair on 4 of 4 live marked names (seeds 255–417 bars away); CNI's raw resolver had
returned the operator's exact pair and the mis-polarised branch overwrote it, and now
resolves to his date. Aggregate against the nine marks: earlier-than-his-end 5 of 6 → **3
of 6**, median −36 → **−9** bars; **HTH regresses** −6 → +54 (its old closeness was two
large errors cancelling). Pinned by `test_climax_terminality_polarity_follows_the_
covering_segment_not_the_seed` + the no-cover fallback twin. Full diagnosis:
[climax_anchor_diagnosis_2026-08-19.md](climax_anchor_diagnosis_2026-08-19.md).

This affects Phase-A scoping diagnostics (`_bars_since_BC`, `_descent_length`, chart-region labels, and Bin A). It does **not** feed R/S selection, LPS detection, scoring, tiering, or filtering.

### Phase A — First-reaction AR anchor — RETIRED 2026-09-08

**Deleted on the operator's ruling** ("Lets DELETE the first two"), one week before its
2026-09-15 kill-by. Never live: dark from 2026-07-04 to deletion, so nothing the engine
reads changed.

It tightened the drawn AR to *the low of the first continuous reaction after the trend's
terminal swing* — the right Wyckoff move, and its SHAPE was vindicated (spans of 1–7 bars
against his own 1–5; on HTH its AR landed on his trend end to the bar). **Its ANCHOR was
wrong**, and that is why it died: the engine's climax is not the trend end. Measured against
his own dated marks on the cohort deliberately chosen to flatter it — the twelve largest
tighteners in the universe — flag-OFF was closer on 4 of 6, total |error| 133 bars against
266. Re-measured 2026-08-31 against the repaired climax polarity it moved FURTHER away, not
closer: it now touches fewer charts (101 of 335, was 100 of 291) and disagrees by more on
the ones it touches (tighten median 19 → 35 bars). On his own marks it is a no-op on 3 of 4
live reads and loses the fourth badly.

The mechanism matters more than the verdict, and it is why deleting this costs nothing:
flag-OFF pins `ar_bar` to `box.start_bar`, and **the operator's AR IS the box open by his
own repeated definition** (*"AR at 17/06 which also serves as the root swing for the
consolidation"*, on IRMD, IART and CYRX). Flag-off satisfies his identity by construction.
The retarget broke that identity to re-attach the AR to a reaction off `climax_bar` — correct
if `climax_bar` were the trend end, which it is not. **That defect is a live open program**
([`climax_anchor_diagnosis_2026-08-19.md`](climax_anchor_diagnosis_2026-08-19.md)): the
climax is reconstructed backward over a FIXED 60-day window, so box placement determines the
anchor error entirely. Fixing that is the work; this flag was never going to.

**What survived:** `market_structure.elected_trend_leg_base` (the full-leg base), because
[`tools/full_package_render.py`](../tools/full_package_render.py) draws it and the
climax-anchor program it serves is open; and the anchor half of
[`tools/operator_marks_diff.py`](../tools/operator_marks_diff.py), whose flip half retired
with the flag. **What went with it:** `bricks._first_impulse_ar_end`,
`market_structure.first_reaction_after`, the flag plus its four `AR_*` tuning constants,
their five manifest rows, and `tools/ar_first_reaction_diff.py`.

### Phase A — Macro bridge read (live; folded 2026-07-18)

`macro_bridge_zigzag()` ([engine_alpha/structure/phase_a.py](../engine_alpha/structure/phase_a.py), formerly `pip.py`), wired
unconditionally through `segment_swings()` ([engine_alpha/structure/segmentation.py](../engine_alpha/structure/segmentation.py))
(folded 2026-07-18; formerly flag `PIP_MACRO_PHASE_A_ENABLED`, live 2026-07-04). A multi-resolution PIP (Perceptually Important Points)
skeleton is ranked **once** (`pip_indices` — the ranking is strictly nested, so top-K is an
exact prefix of top-K+1), then walked coarse→fine from `K=4` up to `PIP_MACRO_K_MAX` (24):
the read stops at the **smallest** skeleton holding a validated climax→AR bridge, so the
macro trend-end is found before range noise can steal the climax.

`_validated_bridge` enforces the **True-Root rule** — *a bridge qualifies only if it leads
to an actual equilibrium*:

- **interior AR** — the right edge is "now", never an AR;
- **room for a base** — ≥ `PIP_MACRO_MIN_BASE_BARS` (= `MIN_BASE_DAYS`) bars after the AR;
- **AR extremity** — the AR is its own leg's extreme (no crash hiding inside the bridge);
- **climax terminality** — post-AR highs ≤ climax + `PIP_MACRO_MAX_POST_EXCESS` (0.25) × bridge height;
- **floor holds** — post-AR breakdown ≤ `PIP_MACRO_EQ_FLOOR_FRAC` (0.5) × height (spring-tolerant);
- **two-sided oscillation** — rally off the AR **and** give-back each ≥ `PIP_MACRO_EQ_OSC_FRAC` (0.3) × height.

Climax candidates are tried in descending extremity, so an unconfirmable right-edge
higher-high can't block a genuine older climax. Any failure → the macro read **abstains**
(returns nothing) and the calibrated order-N read speaks — the merge contract. On
validation the story is **truncated at the AR** (binding: downstream can never draw an
unvalidated sibling swing), the root direction comes from the bridge type (never
re-derived from window net sign), and `resolve_phase_a()` passes box-relation constraints
(bridge kind must match the canonical BC/SC root; the AR must not overrun the box birth at
all — Phase A ends where Phase B opens, the chronological invariant `ar_bar <=
phase_b_start_bar`; an earlier AR is allowed within the `_SEG_LEAD_IN` (60) lookback; AR
price must reach the box level ± touch tolerance) so a macro story can never float away from
the elected box or paint Phase A inside it. Affects the **Phase-A overlay and the
cause-before-effect veto** — `bricks.cause_maturity` reads the macro bridge inside the LIVE
election veto (flipped 2026-07-20), so a guard change here can move elections; R/S selection,
LPS, scoring, tiering read nothing else from this wire. Eyeball evidence: `tools/fidelity/pip_phase_a/`; scan tool:
`python -m tools.phase_a_pip_diff --jobs N`.

### Phase B — trend-terminal box gate — RETIRED 2026-09-08

**Deleted on the operator's ruling** ("Lets DELETE the first two"), one week before its
2026-09-15 kill-by, which was its second and last. It was never live: dark from the day it
was built 2026-07-27 to the day it was removed, so nothing the engine reads changed.

The rule it enforced — *a box may not OPEN before the trend running into it printed its
climax, and if that climax lands inside the box at least `MIN_BASE_DAYS` must have printed
since* — came from a real operator ruling on LIVN and that **DOCTRINE stands**, recorded
append-only in [`decisions.md`](decisions.md) (2026-07-27, 2026-08-14). What was deleted is
an implementation of it that could never be ruled on its own merits: across three A/Bs the
loss cohort turned over **completely** each time (the intersection of any two of the three
loss sets is empty), so its evidence could never bank, and the class-B losses kept their
claimed climax *above the box's own R* — 9 of 9 in August, 5 of 5 in the final read — which
is the fingerprint of `segment_trends` box-blindness, not of a box that opened too early.
The full measured recommendation is
[`trend_terminal_killby_2026-08-31.md`](trend_terminal_killby_2026-08-31.md).

**`market_structure.trend_terminal_floor` SURVIVES and is unconditionally live** — it feeds
Phase A's climax polarity re-key (`bricks._cause_is_up`, above), which is the expensive and
hard-won half. Only the *legality test* built on top of it retired. Re-implementing the gate
later is a fresh A/B against a fixed `segment_trends`, not a revert of this change.

> **Overshoot magnitude is still NOT the test — falsified three times (2026-07-27), and it
> stays Tested-DEAD independently of this deletion.** The operator ACCEPTS boxes whose trend
> ran **47.9%** (PXS), **82%** (VIK) and **101%** (MATX) of a box height past R, and REJECTS
> LIVN at **20.57%**. Those large overshoots are upthrusts *inside* an established base — on
> PXS he deliberately draws R at 4.66 beneath the 4.92 spike. A `TREND_TERMINAL_OVERSHOOT_BOX`
> knob was built, measured, and removed. Do not re-propose it.

### Phase B — Zigzag S/R Anchoring

`phase_b_zigzag()` ([engine_alpha/structure/box_primitives.py](../engine_alpha/structure/box_primitives.py)).

1. **Pivots** — `_find_pivots()` (vectorized; asymmetric `>=` left, `>` right so flat tops/bottoms still pivot at the rightmost — the structurally meaningful "last touch"):
   - `ORDER = PIVOT_ORDER_LONG (2)` if window ≥ `PIVOT_ORDER_THRESHOLD (40)` bars, else `PIVOT_ORDER_SHORT (1)`.
2. **Zigzag construction** — `_build_zigzag()`: merge peaks + valleys chronologically, enforce strict alternation; on consecutive same-type pivots, keep the more extreme (higher peak or lower valley).
3. **ATR reference** — use the engine-aligned snapshot from the reader if supplied; otherwise the median `ATR_10` over the last `PHASE_B_ATR_WINDOW` (30) bars; final fallback = median(High-Low).
4. **Candidate generation** — only **strictly consecutive** zigzag pairs (peak→valley or valley→peak) are tested. The peak's High = R, the valley's Low = S.
5. **Per-candidate validation — the "worked equilibrium" test.** A candidate (a
   Resistance-anchor / Support-anchor pair) is a REAL trading range only if price
   *respects, touches, and zigzags through both rails constantly, with no dead
   space*:
   - **Box width:** `(R - S) / S <= MAX_BOX_WIDTH` (0.18 — a range wider than this
     is the BC→AR extremes, not a tradeable equilibrium).
   - **Boundary respect** — `_is_boundary_respected()`:
     - Buffered band `[S - 0.5·ATR, R + 0.5·ATR]`; wicks count as breaches.
     - ≥ `MIN_BOUNDARY_RESPECT_PCT` (80%) of bars inside the band, no consecutive
       outside run longer than `MAX_CONSECUTIVE_OUTSIDE_DAYS` (10).
     - **The outside bars are named (engine-eyes Task 1, 2026-09-05; measure-only).**
       Beside the engagement hang masks, `box_gates._whole_bar_rest_masks` reads
       the two whole-bar forms against the rail LINE (`rest_above_r` = Low > R,
       `hold_below_s` = High < S), `_outside_bar_forms` partitions every outside
       bar into exactly one of `OUTSIDE_BAR_FORMS` (whole-bar first, then the
       hang as `poke_close_back`, else `straddle_close_out`), and
       `_outside_run_census` types each contiguous run (side, trading days, form
       counts, deepest excursion, resolution ∈ `RUN_RESOLUTIONS`: pivot_back on a
       later bar wholly under the line / hover / right_edge / over_cap). The run
       arithmetic is `_run_spans`, shared with the gate's own run maximum.
       `metrics.measure_gate_margins` derives the archived `eq_*` descriptors
       (`OUTSIDE_BAR_MEASURES` + `eq_traversals_per_20d`) once on the elected
       box; `tools.calibration_stat_card` prints the same columns and the
       census totals on the drawn windows. No gate consults any of it — the
       forms-as-admission re-count is Tested-DEAD (2026-09-04 bench).
   - **Worked-equilibrium occupancy** — `_validate_base_quality()`:
     - In-base crash filter: `min(Low) >= S × CRASH_FILTER_MULT` (0.70).
     - **Constant two-sided touch:** ≥ `EQ_MIN_TOUCHES_PER_RAIL` (3) on each rail,
       each touched in ≥ `EQ_MIN_TOUCH_THIRDS` (2) of 3 time-thirds (not clustered).
     - **No dead space:** ≥ `EQ_MIN_HALF_DWELL` (0.15) of closes in BOTH the lower
       and upper box third, and box-height `coverage` ≥ `EQ_MIN_COVERAGE` (0.80).
     - **Not mid-churn:** middle-third dwell ≤ `EQ_MAX_MID_DWELL` (0.45).
     - **Bar-as-unit dwell — gate form tested and REJECTED 2026-07-25; kept as
       the MEASURE `_dwell_bar_basis`** (docs/bar_dwell_protocol_2026-07.md,
       sealed campaign; the operator's THIRD bar-as-unit statement). The read:
       lower/upper ENGAGEMENT — a bar whose Low/High reaches the end third has
       worked it — plus mid RESIDENCY (bars living entirely interior). It
       diagnoses EGBN exactly: at his drawn box the lower third holds 3/23
       closes but **8/23 bar-lows** (his named support tests 2025-12-24 and
       2026-01-02 are bar engagements whose closes recover — the definition of
       a support test), and the sealed fire A/B converts EGBN AT his rails on
       his bar (first_fire 2026-01-02). **But the gate form is dead:** swapped
       into `_validate_base_quality`, 10/26 ratchet hit identities break (MATX
       stops firing; FOSL/NGL/NTCT/ROIV/WTS elect displaced boxes; BWA/EWTX/
       MS/VIK re-date) and junk **DGII + FLG fire** — DGII being EGBN's
       statistical twin, now proven twin THROUGH fire level. Close-residence
       dwell is load-bearing for ELECTION STABILITY ("Phase-B rails do not
       drift" is measured fact), not merely junk defense. Do not re-request a
       basis swap; converting EGBN without breaking the fleet requires NEW
       measured information (the operator's narrative separator: SOS → Test →
       SOS 2 → True LPS; excursion→recovery-into-box) — the event-sequence
       direction, recorded for the TA-score / narrative program.
     - Public `metrics.measure_dwell_balance()` (formerly `measure_equilibrium`;
       the Equilibrium name now belongs to the rail-to-rail swing read, formerly
       `measure_traversal`) additionally reports High/Low range occupancy for
       analysis, but the box-of-record selector keeps close residence as the
       calibrated dead-space gate so Phase-B rails do not drift.
   - The old "≥2 touches + N midline crosses" gate is retired — a wide box
     mechanically racked up crosses while a one-time AR low left dead space
     beneath the real range, so the widest framing always won.
   - **Traversal gate** — `_apply_traversal_gate()` requires real rail-to-rail
     swing travel: at least `TRAVERSAL_MIN = 2` full traversals and density at
     least `TRAVERSAL_MIN_DENSITY = 0.08`. This is the swing-structural guard
     against boxes that technically touch both rails but leave one side mostly
     dead.
   - **SOS trim rescue** — a worked box whose right side has already broken out
     and held above R can be validated over the worked cause before that
     breakout tail. This rescues break-above-R-then-rest structures (e.g. a valid range that
     backs up to an LPS) without moving ordinary in-range setups.
   - **Deep-excursion pair pool (`BAND_RAILS_ENABLED`, LIVE since 2026-07-16 —
     Event Map Task 11)** — a LAST-RESORT pool consulted only when the
     strict AND rescued pools are both empty, so an ordinary election can
     never move. It re-judges the SAME chronological zigzag pairs (the
     operator's rail rule: anchor R/S from the swings in chronological order,
     wick to wick) with band-leaving excursions typed as EVENTS
     (`engine_alpha/structure/rail_qualification.py`, formerly `band_rails.py`):
     a below-rail episode —
     same-side spans merged across short inside-runs, spring-then-test is
     ONE event — must penetrate, RECLAIM, and HOLD; an above-rail poke must
     fail back and never be exceeded; otherwise the pair dies as a
     breakdown/breakout, exactly as before (the operator's BODI ruling: the
     deep collapse is PHASE C inside one box, "not a box break").
     **Sequence-aware HOLD chain (2026-07-16):** successively deeper
     below-rail events that each reclaim and hold are ONE progressive
     Phase-C step-down — an earlier event's extreme may be undercut only by
     a later qualified event (the working floor steps to the most recent
     event's extreme; non-event bars must respect that standing floor), and
     the FINAL event answers the original never-undercut rule against all
     remaining tape. A pure relaxation: every single-event window judges
     exactly as before. Two hard caps bound what may be typed an event at
     all: `BAND_EVENT_MAX_DEPTH_ATR = 5.0` — an excursion digging deeper
     below the rail is a genuine breakdown, never a terminal shakeout
     (calibrated between BODI's measured chain, 0.86→3.34 ATR, and the
     EGBN 7.68–9.98 ATR over-reach class it kills) — and
     `BAND_EVENT_MAX_BARS = 20` — a run below the rail lasting months is a
     markdown leg, not an episode (EGBN's stale April framing rode a 40-bar
     "event"; BODI's real episodes run 12–18 bars). A non-finite or
     non-positive ATR refuses event-typing outright (quarantine — NaN masks
     must not silently report "no excursions"). **Flip-battery bounds
     (2026-07-16, negative-corpus regressions caught at the live flip):**
     *above* the rail the pool grants no more patience than the respect
     gate's own forgiveness horizon — an above-rail span longer than
     `MAX_CONSECUTIVE_OUTSIDE_DAYS` is a DEPARTURE (the range is not in
     force), never a poke (DBD: a 15-bar, 4.1-ATR rally above R rode the
     uncapped above loop into a tier-S election on rails that were no longer
     in force — the operator confirms DBD's consolidation itself is tight;
     the junk was the mis-framed range, 2026-07-17); and the judged
     window must be a MATURED cause — at least 2 × `MIN_BASE_DAYS` judged
     bars after excision — because a terminal shakeout ends a long Phase B,
     it does not interrupt a five-week flag (SPCB: a 34-bar high-flag whose
     left half was the +35% rally leg itself scraped every gate on 30 judged
     churn bars). Qualified event bars are
     excised from the judged window; every gate in this list runs UNCHANGED
     and full-strength on the remaining bars, except that a pair carrying a
     qualified DEEP below-rail event (multi-bar, beyond S − 2×buffer) may
     measure up to `BAND_MAX_BOX_WIDTH = 0.23` wick-to-wick — the allowance
     exists only with the event, so it can never act as a general width
     loosening. The respect gate is untouched. The qualified deep event also
     feeds Phase C as `bin_c_type = TERMINAL_SHAKEOUT` when the calibrated
     spring detector finds nothing (see the Phase C bin note). Harness proof
     at the marks (2026-07-16, flag-on variant): BODI fires tier A at the
     operator's exact rails (12.33/10.18) on 04-10; both EGBN over-reach
     fires are dead. The operator's A/B rail eyeball over
     `docs/phase_c_marks_2026-07.json` landed 2026-07-11 FAVORABLE; the
     operator granted the flip 2026-07-16 and the flip battery (full pytest,
     shadow re-capture, stage-matched BODI ratchet reseal, negative corpus,
     hermetic recall) ran green with the two bounds above.
6. **Structural-quality score:** every *valid* candidate gets
   `combined = 0.4 × box_tightness + 0.4 × touch_density(/10) + 0.2 × coverage`.
7. **Candidate selection (`select="earliest"` live default):** choose the
   **earliest** `cand_start` among the valid candidates (longest cause),
   tie-broken toward higher quality — "the earliest *of the ones that qualify*."
   There is no reach-quality floor anymore: a sparse / dead-space framing can no
   longer be valid, so the support anchor naturally climbs off one-time lows
   until the band is genuinely worked. **If no candidate is valid → no box → the
   stock is rejected.**

   > **Stale-frame dethronement (`ELECTION_DETHRONE_ENABLED`, LIVE since
   > 2026-07-16 — solve-the-engine task 13).** A rescue-propped (SOS-trim) framing whose
   > buffered R the tape has left FULLY behind for the trailing
   > `ELECTION_DETHRONE_SESSIONS = 10` sessions has stopped being the
   > operative structure: flag-on it loses the election **in favor of a
   > later valid framing** (never into an emptier read; dethroned pairs
   > narrate as `dethroned` in the cascade trace). One trailing pass over
   > the already-loaded window; pure function of the frame. Proof at the
   > marks: with the holding-shelf flag, MATX fires 06-29 tier S at rails
   > within tolerance the evening before its breakout; hermetic corpus
   > sweep shows zero non-target elections moving. The sibling
   > rescued-pool arbitration lever was built and REJECTED (it killed
   > VIK's pinned hit; no clean currency rule separates the good early
   > framing from the bad — the shelf-R lesson at election scope; the
   > counterexample is recorded at the pool seam).

`select="best"` remains a diagnostic mode (highest combined regardless of start);
`select="debug"` returns the valid-candidate landscape. The inner Phase-D
mini-consolidation runs the same worked-equilibrium validity one scale down
(mini Resistance/Support anchors) but still selects for tightness.

#### `cand_start` trim — measure on the actual chop window

Phase B begins at the AR *low* (or the bounce *high* for SC anchors), but the structural box rarely starts there — it starts at the next zigzag pivot, which is the inner "mini BC" / "mini AR" that opens the working consolidation. Bars between the outer AR and this inner pivot are the early-chop drift, not part of the box, and including them in boundary respect / base quality measurement inflates breach counts and forgives wicks that aren't really chop. To correct this, every candidate inside `phase_b_zigzag()` is measured on its own bar window: starting at `cand_start = min(r_anchor_bar, s_anchor_bar)` (the earlier of the two zigzag anchors that define R and S). Both `_is_boundary_respected()` and `_validate_base_quality()` run over `eq_df.iloc[cand_start:]`, so the boundary-respect % and the touch / midline-cross counts reflect the actual chop range, not the BC→AR span. The returned `base_length` is also the trimmed length (`base_length - cand_start`), and the r/s anchor bars are rebased to it. The outer BC anchor (`bc_anchor_bar`) remains df-positional — only the box window itself is trimmed.

`phase_b_zigzag` returns: `(base_length, R, S, box_width, r_touches, s_touches, total_outside, r_anchor_bar, s_anchor_bar)`.

The live reader returns a `Structure` object with the validated parent `EquilibriumBox`, optional `InnerBox`, optional `Spring`, winning `Lps`, phase boundaries, and Phase-D evidence. `_evaluate_ticker()` adapts that into the legacy parent tuple internally: `(base_length, R, S, box_width, r_touches, s_touches, breach_days, r_anchor_bar, s_anchor_bar, bc_anchor_bar, phase_b_start_bar, is_inner_box)`. `bc_anchor_bar` / `phase_b_start_bar` are df-positional and feed the `_bars_since_BC` / `_descent_length` archive fields. Diagnostic `detect_boxes()` still returns `{"parent": <12-tuple>, "inner": <dict|None>}` for tools.

`r_anchor_bar` / `s_anchor_bar` are returned in **eq_df-relative** (base-relative) coordinates — the dashboard and SQLite archive consume them that way. The LPS detector translates them into df-positional indices locally.

### Phase 2b — Crash & Extension Filters

After consolidation passes, `_evaluate_ticker()` re-checks at the latest bar:

- **Crash filter:** `Close >= S × CRASH_FILTER_MULT` (0.70).
- **Extension filter:** `Close < R × EXTENSION_FILTER_MULT` (1.15) — too far above R means the move has already gone, no entry left.

---

## The Phase D Model — Reading the Right-Most Region

Phases A and B establish *where the base is* and *what its R/S are*. But everything a trade actually depends on happens in **Phase D — the right-most region of the consolidation**, where the LPS is evaluated before markup. This is the part a human reads *first* when scanning, and it is the north star the engine exists to honor: read Phase D faithfully and the rest is context.

**Phase D is defined by its Last Point of Support (LPS).** The LPS is the foundation of every setup worth considering — no LPS in the right-most region means no Phase D and no setup. This is not aspirational: `detect_lps()` is mandatory in the pipeline, and a ticker with no qualifying LPS is dropped (`_evaluate_ticker` returns `None`).

**What an LPS is (and isn't).** An LPS is **support forming and holding around the support zone, in general** — price returns to the floor and holds. It is **not** *defined* by being a higher low. A higher-low / ascending / "tennis-ball" shape is **rewarded, not required**: plenty of valid LPSs simply form around the support zone without stair-stepping up. The implementation already reflects this general definition:

- the pullback-shape gate is **graded, not binary** — `descent_frac` *multiplies* LPS quality rather than rejecting non-higher-lows (Phase 3, gate 5);
- the zone gate accepts the LPS **anywhere around the zone** — `INSIDE`, `OVERSHOOT_R` (breakout retest), or `UNDERCUT_S` (spring) — not only a clean higher low (Phase 3, gate 6);
- the ascending-support footprint is a **bonus-only** score, never a filter (see "Ascending Support / Higher-Lows Footprint");
- behind the `LPS_HOLDING_SHELF_ENABLED` flag (LIVE since 2026-07-16), a **second sanctioned completion form** — the flat holding shelf resting **high** in the structure — joins the pullback-and-rest form. This is the canon's two-form doctrine (Wyckoff: the back-up is "a simple pullback **or a new TR at a higher level**"; [lps_final_structure_canon_2026-07-10.md](lps_final_structure_canon_2026-07-10.md)), judged on geometry only (Phase 3).

**The optional tenant: a mini-consolidation.** Phase D *may* contain a second, tighter mini-consolidation — a natural development when live equilibrium shifts during accumulation and the range re-settles inside the larger process. It is **not** always present. The engine handles the "sometimes" through the `find_inner_box()` brick, which mirrors the shared inner search (`inner_box_at` + `detect_inner_root_swing`; see "Parent + Inner"). The inner box is a *structural fact to recognize*, not a requirement to impose.

**The "V" — a positioning guide, not a detected object.** The right-most action often traces a V: a final dip / shakeout / spring down into support, then a turn back up. The V is a guide for *where the trader wants to stand*:

- **before the tip** (still descending into the dip) = wrong place, wrong time — the low isn't in;
- **after the tip** (turned up off the low, demand returning) = the shakeout is done and we are walking toward launch.

The LPS *is* that turn — the last support after the reaction. The engine leans this way structurally: the active setup LPS is terminal-bar based and must sit below its trigger (Phase 3, gate 14), so a qualifying setup is biased toward the up-leg rather than a knife still falling.

**The comprehension this encodes.** Read top-to-bottom, Phase D is the bridge from *"a consolidation exists"* to *"I understand I'm in the right-most region, past the shakeout — now localize the LPS zone."* That region is resolved by `resolve_phase_d_boundary()` ([engine_alpha/structure/phase_d.py](../engine_alpha/structure/phase_d.py)) and surfaced through the narrative reader, `measure_phases()`, and `scope_consolidation()` ([engine_alpha/structure/scope.py](../engine_alpha/structure/scope.py)). It is strictly **measurement/evidence**, never a gate: it cannot drop a ticker, change R/S, or directly alter score/tier. The mandatory gate remains the active LPS itself.

The scoping layer emits best-effort chart anchors:

- **Phase A:** local root climax / automatic-reaction lead-in, from the resolved consolidation-specific climax to the reaction bar.
- **Phase B:** the whole working base / cause-building region from `phase_b_start_bar` through the setup end. In the chart validation view, Phase D is an overlapping right-side read, not a cutoff that truncates Phase B.
- **Phase D:** the right-most launch region. A true Phase-C spring recovery floors the Phase-D search; it is not itself the boundary source. Phase D starts at the earliest credible right-side evidence at/after that floor: support-test cluster, SOS reclaim, rising support, inner mini-consolidation, or recovered V-tip. If none is present, the LPS window is the mandatory fallback.
- **Phase C:** optional measured spring event in Bin B. A `SPRING` is a late Low undercut below S that stays near the box, then recovers by Close back above S within the configured recovery window. Ordinary held support tests remain part of the LPS/support-test layer, not a forced Phase C. Most bases have no Phase C and that is normal. **`TERMINAL_SHAKEOUT` (`BAND_RAILS_ENABLED`, live since 2026-07-16)** — when the calibrated detector finds nothing (its depth/linger caps are breakdown defenses and stay untouched), the box's own qualified DEEP excursion (rail_qualification: penetration → reclaim → hold, multi-bar, beyond S − 2×buffer) is typed as the Phase C at terminal-shakeout scale — the operator's BODI ruling ("the collapse is Phase C inside one box, not a box break"). Fed at the ONE detector seam (`_phase_c_candidate`), so `find_spring`, `measure_phases`, the chart's C label and the archive can never drift; a calibrated `SPRING` is never re-typed.
- **LPS zone:** a tight price-and-time box around the exact LPS candidate bars (`lps_zone_low/high` plus `lps_zone_start/end_date`), not a level stretched across all of Phase D.

All boundaries are nullable. If the engine cannot place a region confidently, it emits `None` and the frontend skips that label/box. Young bases may yield only a base body and a right edge; the model must never force four tidy quadrants.

---

## Phase 3 — LPS Detection

`detect_lps()` ([engine_alpha/structure/lps.py](../engine_alpha/structure/lps.py)). For each `(offset, length)` window in the recent tape, every hard gate below must pass; failing any hard gate disqualifies the window. Candidate swing depth is measured from the first bar's High -- the anchor peak before the pullback -- into the elected LPS valley. Normally that valley is the final bar's Low, and the trigger is the final bar's High. Two shelf patterns are also valid: a compact rising support shelf can elect its early window low as the LPS low, and a long shallow above-R shelf can hold just above old R. Surviving candidates are filtered for actionability (`current_price < trigger`) and the latest valid setup LPS wins.

**The holding-shelf completion form (`LPS_HOLDING_SHELF_ENABLED`, LIVE since 2026-07-16).** The scan carries a second pure completion judgment, `_holding_shelf_verdict` — the two-form doctrine's flat shelf ([lps_final_structure_canon_2026-07-10.md](lps_final_structure_canon_2026-07-10.md)) — consulted only where the pullback form rejects at gate 7 (pullback depth) or gate 11 (volume floor); every other gate binds both forms. A holding shelf is judged on **geometry only**: at least `LPS_SHELF_LENGTH_MIN = 3` bars, **monotone non-rising lows** (the operator's "LPS = peak that goes down"; a rising low is the canon's wedging failure — which also means the terminal-low guard passes by construction), its low at/above the **box midpoint** (`LPS_SHELF_MIN_LOW_POS_BOX = 0.5` — the canon position test: flat finals are sanctioned only high in the structure; flat-and-low is the named failure geometry), and a dig inside the base depth envelope `[0.40, 4.50]` without the OVERSHOOT_R escalation. A shelf-saved window carries `swing_type = "holding_shelf"` and a **volume-free quality**; volume is measured truthfully (`vol_contraction` may archive negative) but never gates or rewards this form. Flag-off the judgment is never consulted — byte-identity is structural. Calibrated on the operator's marked WTS + PBT shelves (flag-ON: both convert, all pinned corpus hits and all 32 shadow fires unchanged, negative corpus clean). The shelf-length floor STAYS at 3: the 3→2 move was attempted 2026-07-17 and reverted at its flip battery — KWR + FLG (labeled dead-space) both fired via 2-bar shelves; at n=2 the monotone axis is one comparison and does not discriminate.

**The final method, build step 2 (Sun 13/09/2026): the ruled stack behind flags, DARK.** Eight default-off flags carry the operator's rulings R1 and R7 to R18 exactly as they were measured in process (rulings ledger, `rulings_ab2` to `ab8`), one flag per ruling site so each can be measured alone (six of them flip only together with the stack and step 12); every name rides the engine manifest. Flag-off every path is byte-identical (the fleet, junk, marks and reader-pin guards prove it); flag-on mechanics are pinned on fakes in `tests/test_final_method_step2.py`. Inside this detector: `LPS_RANGES_YARDSTICK_ENABLED` (R8 + R12) reads the window height (`LPS_WINDOW_SPAN_ATR_MAX` 2.5), the launch above R (`LPS_LAUNCH_ABOVE_R_ATR_MAX` 2.5) and the resistance shelf's lift (`LPS_SHELF_ABOVE_R_ATR_MAX` 1.5) in daily ranges instead of box heights, and lifts the zone's R-side ceiling to `LPS_ZONE_CEILING_ATR` 1.35 ranges; `LPS_GRADED_TRAITS_ENABLED` (R9/R9b + R15) turns the terminal-low guard, the markup-leg test, the depth minimum, both spread caps and every volume ask into measured facts (quality becomes volume-free), while the story position stays a refusal (the window's high before its low, a dig of at least `LPS_CORRECTION_DIG_MIN_ATR` 0.70 ranges, the last high at most `LPS_CORRECTION_LAST_HIGH_MAX_ABOVE_FIRST_ATR` 0.25 ranges over the first); `LPS_WINDOW_RECEDING_ENABLED` (R18 + the sixteenth sitting) replaces the 2..7 length enumeration with ONE window per read day, the last run of receding days (a lower high or a lower low than the day before) with the day before the run as its top, ending ON the frame's last receding day, and refuses a window that ends on a breakout day (a close over the prior high by more than `LPS_BREAKOUT_DAY_CLOSE_ABOVE_PRIOR_HIGH_ATR` 0.10 ranges); `LPS_BUY_DAY_READS_HIGH_ENABLED` makes the election's "still live" test read the HIGH: a candidate whose trigger a later day's high crossed was bought and shows nothing (the measure-only staircase keeps every window: since the review of Mon 14/09/2026 the one-window rule is an election rule too, and `detect_lps_tests` enumerates with `staircase=True`, so the Phase D evidence that needs two right-half support tests survives the flip). Outside this detector: `RESPECT_WHOLE_BAR_ENABLED` (R1) counts a bar as outside the box only when the WHOLE bar sits beyond the rail area (`box_gates._respect_stats`); `DWELL_GRADED_ENABLED` (R13) stops the whole occupancy exam from refusing, both end-third dwells, the mid churn and the coverage (`box_gates._validate_base_quality`; the touch legs still refuse; alone it regresses MATX, so it goes live only with the stack); `BOX_HANDOVER_RANGES_ENABLED` (R11) keeps a rescued box only while the last close sits within `BOX_HANDOVER_MAX_ABOVE_R_ATR` 1.5 ranges above its R instead of 15 percent of price (`box_primitives._still_backing_up`); `SPRING_BOUNDS_LIFTED_ENABLED` (R17) lets a spring sit anywhere in the box with its depth bounded by the ATR cap alone (`phase_features._phase_c_candidate`). The measured scoreboard of each flag and of the whole stack is in the decisions record (2026-09-13, build step 2).

**The final method, build step 3 (Sun 13/09/2026): LPS refusals to grades, DARK.** One default-off flag, `LPS_REFUSALS_TO_GRADES_ENABLED` (on the engine manifest), carries his points 18, 19 and 20 of the final method inside `detect_lps_candidates`. 18: the support side of the zone gate is read on WHOLE BARS (his Q18, "not below the support area", and his JAZZ answer, on support "since most of the move is above it"): `_share_below` measures the share of the window's high-to-low travel under a level, more than half under the support area refuses and more than half under S types UNDERCUT_S (an LPS on a spring candidate), so a poke never refuses; the ceiling above R stays (R12). The first build typed the zone by the lowest close and had no floor; the review of Mon 14/09/2026 restored both his words. The tight-box widening leaves only the R-side ceiling, and only together with `LPS_RANGES_YARDSTICK_ENABLED`; `_zone_tolerance` is unchanged (alone, step 3 keeps today's ceiling, which is what admits MRK's above-R LPS). 19: the three post-window checks go (the latest close under `LPS_HOLD_TOLERANCE` of the LPS low, the post-window low test, the post-window spread test; under one window per read day there is no post-window day to check), and `_depth_in_base_envelope` drops the `LPS_PULLBACK_PROFILE_MAX` cap (with `LPS_RANGES_YARDSTICK_ENABLED` the window height in ranges is the one "too deep" refusal left, without it the 0.85 box-height cap still refuses; a NaN dig still refuses). 20: volume never refuses (the `volume baseline invalid`, `volume not drying up` and `pullback volume above baseline` refusals stop) and never elects (quality is volume-free; `vol_contraction` stays a fact on the card). Flag-off every path is byte-identical (the fleet, junk, marks and reader-pin guards PASS unchanged); flag-on mechanics are pinned on fakes in `tests/test_final_method_step3.py`, every branch mutation-proved. The scoreboard (alone, with the step-2 stack, with everything) is in the decisions record (2026-09-13, build step 3).

**The final method, build step 4 (Sun 13/09/2026): the ONE turn line, DARK.** `engine_alpha/structure/pivots.py` grows the operator's line as a pure primitive: `turn_line(highs, lows, floors)` walks the whole frame and commits a turn on the bar where price backs off the running extreme by that bar's floor, wick to wick, with no retracement ratio; the confirming bar carries the next leg's extreme, so a bar whose own range covers the floor holds both a peak and a valley; bar 0 is a turn by its shape and the terminal running extreme rides as a FORMING turn, so the line has neither the order-1 walk's edge mask nor the five-day right-edge reserve. Each turn carries its own `knowable_bar` — the causality contract's commit stamp, which the line knows by construction rather than reconstructing. `turn_line_floors(df, atr_val)` builds the per-bar floor: `TURN_LINE_FLOOR_ATR` (0.75) of each bar's OWN `ATR_10`, falling back to the caller's one scalar range where the frame carries no range column; the per-bar unit is what lands the line on all 186 of his named turns (one range from the read day lands 183). `turn_line_views(turns, start)` splits the line at the box-start seam and is the ONLY way it reaches the staircase: rebuilding it through `_build_zigzag` inverts a bar that carries both turns and the same-type merge then eats its neighbours, so `box_events._staircase_from_pivots` grew one `swings=` keyword that LABELS a finished alternating list instead (every other caller passes nothing and is byte-identical). Two default-off flags carry it, one per site: `TURN_LINE_ENABLED` under `event_map.read_swing_map`, `TURN_LINE_TREND_ENABLED` under `market_structure.read_market_structure`. Both readers take a `line=` pin (None follows the flag): since the review of Mon 14/09/2026 the live cause veto's Operand B (`bricks.cause_maturity`) and the Phase A climax repair (`trend_terminal_floor`) pass False and keep today's skeleton until build step 10, and the line opens on the older running extreme when its first leg covers the floor (bar 0 only when bar 0 is that extreme). The recall of his 186 turns is density more than agreement (his day moved three trading days still lands 173 of 186), so the floor stays his measured number, not a proven optimum. The box election is deliberately NOT a site — it stays on today's skeleton until build step 10. Flag-off every path is byte-identical (the fleet, junk, marks and reader-pin guards PASS unchanged, and the event map's own byte-identity battery is untouched); flag-on, the measured result is that no fire moves anywhere and the reader pin's only drift is the commit stamps. The scoreboard is in the decisions record (2026-09-14, build step 4).

**The final method, build step 5 (Mon 14/09/2026): the words on the line, DARK.** `engine_alpha/structure/line_words.py` is a measure-only reader over the step-4 line. `read_line_words(df, box, unit, lps=, inner=)` builds the line over the whole frame (whatever `TURN_LINE_ENABLED` says) and returns every word as a pure function of it: `thrusts` (a clean up-leg walked back through pauses smaller than a last supper's dig, `LINE_WORD_SUPPER_DIG_ATR` 1.5 ranges; ground at least `LINE_WORD_SOS_MIN_GROUND_ATR` 1.70; its top in the R area, `LINE_WORD_AREA_ATR` 0.5, or over the swing high before the push began), `pick_the_sos` (the last thrust topping at or before the LPS low, launched after the Phase C tip), `last_suppers` (hindsight: the deepest low within `LINE_WORD_SUPPER_MAX_DAYS` 4 trading days off a thrust's top, sought only before the LPS window opens), `dips` and `phase_c` (every valley beyond the support area read forward swing by swing: recovered once a peak reaches the support area and the next valley commits higher than the tip, recovering while that valley forms, failed on an equal or lower low; the Phase C is the deepest recovered), `spring_tests` (the first valley back inside the support area after it), `phase_d` (the earliest of the round trip, the staircase after the Phase C, THE SOS's launch, the LPS window's first day) and `mini` (today's elected inner box). Five default-off flags, one per word, only choose what `emitted` lets out: the evaluation's score context reads the words only when a flag is on and spreads ONE key, `_line_words_json` (a compact JSON string), onto the result; no archive writer, wire key, tag or grade reads it, and with every flag off the hook reads five settings and computes nothing. `tools/word_recall.py` is the committed measuring stick (read-only on the marks DB; his rails fed his drawn LPS windows, and the engine's own election on his fire day; the exact day, one trading day and a shifted-day chance beside every rate). The scoreboard is in the decisions record (2026-09-14, build step 5).

`offset` = bars between the LPS evaluation bar and "today" (`offset = 0` means the LPS ends today). `length` = number of bars in the LPS sequence.

| # | Gate | Rule | Setting / source |
|---|------|------|------------------|
| 1 | **Recency** | `offset` in the last 7 active LPS bars | `LPS_SCAN_OFFSET_MAX = 7` |
| 2 | **Length** | `LPS_LENGTH_MIN ≤ length ≤ LPS_LENGTH_MAX` | 2 to 7 bars |
| 3 | **Window bound** | `offset + length ≤ base_len + AR_MAX_BARS` | redundant outer guard; never lets the LPS pre-date the box |
| 4 | **Swing-complete** | `eval_idx > swing_complete_idx` where `swing_complete_idx = (len(df) - base_len) + max(r_anchor, s_anchor)` | LPS must sit *after* the swing pivots that defined R and S |
| 4b | **Chronology floor** (only when the caller passes one) | `start >= start_floor_bar`. The narrative walk passes the elected **spring's tip** (`LPS_AFTER_SPRING_ENABLED`, live from birth 2026-08-09 — cause before effect, Phase C → D): the LPS may not OPEN left of the spring that conducts the turn; opening ON the tip is legal (the undercut-rebound form rests on the spring low). No floor → no behavior change; the measure-only staircase (`detect_lps_tests`) never passes one. Repairs the KYMR C6 violation (a triggered post-spring LPS let the elector reach back to a pre-spring window whose support had already broken); a spring story whose only LPS predates the tip is refused with trace outcome `lps_before_spring` — a doctrinal non-election the doctrine gate reads like `cause_absent`. Fleet census 2026-08-09 (256 payload setups, 69 with springs): `lps.start − spring.tip` min +2 / median +21 on the 68 legal reads — KYMR at −8 was the sole violator, 10 bars clear of the nearest legal read, so the floor clips no sanctioned form. | `LPS_AFTER_SPRING_ENABLED = True`; `start_floor_bar` (detector arg) |
| 5 | **Pullback shape (graded)** | `descent_frac >= LPS_MIN_DESCENT_FRAC` and `high_descent_frac >= LPS_MIN_HIGH_DESCENT_FRAC`; both are pair-wise non-rising fractions over lows/highs. A fully clean downswing may span more vertical box range because it is one peak-to-valley swing, not broad chop. | shape gates + quality multipliers |
| 6 | **Zone gate** | elected LPS low lands in one of three buffered zones. Normally this is the last-bar `Low`; for a compact rising support shelf it can be the early window low. **`S`/`R` below are the rails of the box this call was given** — the narrative elects inner-first-then-parent (`find_lps(df, inner, …)` before `find_lps(df, box, …)`), so an inner-elected LPS is typed against the INNER rails. `Structure.R/S` publish the PARENT's either way, so `lps.zone_type` and `Structure.R` are **not** comparable when `lps_in_inner` — read `Structure.inner.R` there. See the theory statement in [strategy_alpha.md](strategy_alpha.md) ("Which R is 'the old resistance'?"). | `LPS_ZONE_ATR_MULT = 0.5` |
|   | • INSIDE | `S ≤ low ≤ R` → setup `LPS` | |
|   | • OVERSHOOT_R | `R < low ≤ R + 0.5·ATR` → setup `LPS` (backtest of breakout) | |
|   | • UNDERCUT_S | `S - 0.5·ATR ≤ low < S` → setup `REBOUND` (spring) | |
| 6b | **Launch gate (INSIDE only)** | an INSIDE window whose high extension above R exceeds BOTH caps (`> 0.35 × box_height` AND `> 0.75 × ATR`) is refused as "window launched above resistance" — a late/off-structure pullback, not LPS-above-R behavior. **The ceiling-rest exception (`LPS_CEILING_REST_ENABLED`, dark — operator ruling 2026-08-29, NOK):** the straddle passes when the REST lands ON the ceiling, `support_low ≥ R − LPS_CEILING_REST_MAX_BELOW_R_ATR (0.3) × ATR` — the launch above R is then the preceding advance's own top giving back to the rail (the drawn corpus's most common terminal form). The 0.3 bar is drawn-evidence-placed (DSGN 0.010 / MATX 0.087 / MSGS 0.148 / NOK 0.241 vs junk ENIC's 0.314 — a stated razor, pinned by the negative-corpus flag-on leg). A launch-above window resting deeper stays refused. Fail-closed on a bad ATR; flag off = byte-identical | `LPS_INSIDE_HIGH_EXTENSION_BOX_MAX`, `LPS_INSIDE_HIGH_EXTENSION_ATR_MAX`, `LPS_CEILING_REST_*` |
| 7 | **Pullback depth (profile-normalized)** | `pullback_profile = (first_high - elected_low) / profile_unit`, where `profile_unit = max(base_range_threshold, 0.15 × box_height)`. INSIDE/UNDERCUT_S need `>= 0.40`; ordinary OVERSHOOT_R needs `>= 1.25`; a long shallow above-R shelf may use the normal `0.40` floor when price is still sitting low on R. All zones cap at `<= 4.50`. Flag-on, a window failing this gate may still complete as a **holding shelf** (see above) | `LPS_PROFILE_BOX_FRACTION_FLOOR`, `LPS_PULLBACK_PROFILE_*` |
| 8 | **Terminal-low guard** | last-bar `Low` must be within `0.10 × profile_unit` of the lowest Low in the candidate window, except for a compact multi-bar rising support shelf whose early low remains inside the support side of the box. That shelf rescue is itself rejected as a markup leg when its net advance `(last Close − first Close) / box_height > LPS_RESCUE_MAX_ADVANCE_BOX` — a genuine ascending-support coil is gradual, not a steep launch off support (OHI-class). | `LPS_TERMINAL_LOW_TOL_PROFILE = 0.10`, `LPS_RESCUE_MAX_ADVANCE_BOX = 0.21` |
| 9 | **Spread (core)** | every LPS bar's `Spread (High - Low)` must be `<= profile_unit × 1.25`; the final bar may widen over the prior bar by at most `0.35 × profile_unit` | `LPS_SPREAD_MAX_PROFILE_MULT`, `LPS_SPREAD_EXPANSION_MAX_PROFILE` |
| 10 | **Declining spread quality** | last bar spread narrower than the prior bar earns full quality; widening inside the allowed expansion cap is discounted against `profile_unit` but does not reject by itself | `LPS_SPREAD_MUST_DECLINE = True` |
| 11 | **Volume floor** | `mean(Volume[LPS]) < Vol_50[eval_idx] × 0.87`. The dry-up is the **pullback form's** judgment: a holding shelf may complete without it (volume never gates the shelf form). Moved 0.85→0.87 on 2026-07-17 against the archive (1,679 matured episodes: outcome quality flat up to the old edge, no cliff; converts AGCO); 0.88+ stays pinned rejected. A non-finite `Vol_50` refuses BOTH forms (data-integrity guard, same change) | `LPS_VOL_CONTRACTION_MAX = 0.87` |
| 12 | **Hold tolerance** | `latest['Close'] >= elected_low × 0.95` | `LPS_HOLD_TOLERANCE = 0.95` |
| 13 | **Post-LPS continuation** (only when `offset > 0`) | every bar between LPS end and current bar must hold `Low >= elected_low × 0.95` and stay profile-tight | catches support-test failures that widen after the LPS |
| 14 | **Trigger room** | candidate is actionable only when `current_price < trigger_price`; `_evaluate_ticker` keeps the same final room check | trigger = last LPS bar High |

**Setup label:** `REBOUND` if zone is `UNDERCUT_S`; otherwise `LPS`.

**Quality ranking:** pullback candidates carry `vol_contraction × (1 - tightness_ratio) × descent_frac × high_descent_frac × spread_decline_quality`; a shelf-saved candidate carries the same product **without the volume term**. Setup election is actionability-first and recency-first: latest valid `end_index`, then latest `low_index`, then (flag-on) the pullback form before the shelf form on an integer rank, then longer length, then quality — so float quality is only ever compared *within* a form. If several clean slices of the same form share the same final low, the detector reports the longest clean pullback.

> **Note on breakouts.** Despite the historical name "VCP/breakout screener," the live `detect_lps()` path is the only signal generator. A genuine breakout setup type isn't emitted from the engine right now, so the old `BREAKOUT_*` settings were removed rather than kept as false knobs.

---

## Phase 4 — Scoring & Tier Assignment

`score_setup()` ([engine_alpha/scoring/scoring.py](../engine_alpha/scoring/scoring.py)) sums **15 components**, each clamped into `[0, cap]` (box tightness is first scaled by the live candle-spread readability multiplier — a `[floor, 1]` grade, never additive).

> **Since the 2026-08-09 flip this raw sum is no longer the number the operator reads.** `compose_ta_grade()` normalizes the same terms — plus the promoted story terms — against a FIXED divisor into the **0-100 TA grade**, partitions it into the story chapters, applies the floored warning discounts, and derives the tier from the result. **The legacy path RETIRED 2026-08-23** (operator-delegated; council 2026-08-22): `calculate_tier`, the `TIER_S/A/B/C` cuts and the `TA_SCORE_V2` flag are gone (a declared manifest seam), the **scan ranking is the grade** (raw-sum tiebreak, then ticker — council P1: rank and badge must come from ONE verdict), and the seed scan-back election keys on the same basis. The raw sum survives ONLY as the archived `score` fact and the ranking tiebreak — writers keep stamping it (NOT NULL contract, computationally free), no surface displays it. See [ta_grade_flip_2026-08-09.md](ta_grade_flip_2026-08-09.md) for the flip's basis and measured drift.

> **The chapters are three since the 2026-08-12 re-partition: Consolidation → Phase D → Trend** (`taxonomy.CHAPTER_ORDER`). `cause` and `phase_b` were fused into `consolidation` — they graded one object from two sides — and `phase_c` was retired as a chapter on the operator's ruling that a spring is *marked, not graded*. Two mechanical consequences worth knowing at the point of use:
>
> - **`ascending_support` moved to `consolidation`, it was not demoted.** It grades the whole base's valley lows stair-stepping up (`measure_support_slope` over the box), never the shakeout; it sat under `phase_c` only because that chapter's blurb mentioned "the rising support", and it was the *only* reason a Phase C column ever showed points. Its 8-point cap is untouched.
> - **`spring` left the `ta` layer for a third layer, `marker`.** A marker term is measured, archived (`score_spring`) and drawn, and is excluded from `ta_layer_terms()` — so it cannot reach a chapter, the divisor, or the tier even if its cap were raised. This is the ruling encoded as arithmetic rather than as a comment; `tests/test_score_taxonomy.py::test_a_marker_event_is_found_and_never_graded` is the gate.
>
> **The grade itself did not move**: same terms, same caps, same fixed divisor of 171 (spring's cap was already 0). Only the partition changed — plus `engine_config_version`, which rotates because chapter membership is hashed engine identity.

| Component | Formula | Cap (setting) |
|-----------|---------|---------------|
| **Box tightness** | When `TIGHTNESS_ADR_AWARE` (live): `((MAX_BOX_WIDTH_ADR - box_width_adr) / MAX_BOX_WIDTH_ADR) × 22`, where `box_width_adr = box_width·100 / ADR%` measures the range in the stock's OWN daily ranges (a flat low-ADR drift no longer reads as a coil; `corr(box_tightness, ADR) = −0.73` before the rebase). Flag-off / zero-ADR fallback: the absolute `((MAX_BOX_WIDTH - box_width) / MAX_BOX_WIDTH) × 22`. Then scaled by the always-on candle-spread readability grade `∈ [floor, 1]` (folded 2026-07-18; formerly flag `CANDLE_SPREAD_AWARE`). The absolute `MAX_BOX_WIDTH` validity gate upstream is unchanged — this only re-bases the score. | `SCORE_BOX_TIGHTNESS = 22`, `TIGHTNESS_ADR_AWARE`, `MAX_BOX_WIDTH_ADR = 4.5`, `CANDLE_SPREAD_*` |
| **Touch density** | `min(touches × 2, 15)` plus `+10` if `r_touches ≥ 3 AND s_touches ≥ 3` OR `total ≥ 6` | `SCORE_TOUCH_DENSITY = 25` (15 base + 10 bonus); `TOUCH_BONUS_INDIVIDUAL = 3`, `TOUCH_BONUS_TOTAL = 6`, `TOUCH_BONUS_POINTS = 10` |
| **Traversal quality** | `clamp((density / 0.33) × 10, 10) − clamp((dwell_asymmetry + max(0, max_swing_frac − 1)) × 8, 8)`, floored at 0, where `density = n_full_traversals / n_swings`. Rewards a box whose swing limbs genuinely run rail-to-rail; docks dead-space framings that hang off one rail (`dwell_asymmetry`) or anchor a rail on a one-off spike (`max_swing_frac > 1`). The overshoot term is zeroed for a tight box (`box_width ≤ BASE_AGE_DEADSPACE_WIDTH`) or a confirmed spring (`has_spring`) — there an oversized limb is inevitable (any real swing dwarfs a tiny range, e.g. PRA) or a bullish undercut, not dead space; the `dwell_asymmetry` dock still applies. Replaced the rail-blind **oscillation** term (which a one-sided top-hug maxed just like a true two-sided box). | `SCORE_TRAVERSAL_QUALITY = 10`, `TRAVERSAL_QUALITY_DENSITY_FULL = 0.33`, `TRAVERSAL_QUALITY_DWELL_PENALTY = 8` |
| **ATR squeeze** | `(1 - ATR_10/ATR_50 at bar -6) × 8` | `SCORE_ATR_SQUEEZE = 8` |
| **LPS tightness** | `(1 - tightness_ratio) × (20 × 2)` | `SCORE_LPS_TIGHTNESS = 20` |
| **Volume contraction** | `vol_contraction × (20 × 2)` | `SCORE_VOL_CONTRACTION = 20` |
| **Base age** (only if `base_len > MIN_BASE_DAYS`) | `sqrt(base_len / BASE_AGE_CAP_DAYS) × 22`. Hits ~50% at 30d, ~71% at 60d, 100% at 120d. **Dead-space dock:** a WIDE base (`box_width > BASE_AGE_DEADSPACE_WIDTH`) that did not work rail-to-rail (`traversal_density < TRAVERSAL_QUALITY_DENSITY_FULL`) scales its age credit by the achieved density fraction (`traversal_density / TRAVERSAL_QUALITY_DENSITY_FULL`, capped at 1) — long "cause" only counts if the base actually traversed; tight boxes are exempt. | `SCORE_BASE_AGE = 22`, `BASE_AGE_CAP_DAYS = 120`, `BASE_AGE_DEADSPACE_WIDTH = 0.06` |
| **Strong-uptrend bonus** — **DEMOTED to measure-only (weight 0) 2026-07-25, operator-authorized** | Was a linear ramp (`0` below 30% YoY return, full at 60%+). Both edge reads graded the archived sub-score HARMFUL (corr −0.19 with forward returns at n=1977, `docs/edge_read_2026-07-22.md`): momentum context was hurting the ranking. The ramp still computes (weight 0 → 0 points) and the RAW input is now archived (`yearly_return` column, model-only) so a regime-spanning revisit can re-open the question with evidence. | `SCORE_UPTREND_BONUS = 0` (was 15), `MIN_STRONG_YEARLY_RETURN = 0.30`, `MAX_STRONG_YEARLY_RETURN = 0.60` |
| **Soft RS bonus** — **DEMOTED to measure-only (weight 0) 2026-07-25, operator-authorized** | Was `min(1, excess_return_6m / 0.30) × 15`. The worst term in the book on both edge reads (corr −0.22 at n=1977). Raw signal stays archived (`excess_return_6m`). | `SCORE_RS_BONUS = 0` (was 15), `RS_LOOKBACK_BARS = 126`, `RS_MAX_EXCESS_RETURN = 0.30` |
| **52w-high proximity** | Linear ramp from `0` at −20% below 52w high to full at −5% (or higher). Bases that consolidate near recent highs hold their breakouts more reliably than ones rebuilding from deep drawdowns. | `SCORE_52W_HIGH_PROXIMITY = 8`, `HIGH_PROXIMITY_FULL_PCT = -0.05`, `HIGH_PROXIMITY_ZERO_PCT = -0.20` |
| **Market-breadth bonus** | Linear ramp on % of universe with `Close > SMA_50`. Zero below 35%, full at 60%+. Same value for every setup in a run (it's a market-wide scalar), but a strong-tape setup is structurally a better trade than the same chart in a defensive regime where most stocks are under their SMA_50. | `SCORE_BREADTH_BONUS = 8`, `BREADTH_FULL_PCT = 0.60`, `BREADTH_ZERO_PCT = 0.35` |
| **VCP contraction** | `contraction_quality × 12`, where quality ∈ [0,1] from `measure_contractions()` (see below) = `0.40·count + 0.35·progressive_tightening + 0.25·final_tightness`. Captures the Minervini VCP *process* (each pullback tighter than the last), distinct from box-tightness/ATR-squeeze which only see *static* tightness. | `SCORE_CONTRACTION = 12`, `CONTRACTION_IDEAL_MIN/MAX = 2/6`, `CONTRACTION_FINAL_TIGHT_PCT = 0.03`, `CONTRACTION_FINAL_LOOSE_PCT = 0.12` |
| **Ascending support** | `support_quality × 8`, where quality ∈ [0,1] from `measure_support_slope()` (see below) = `0.6·slope_score + 0.4·higher_low_frac`. Rewards a base whose swing lows stair-step *up* (rising support / tennis-ball action). Bonus-only — a flat or sagging floor earns 0, never penalized. | `SCORE_ASCENDING_SUPPORT = 8`, `ASCENDING_SUPPORT_FULL_SLOPE = 0.10` |
| **ADR% absolute volatility** | `adr_quality × 8`, where `adr_quality = min(ADR% / 5.0, 1.0)`. Rewards Qullamaggie-style volatile movers: stocks that travel enough each day to be worth trading. Bonus-only — low-ADR names earn 0, never a penalty. | `SCORE_ADR = 8`, `ADR_WINDOW = 20`, `ADR_FULL_PCT = 5.0` |
| **Setup quality** (E3, live; renamed from *puzzle quality* 2026-08-09, operator ruling) | `setup_quality × 8` — the L2 assembled-Wyckoff-story completeness/chronology grade from `assemble_box_narrative()` (see [The L2 event reader](#the-l2-event-reader--wyckoff-story-from-rail-events-to-a-scored-narrative)). Additive, bonus-only, clamped `[0, cap]`; grades-not-vetoes (≥ 0, can only raise a score). | `SCORE_SETUP_QUALITY = 8`, `PUZZLE_SCORE_ENABLED` (folded 2026-07-18) |

**Tier mapping — LIVE ladder (`calculate_structure_tier()`, flipped 2026-08-09).** The tier's SOURCE is the 0-100 **TA grade**, not the raw component sum. Resolved once inside `compose_ta_grade()` and carried as `structure_tier`, so the wire, the archive and the lens cannot disagree about the letter.

| Tier | Threshold | Setting |
|------|-----------|---------|
| **S** | `ta_grade ≥ 62` | `TIER_S_STRUCT = 62` |
| **A** | `ta_grade ≥ 52` | `TIER_A_STRUCT = 52` |
| **B** | `ta_grade ≥ 42` | `TIER_B_STRUCT = 42` |
| **C** | `ta_grade ≥ 32` | `TIER_C_STRUCT = 32` |
| **D** | else | — |

Operator-chosen from the A/B on the 2026-08-09 scan (256 fires, grades 35.5–76.3, median 59.0), which reads S=85 / A=118 / B=41 / C+D=12 under this ladder. The count-preserving alternative (61.5) was rejected as a knife edge — it sat 0.19 points above the next grade. Evidence: [ta_grade_flip_2026-08-09.md](ta_grade_flip_2026-08-09.md).

> **S-tier width cap — unchanged by the re-base.** A base wider than `S_MAX_BOX_WIDTH = 0.15` cannot be S no matter how high it grades; it takes A on merit. This is the operator's own rule ("wide … getting an S, this is bad") and it applies on top of whichever ladder is live. On the flip A/B it held **22 of 111** A-tier names out of S on width alone — AAP among them, the 4th-highest grade on the scan at 0.151 box width against the 0.15 cap.

**Legacy ladder — RETIRED 2026-08-23.** `calculate_tier()` over the raw sum (cuts 110/95/75/55) served the `TA_SCORE_V2`-off path from the 2026-08-09 flip until the retirement; the council's P1 found its rollback had silently stopped being faithful (the frontend cap mirror fired the demoted RS/Uptrend chips on every legacy-epoch row), which removed the last reason to keep it. `_apply_tier_ladder` survives as the one ladder shape under `calculate_structure_tier`. Resurrection is one git command away (checklist §2 records the executed wave).

---

## VCP Progressive-Contraction Footprint

`measure_contractions()` ([engine_alpha/structure/metrics.py](../engine_alpha/structure/metrics.py)) measures the **defining Minervini VCP signature** — a sequence of 2–6 pullbacks each tighter than the last (e.g. 18%→12%→6%) ending in a tight final coil. This is the *process* of tightening, which `box_width` / `atr_squeeze` (static tightness) cannot see.

It reuses the Phase B zigzag machinery over the base window: each peak→valley downswing is one contraction, `depth = (peak − valley) / peak`. The initial BC→AR descent into the base is excluded by design (it's the entry into the base, the early-chop the `cand_start` trim already removes).

`quality ∈ [0,1] = 0.40·count_score + 0.35·progressive + 0.25·final_tight`:
- **count_score** — full credit for 2–6 contractions (Minervini's range, 3–4 typical); partial for 1 or for an over-count (choppy, not a clean coil).
- **progressive** — fraction of consecutive contractions that don't widen (5% tolerance); 1.0 = textbook monotonic tightening.
- **final_tight** — ramp on the rightmost contraction depth: full ≤ 3%, zero ≥ 12%.

**Volume across the contractions (`vol_trend`).** In the same pass, the mean volume of each contraction's bars is captured and scored into `vol_trend ∈ [0,1] = 0.5·progressive_decline + 0.5·final_is_lightest` (`None` with < 2 contractions) — the Minervini nuance that volume should dry up step by step, lightest at the final coil. This is **measured only**: it is deliberately NOT folded into `quality`, so the contraction sub-score, the tiers, and the VCP-Coil tag are byte-for-byte unchanged (verified against the shadow-output guard). Archived raw as `contraction_vol_trend` to validate against forward returns before it is allowed to matter (or to surface on the tag).

Persisted to the archive as `contraction_count`, `contraction_quality`, `final_contraction_depth`, `contraction_vol_trend`, and the `score_contraction` sub-score. The frontend 🌀 **VCP Coil** tag chip currently fires when `score_contraction` reaches 80% of its sub-score cap. Scored, not gated — measure-first, like the touch-volume signature.

---

## Base Bar Compression Footprint

`measure_bar_compression()` ([engine_alpha/structure/metrics.py](../engine_alpha/structure/metrics.py)) measures the **texture inside the detected box**: whether the bars themselves are quiet / low-spread, not just whether R/S are close together. This is distinct from `box_width` (range tightness) and `atr_ratio` (ATR squeeze) because a narrow box can still contain sloppy wide bars.

It reports four raw diagnostics, all persisted to the archive and not scored:

| Field | Meaning |
|-------|---------|
| `base_median_spread_atr` | median base bar spread divided by the ATR snapshot used by the LPS detector |
| `base_p80_spread_atr` | 80th percentile base bar spread divided by that ATR snapshot |
| `base_median_spread_pct_box` | median base bar spread divided by box height (`R - S`) |
| `base_tight_bar_pct` | share of base bars whose spread is no wider than the ATR snapshot |

This is **measure-first / never-gated / never-penalizing**. It gives the archive a direct way to test whether visually quiet bases outperform choppier bases with similar box width.

---

## Ascending Support / Higher-Lows Footprint

`measure_support_slope()` ([engine_alpha/structure/metrics.py](../engine_alpha/structure/metrics.py)) measures whether the base's swing lows are **stair-stepping up** — the Minervini "tennis-ball action" / Qullamaggie "higher lows surfing the rising EMA" footprint. A flat box with a *rising floor* is a stronger coil than a flat box with a flat/sagging floor: demand is getting more aggressive into each pullback.

It reuses the same Phase B zigzag as the contraction metric, but reads the **valley** sequence. It fits a least-squares line through the `(bar_index, valley_low)` points and ATR-normalizes the slope so it's comparable across price levels and tickers.

`quality ∈ [0,1] = 0.6·slope_score + 0.4·higher_low_frac`:
- **slope_score** — linear ramp of the ATR-normalized slope from 0 (flat/descending → 0) to `ASCENDING_SUPPORT_FULL_SLOPE` (0.10 ATR/bar → 1.0).
- **higher_low_frac** — fraction of consecutive valley pairs that actually step up (consistency of the higher-lows).

Needs ≥ 2 zigzag valleys; otherwise returns neutral (quality 0). Persisted as `support_slope_atr`, `ascending_support_quality`, and the `score_ascending_support` sub-score. The frontend 📈 **Ascending Support** tag chip currently fires when `score_ascending_support` reaches 80% of its sub-score cap. **Bonus-only / measure-first** — a flat or descending fitted slope zeroes the slope component, but the higher-low fraction can still earn partial credit (its 0.4 share of quality); nothing is ever penalized.

---

## ADR% Absolute Volatility

`adr_pct()` ([engine_alpha/structure/indicators.py](../engine_alpha/structure/indicators.py)) measures Qullamaggie-style Average Daily Range % over the latest full tape, not just the consolidation window:

```
ADR%(20) = 100 × (mean(High / Low over the last 20 bars) - 1)
```

This captures the stock's **absolute volatility character**: a high-ADR stock resting in a tight base is a stronger momentum-continuation candidate than a low-range stock with the same visual structure. The metric is guarded at source: insufficient history, zero lows, NaN/Inf, or malformed ranges return `0.0`, so the dashboard payload never receives non-finite values from ADR.

Scoring uses `adr_quality = min(ADR% / ADR_FULL_PCT, 1.0)`, with full credit at `ADR_FULL_PCT = 5.0`. Persisted as `adr_pct` and the `score_adr` sub-score. The frontend ⚡ **High ADR** tag chip currently fires when `score_adr` reaches 80% of its sub-score cap. **Bonus-only / measure-first** — quiet names earn 0 points and are never filtered or penalized.

---

## Volume Signature Around Touches

After the consolidation passes, `_evaluate_ticker` computes two diagnostic z-scores using the base's own volume distribution as baseline:

```
touch_band = TOUCH_TOLERANCE_ATR × ATR_10
r_touch_vol_z = (mean_vol_at_R_touches − mean_base_vol) / std_base_vol
s_touch_vol_z = (mean_vol_at_S_touches − mean_base_vol) / std_base_vol
```

These don't gate anything — they're persisted to the archive (`r_touch_vol_z`, `s_touch_vol_z`) and surface as Wyckoff-classic interpretation tags on the frontend card. Those chip thresholds live in `webapp/frontend/src/components/setupTagsData.js`, not Python settings:

| z-score signature | Tag chip | Meaning |
|---|---|---|
| `r_touch_vol_z < -0.30` | 🤫 No Supply | Resistance tested on below-average volume — buyers absorbed silently, textbook precursor to a clean breakout |
| `s_touch_vol_z > +0.30` | 💪 Demand at S | Support tested on above-average volume — buyers stepping in at S, selling absorbed. **Not a spring** — a spring is the measured Phase C undercut-and-recover event (`bin_c_type = SPRING`), and an active undercut LPS still shows as `REBOUND`. |
| `r_touch_vol_z > +0.50` | ⚠️ Heavy Resistance | Resistance tested on ABOVE-average volume — supply hitting the bid every time, distribution-flavored, breakout risk |

The "Heavy Resistance" tag is the only *warning* tag in the system — designed to surface even when other positive tags would otherwise crowd it out (it carries higher `weight` in the tag-ordering than even Phase D).

These are bookkeeping (not score gates) intentionally: the volume signature at touches is a real Wyckoff axis but its predictive power needs to be measured in the archive before we make it a hard gate or a score component. Phase 2 archive analysis will tell us which thresholds actually matter and at what magnitude.

---

## Region (Bin) Features & Trend Template (Stage 2A)

Two measure-only layers. Both are **descriptive, never scored and never gated** —
every value is an underscore-prefixed result field persisted to the archive
(nullable, backward-compatible) so a later calibration pass can test whether any
of it predicts forward returns. Scoring (15 components, max ~209) and the tier
thresholds are **unchanged**.

### Bin features — "where am I in the base?"

`measure_phases()` ([engine_alpha/structure/phase_features.py](../engine_alpha/structure/phase_features.py))
slices an already-detected base into its named regions and reports raw size,
price-range, and volume character per region. It detects nothing new — it
consumes anchors the detector + LPS finder already produced.

| Region | Span | What it is |
|--------|------|------------|
| **A — climax event** | `bc_anchor_bar → phase_a_end_bar` | the BC/SC → AR trend-exhaustion lead-in |
| **B — working base** | the validated box (`base_df`) | the cause-building equilibrium |
| **D — Phase D** | the right-most region | earliest credible right-side evidence after the spring/search floor: support-test cluster, inner mini-consolidation, or recovered V-tip; else the LPS fallback |
| **LPS** | the exact LPS candidate bars | the Last Point of Support itself |

Per region: `_bin_{a,b,d}_bars`, `_bin_{a,b,d}_range_pct` ((maxHigh−minLow)/minLow),
`_bin_{a,b,d}_volume_ratio` (region mean volume ÷ trailing-50 mean). Plus:

- `_bin_lps_bars`, `_lps_position_in_box` ((lps_low − S)/(R − S): 0 = floor, 1 = ceiling);
- `_bin_d_vs_b_range_ratio` / `_bin_d_vs_b_volume_ratio` — is Phase D
  tighter / quieter than the base it sits in? (the VCP "coil into launch" read);
- `_bin_d_support_slope_atr`, `_bin_d_higher_low_frac`,
  `_bin_d_ascending_support_quality`, and
  `_bin_d_vs_b_support_quality_delta` — is the right side stair-stepping higher
  more clearly than the base as a whole?
- `_bin_d_boundary_source` — `support_tests` (a right-side support-test cluster),
  `sos_reclaim`, `rising_support`, `inner_box` (a real detected
  mini-consolidation), `v_tip` (the final recovered late-base low), or `lps`
  (the mandatory gate / fallback). Spring recovery only floors the search; it is
  not itself a boundary source.
- `_phase_d_evidence_json` — serialized evidence detail: floor marks, all
  candidate evidence signals, and the selected source/bar. The frontend overlay
  uses this when present and falls back to `_bin_d_boundary_source` otherwise.

**Phase-D boundary is single-sourced.** The Phase-D start uses the *same* rule
the narrative, bin measurement, and scoping overlay draw — all call
`phase_d.resolve_phase_d_boundary()` through thin wrappers — so the measured
Phase-D bin and the drawn Phase-D band share one resolver. Their FLOOR
policies deliberately differ (the C24 note on the resolver: the bin
measurement floors on SPRING-type recoveries only, scope selects its floor
caller-side), so on a TERMINAL_SHAKEOUT row the two boundaries can
legitimately differ; the no-drift guarantee holds for the ordinary-SPRING
case. Any region the
engine can't place confidently (e.g. no LPS window) is emitted as `None`; young
bases legitimately have fewer regions.

### Last Supper stretch

**What a Last Supper is (operator's definition).** The **final run-up that traps
late buyers before the real pullback** — a last deceptive rally that lures in late
longs, after which price gives back into the *real* pullback and only then resumes.
It is a discrete **event**, can appear **before *or* after an LPS** (Phase D holds
more than one), and setups often break out *after* the Last Supper has run its
course. **Which bars carry the name (ruling 2026-08-28, drawn corpus):** the run-up
is the *anchor*; the event's own span is the **giveback** — the deep, fast seller
reaction that follows it (all 10 drawn `last_supper` marks open on the extension top
and travel down), and the anchoring up-move may be an SOS, the push off an LPS, or
the breakout itself — never SOS-bound. Any future dated detection stamps the
giveback span. The engine does **not** label it as a timed event today — it measures
the over-extension *geometry* around the LPS (below).

**It is NOT a warning (operator ruling 2026-08-26).** *"Last suppers aren't a bad
thing. many stocks popped off after said event because its essentially just a deep
correction."* The tag never cost a point — it is absent from `_ta_grade_warnings` —
but it was grouped warning-side and rendered in the danger tone, which contradicted
this section's own "setups often break out *after* the Last Supper has run its
course" and trained the eye to read a present Last Supper as a defect. It now sits
in the LPS group as a descriptive event chip. What the engine still does NOT do is
label the run-up as a dated event; the operator's ask — *"I want the algorithm to
know it exists as an event"* — is the event-typing program (`event_map` reserves the
column family), not this measurement.

**What the engine measures is the over-extension geometry.** Two raw families say
how exposed *this* entry is to a Last Supper. A precise, well-positioned LPS (near
support, off a rebound, after a Phase-C spring) survives a Last Supper; a stretched
one is the trap.

*Stretch* — how far the LPS foot sits *above the box that birthed it* (its energy source):

- `_lps_stretch_atr` = `(lps_low − R) / ATR` — distance above the ceiling, in ATR;
- `_lps_stretch_box` = `(lps_low − R) / (R − S)` — same, in box-heights.

≤ 0 means the LPS formed in or below the box (no stretch); a large positive value
flags a stretched, Last-Supper-risk LPS far from its energy source.

*Event geometry* (`engine_alpha/structure/phase_features.py` →
`_last_supper_measurements`) — the run-up-and-flush around the LPS:

- `_last_supper_pullback_from_extension_pct` = `(anchor_high − lps_low) /
  anchor_high` — depth of the pullback from the trapping run-up's high
  (`anchor_high` = the High at the elected LPS anchor bar) down to the LPS low;
- `_last_supper_reclaim_quality` ∈ [0,1] — how much of that pullback the LPS
  reclaimed (final close vs the LPS low, over the swing), averaged with the final
  bar's spread contraction (did it recover cleanly — the "popping off *after* the
  Last Supper" tell);
- `_last_supper_source_box_age` = bars from when price left the source box (rose
  above R) to the LPS low — over-extension in *time* from the energy source; set
  only when the LPS sits above R.

*Pivot-anchored over-extension* (added 2026-07-26, `_run_up_pivot_bar`) — the same
question, anchored on the run-up's **terminal swing pivot** instead of the elected
LPS window's first bar. The operator's statement of the read: *"how far above [the
energy source] sits the last pivot that caused that run up… to avoid traps of a deep
correction."*

- `_last_supper_pivot_stretch_atr` = `(pivot_high − R) / ATR` — the operator's
  measure: how far above the energy source the run-up actually reached;
- `_last_supper_pivot_stretch_box` — the same, in box-heights;
- `_last_supper_pullback_from_pivot_pct` = `(pivot_high − lps_low) / pivot_high`;
- `_last_supper_pivot_bars_back` = bars from the pivot to the LPS low.

**Why a sibling family and not a redefinition.** `anchor_high` above is the High at
the *elected window's first bar*, and elected windows run 2–7 bars — so its reach is
~2–3 bars in practice and it cannot see a give-back that began earlier. Measured over
4,561 archived rows, `_last_supper_pullback_from_extension_pct` has a **maximum ever
recorded value of 0.144**; it structurally cannot report a deep pullback. The defect is
tail-shaped, not universal: over 17 Guided-List tickers 9/17 agree exactly with the
pivot anchor (median ratio 1.00×) while the tail diverges hard — EGBN 0.019 → 0.100
(5.3×), WTS 2.7×, CTOS 2.4×. The old columns are kept unchanged so historical rows stay
comparable; redefining a live column in place would make new rows non-comparable while
looking like a fix (the `bin_a_*` seam precedent).

All raw, archived **measure-first** — never gated or scored until validated against
the durable-win vs cash-grab outcome.

### Inner-origin measurements

The selected inner Phase-D range also records how it was born:

- `_inner_source` = `midpoint` or `inner_climax`, describing which best-of-both
  search origin produced the selected inner box;
- `_inner_search_start_bar` = the df bar where that winning inner search began;
- `_inner_climax_bar` / `_inner_reaction_bar` = the detected mini-BC -> mini-AR
  swing when `_inner_source = inner_climax`;
- `_inner_reaction_pct` / `_inner_reaction_bars` = depth and duration of that
  reaction.

These are descriptive archive fields only. They let the calibration report learn
whether inner boxes born from a real mini-climax behave differently from midpoint
heuristic boxes before any later scoring or anchoring change is considered.

### Minervini Stage-2 trend template

`trend_template()` ([engine_alpha/structure/indicators.py](../engine_alpha/structure/indicators.py))
records the classic price/MA leadership template as raw context, computed
self-contained from the daily frame:

1. price > SMA_150 and > SMA_200; 2. SMA_150 > SMA_200; 3. SMA_200 rising over
~1 month (21 bars); 4. SMA_50 > SMA_150 > SMA_200; 5. price > SMA_50; 6. price
≥ 30% above the 52-week low; 7. price within 25% of the 52-week high.

Fields: `_stage2_ma_stack_pass`, `_stage2_ma200_slope_1m_pct`,
`_stage2_52w_low_pct`, `_stage2_trend_pass_count` (0–7), `_stage2_trend_pass`
(all 7). Minervini's 8th criterion (RS rating ≥ 70, a *universe percentile*) is
**deliberately omitted from the count** — the live scoring path measures relative
strength SPY-relatively via `excess_return_6m` — so the count is out of 7.
Context only; no gate, no score. **Correction 2026-07-26:** a universe-percentile
RS rank DOES exist in the tree (`core/regime/percentile.py` + `scan_context.attach_rs_ratings`,
wired at `screener.py` and archived as `rs_rating`); it is dormant only because
`RS_LINE_ENABLED` / `SECTOR_RANKING_ENABLED` are False. Do not rebuild it — the
action is a flag flip plus a shadow re-capture.

All Stage-2A fields persist to `setup_archive` (writer + seed parity) and are
surfaced by `core/archive/analyze.py` in the fingerprint + correlation sections.

### The Phase-A anchor family is partitioned, not pooled (2026-08-13)

`bin_a_bars` / `bin_a_range_pct` / `bin_a_volume_ratio` / `bars_since_bc` /
`descent_length` all measure the **climax→AR span**, so their value is a function
of where the reader puts the automatic reaction — not only of what the chart did.
The always-on climax-terminality repair moves that anchor with no chart changing
— and it has been re-keyed since (2026-08-19). Pooled across an
`engine_config_version` seam, rows either side are an average of two different
measurements of the same word. (A second mover, the dark
`AR_FIRST_REACTION_ENABLED` tighten, was RULED DELETED 2026-09-08; the partition
below outlives it because the climax repair alone still needs it.)

`analyze.py` now takes that partition (`PHASE_A_ANCHOR_FEATURES`): on a
multi-epoch population the family is **withheld** from the pooled fingerprint and
from the outcome correlations, and reported separately scoped to the **current**
epoch — the one holding the latest `scan_date`, since config hashes carry no
ordering and the largest epoch here is the oldest. On a single-epoch population
nothing changes. It was built as the precondition for flipping
`AR_FIRST_REACTION_ENABLED`, which never happened — but it STANDS on its own: the
climax-terminality re-key is itself an AR-mode seam, and without the partition a
blend across it reads as a signal.
Gate: `tests/test_analyze_anchor_seam.py`.

---

## Outputs

`_evaluate_ticker()` returns one dict per qualifying ticker. Public fields surfaced to terminal/dashboard: `Ticker`, `Tier`, `Setup`, `Score`, `Current Price`, `Base Len`, `Box Width`, `Touches`, `ATR Ratio`, `LPS Length`, `Breach Days`. Underscore-prefixed fields feed the chart renderer and the archive but are not displayed in the terminal.

Important structure payloads:

- Box/rail fields: `_R`, `_S`, `_r_anchor_bar`, `_s_anchor_bar`, `_phase_a_start_date`, `_phase_a_end_date`, `_phase_b_start_date`, `_phase_d_start_date`.
- LPS geometry: `_lps_offset`, `_lps_len`, `_trigger_price`, `_lps_zone_type`, `_lps_descent_frac`, `_lps_high_descent_frac`, `_lps_profile_unit`, `_lps_pullback_profile`, `_lps_first_high`, `_lps_last_low`, `_lps_window_high`, `_lps_window_low`.
- Inner/Phase-D fields: `_phase_d_inner`, `_lps_in_inner`, `_inner_*`, `_bin_d_boundary_source`, `_phase_d_evidence_json`.
- Scoring/archive helpers: `_sub_scores`, `_r_touch_vol_z`, `_s_touch_vol_z`, `_stage2_*`, `_bin_*`, `_trav_*`, `_eq_*`.

The read-only scoping payload is also underscore-prefixed: `_phase_a_start_date`, `_phase_a_end_date`, `_phase_b_start_date`, `_phase_d_start_date`, optional `_phase_c_event_date`, `_lps_zone_low`, `_lps_zone_high`, `_lps_zone_start_date`, `_lps_zone_end_date`, `_has_mini_consolidation`, `_scope_confidence`, and `_phase_d_evidence_json`. These fields are visualization/diagnostic facts only; no downstream filtering or scoring consumes them.

The `_lps_zone_*` quad is the **single drawn LPS** (operator ruling 2026-08-09: one LPS
per setup — the chronological terminal one in Phase D). The prior-test staircase the
payload used to carry (`lps_tests`, filtered by `phase_d.drawn_support_tests`) was
retired from the wire and the chart in the same ruling; the RAW staircase
(`detect_lps_tests`) still runs inside evaluation, feeding the Phase-D boundary
evidence (`support_test_evidence_starts`) and the LPS-shrink charter measurement —
measurement kept, marking dropped.

Pipeline returns `(results_df, market_data, tickers, market_context)` — `results_df` is sorted by `Score` descending.

### The narrative fact block (Surface the Read)

Each `chart_data` entry in the payload artifact also carries the engine's read of the chart —
what the frontend narrative surface renders and the operator grades concordance against:

- **The `event_map_*` family** (the whole `EVENT_MAP_COLUMN_SQL` family), projected by
  `event_map.narrative_chart_fields()` — the THIRD consumer of the same extraction both archive
  writers splat, so the archived cell and the served field are value-identical per fire by
  construction. Keys match the archive column names verbatim. The one shape change at this
  boundary: `event_map_episodes` travels PARSED (the archive's JSON text cell decoded once,
  engine-side), so the wire carries structure. An unparseable tape degrades that one field to
  `None` while the scalars stay measured — "tape unreadable" (scalars present, tape `None`) is
  distinguishable from "not measured" (whole family `None`, i.e. pre-flip rows / flag off).
  Since 2026-08-10 the family also carries **`event_map_zone_coverage`** — the geometry
  companion (`2 × TOUCH_TOLERANCE_ATR × ATR / (R−S)`, raw, unclamped; NULL when the read was
  refused): the episode zones are ATR-fixed, so on the screener's tightest boxes they consume
  most of the box height and distinct tests merge into one unresolved visit (the LEVI case —
  strategy_alpha "the stated geometric limit"). Consumed in two places, both mirroring the
  NaN-bars law: `_story_points` routes all-zero counts at coverage ≥
  `STORY_UNREADABLE_ZONE_COVERAGE` to ABSENT (zero-by-geometry never masquerades as
  zero-by-drift; nonzero counts stay evidence at any coverage), and the lens/chapter-strip
  caveat channel (`narrativeRead.readCaveats`) says the same thing in the operator's words.
  The zones themselves are deliberately untouched — re-basing them is a census re-pin program,
  not a cleanup (the pinned-yardsticks warning in `read_rail_episodes`).
- **Electing-pool provenance**: `elected_pool` (closed set) and `story_admission_profile`
  (the sentence that admitted a story fire — AP-8: a different basis from the substrate's
  `event_map_story_admitted`, and the two may legally disagree).
- **`scan_identity`** (payload top level): `scan_date` — the SAME string
  `archive_scan_results` stamps (scan_job computes it once and threads it to both writers, so
  payload and archive can never straddle midnight into different identities). The value is the
  panel's own last completed session, copied from the fetched artifact rather than the wall
  clock (EC-37); clock fallback only for an empty panel. The prior local-`today()` stamp on an
  ET+7 box filed weekend and post-midnight re-scans of Friday's data under new Saturday/Sunday
  identities — the archive's ~28% duplicate-episode defect (fixed 2026-08-11; a weekend re-scan
  now re-upserts Friday's rows idempotently). Plus `universe_type` and
  `engine_config_version`. A review verdict recorded from the frontend binds to the archive row
  via this key verbatim, never a client-derived date.

- **The election trace** (`election_trace`, flag `ELECTION_TRACE_EXPORT_ENABLED`, dark):
  `read_structure`'s own narration captured during the SAME election that fired (evaluation
  passes `trace=[]` under the flag — never a re-run, which could elect a different box) and
  summarized by the ONE owner of the outbound shape, `structure/trace_export.py`: per-root
  climax/AR **dates** + outcome + per-stage refusal counts + how far the best candidate got
  (`terminal_verdict` — the one summarizer; the census tools' three independent copies are its
  migration backlog) + the elected framing's provenance (start date, rails, candidate/valid
  counts, rescued). Gate-leg sentences render from the structured leg records + `GATE_LEGS`
  through the one operator-language vocabulary (`leg_sentence`) — internal `detail` prose never
  reaches a surface. The RAW trace stays engine-internal (measured 2026-08-04: median ~106 KB,
  p90 3.6 MB per ticker); the export is ~1–2 KB. Archived per fire as ONE TEXT cell (model-only
  column; NULL = never captured, never backfilled) and served parsed in `chart_data`. Capture
  cost measured +20.3 ms per evaluated ticker (~+111 s per full scan); the flip is gated on that
  bound re-measured in scan metrics (see the flag-ledger row).

- **The strategy read** (`strategy_correction_depth_pct` / `strategy_floor_above_ar`, flag
  `STRATEGY_READ_ENABLED`, dark): the held-through-correction campaign context, measure-first —
  how deep the base floor cut below the resolved climax high, and whether it held at/above the
  automatic reaction's low. Raw values only (`structure/strategy_read.py`); a ruled judgment over
  them is a later archive calibration, never an add-time threshold.

The block is display/record data only: no score, tier, gate, or election reads it, and the
frontend formats it without re-deriving any judgment (one implementation per ruled predicate).

Every scan also writes timing telemetry:

- `cache_meta.json["scan_metrics"]` — latest run summary.
- `output/scan_metrics.jsonl` — append-only history, one JSON record per scan.
- `market_context["_scan_metrics"]` — included in `output/screener_data.json`.

The phase timings are `ticker_universe`, `market_data_fetch`, `frame_prep`,
`market_context`, `evaluation`, and `result_assembly`; counts include the loaded
universe size, evaluated ticker-frame count, and setup count.

---

## Archive System

The screener writes every output to a SQLite-backed setup archive (`webapp/backend/trading_journal.db`, `setup_archive` table) so we can build a regression dataset of structural fingerprints + forward outcomes.

### `archive.writer.archive_scan_results()` ([core/archive/writer.py](../core/archive/writer.py))
- Called automatically after each screener run.
- Upserts on `(ticker, scan_date)` — re-running the same day updates rather than duplicates.
- `autoflush=False` on the session: avoids the "database is locked" path where a per-row existence query would auto-flush pending UPDATEs while the webapp holds a read lock.
- Attaches **market context** to every row: `spy_trend`, `vix_level`, `sector_etf`, `sector_trend` (sector ETF mapped per ticker, 50d trend pulled at scan_date). Sector lookups are cached per ticker within a run.
- New archive columns are **model-only** registrations (AP-7): declare the `Column` on `SetupArchive`, emit the `_key` from `evaluation.py`, add the `row.get` line here — the boot pass and this writer's second pass derive the `ALTER TABLE`s from `SetupArchive.__table__`; the legacy `_NEW_COLUMNS` hand list does not grow. The `eq_*` outside-bar family (2026-09-05) travelled this route; `eq_terminal_run_form` is a closed set (`box_gates.TERMINAL_RUN_FORMS`) with a fresh-DB CHECK like `inner_position`.

### `seed_archive()` ([core/archive/seed.py](../core/archive/seed.py))
- Bootstrap mechanism for known-winner setups defined in `SEED_SETUPS = [(ticker, trigger_date), ...]`.
- For each pair, scans `[trigger_date - 10d, trigger_date + 3d]` to find which day the screener actually fired (LPS is identified *before* the breakout), keeps the highest-scoring hit.
- Re-runs the full Phase 1–4 pipeline at that historical date via `_evaluate_at_date()` (a ported copy of `_evaluate_ticker` that works on a pre-sliced DataFrame).
- Computes forward returns immediately (we have the future data already).
- Tags rows with `source="seed"`, `quality_label="perfect"` to distinguish from live scans.
- CLI: `python -m core.archive.seed [--force]`.

### `update_forward_returns()` ([core/archive/forward_returns.py](../core/archive/forward_returns.py))
- Backfills outcome data for archive rows older than `--min-age` calendar days (default 5).
- For each setup, downloads OHLC after `scan_date` and computes via `_compute_returns()`:
  - **Forward returns:** `fwd_return_1d`, `5d`, `10d`, `20d`, `60d` (close-to-close from `scan_close`).
  - **MFE/MAE:** maximum favorable / adverse excursion at 20d and 60d windows.
  - **Trigger status:** `triggered = 1` if any forward `High >= trigger_price`, plus `trigger_date`.
- **The stored absolutes are re-scaled before they are graded.** `trigger_price` and `s_level` sit on the SCAN-TIME price scale; the freshly downloaded series may not. `_price_scale_factor` recovers the factor from the stored scan close vs the re-read one, and has THREE outcomes: agree (1.0), a usable factor, and **UNKNOWN** when the implied factor lands outside `[0.2, 5.0]`. Unknown is an abstention, not a claim of "same scale" — a 10-for-1 split, or a 1-for-10 reverse split among the sub-$5 names, cannot be told from a bad stored close. On unknown, every column derived from a stored absolute (`triggered` / `trigger_date` / `days_to_*` / `trigger_volume_ratio` / `r_multiple_*` / `barrier_label` / `win_barrier`) is written NULL and the refusal is logged; the ratio metrics read only the fresh close and stay valid. `near_miss_outcomes` applies the same rule — an unknown scale never records "never triggered".
- By default skips rows that already have `fwd_return_1d` populated; `--force` re-computes everything.
- CLI: `python -m core.archive.forward_returns [--min-age N] [--force]`.

---

## Settings Quick-Reference

<!-- BEGIN GENERATED: settings-quick-reference -->
_Generated from the frozen engine-identity allow-list
(`engine_alpha/freeze/manifest.ENGINE_SETTINGS_KEYS`) — every constant that can move a
detector decision, in manifest order, with its live `config/settings.py` value.
Regenerate with `python -m tools.settings_reference --write`;
`tests/test_docs_sync.py` fails the suite when this block drifts._

_engine_config_version: `1f45155f67fc4db505617e63cb33b438d17b70dae9ce32c1a8be17cfa2514bbb`_

```text
DATA_DIVIDEND_ADJUSTED = False
MIN_PRICE = 3.0
MIN_VOLUME_50D = 50000
MIN_YEARLY_RETURN = -0.2
SMA50_DIP_EXCEPTION_ENABLED = False
SMA50_DIP_MAX_SESSIONS = 25
SMA50_DIP_MAX_ATR = 1.0
BOTTOMING_BASE_LANE_ENABLED = False
BOTTOMING_SMA50_BARS = 50
MIN_BASE_DAYS = 20
MAX_BOX_WIDTH = 0.18
CRASH_FILTER_MULT = 0.7
EXTENSION_FILTER_MULT = 1.15
PIVOT_ORDER_SHORT = 1
PIVOT_ORDER_LONG = 2
PIVOT_ORDER_THRESHOLD = 40
PIP_MACRO_K_MAX = 24
PIP_MACRO_MAX_POST_EXCESS = 0.25
PIP_MACRO_MIN_BASE_BARS = 20
PIP_MACRO_EQ_FLOOR_FRAC = 0.5
PIP_MACRO_EQ_OSC_FRAC = 0.3
PHASE_A_CLIMAX_TERMINALITY_EXCESS = 0.25
CAUSE_BEFORE_EFFECT_VETO_ENABLED = True
CAUSE_LPS_LOOSE_MAX = 0.9
BOUNDARY_ATR_BUFFER = 0.5
MAX_CONSECUTIVE_OUTSIDE_DAYS = 10
MIN_BOUNDARY_RESPECT_PCT = 0.8
TOUCH_TOLERANCE_ATR = 0.5
EQ_MIN_TOUCHES_PER_RAIL = 3
EQ_MIN_TOUCH_THIRDS = 2
EQ_MIN_HALF_DWELL = 0.15
EQ_MAX_MID_DWELL = 0.45
EQ_MIN_COVERAGE = 0.8
EQ_COVERAGE_BINS = 6
EQ_COVERAGE_MIN_FRAC = 0.03
TRAVERSAL_NOISE_FRAC = 0.15
TRAVERSAL_FULL_FRAC = 0.55
TRAVERSAL_LOW_ZONE = 0.3
TRAVERSAL_HIGH_ZONE = 0.7
TRAVERSAL_MIN = 2
TRAVERSAL_MIN_DENSITY = 0.08
DESCENT_TAIL_LSF_MAX = 0.4
DESCENT_TAIL_CFP_MIN = 0.2
SOS_TRIM_MIN_RUN = 3
SOS_TRIM_MIN_PREFIX_FRAC = 0.3
SOS_NEAR_R_MAX_BOX = 1.5
SOS_HOLD_MAX_RANGE_BOX = 0.55
TREND_MIN_GAIN_PCT = 0.15
TREND_MIN_MOVE_BARS = 20
TREND_PRIOR_LOOKBACK = 100
LOCAL_PEAK_BARS = 30
ROOT_TREND_SMA = 200
PHASE_B_ATR_WINDOW = 30
AR_MIN_DROP_PCT = 0.05
AR_MAX_BARS = 15
LPS_MIN_DESCENT_FRAC = 0.0
LPS_MIN_HIGH_DESCENT_FRAC = 0.0
LPS_MAX_WINDOW_BOX_RANGE = 0.85
LPS_OVERSHOOT_WINDOW_ATR_ENABLED = True
LPS_OVERSHOOT_WINDOW_ATR_MULT = 2.0
LPS_RESCUE_MAX_ADVANCE_BOX = 0.21
LPS_INSIDE_HIGH_EXTENSION_BOX_MAX = 0.35
LPS_INSIDE_HIGH_EXTENSION_ATR_MAX = 0.75
LPS_SCAN_OFFSET_MAX = 7
LPS_LENGTH_MIN = 2
LPS_LENGTH_MAX = 7
LPS_HOLD_TOLERANCE = 0.95
LPS_PROFILE_BOX_FRACTION_FLOOR = 0.15
LPS_PULLBACK_PROFILE_MIN = 0.4
LPS_PULLBACK_PROFILE_MIN_OVERSHOOT_R = 1.25
LPS_PULLBACK_PROFILE_MAX = 4.5
LPS_TERMINAL_LOW_TOL_PROFILE = 0.1
LPS_SPREAD_MAX_PROFILE_MULT = 1.25
LPS_SPREAD_EXPANSION_MAX_PROFILE = 0.35
LPS_AFTER_SPRING_ENABLED = True
LPS_HOLDING_SHELF_ENABLED = True
LPS_SHELF_LENGTH_MIN = 3
LPS_SHELF_MIN_LOW_POS_BOX = 0.5
LPS_CEILING_REST_ENABLED = False
RESPECT_WHOLE_BAR_ENABLED = False
DWELL_GRADED_ENABLED = False
BOX_HANDOVER_RANGES_ENABLED = False
BOX_HANDOVER_MAX_ABOVE_R_ATR = 1.5
SPRING_BOUNDS_LIFTED_ENABLED = False
LPS_RANGES_YARDSTICK_ENABLED = False
LPS_WINDOW_SPAN_ATR_MAX = 2.5
LPS_LAUNCH_ABOVE_R_ATR_MAX = 2.5
LPS_SHELF_ABOVE_R_ATR_MAX = 1.5
LPS_ZONE_CEILING_ATR = 1.35
LPS_GRADED_TRAITS_ENABLED = False
LPS_CORRECTION_DIG_MIN_ATR = 0.68
LPS_CORRECTION_LAST_HIGH_MAX_ABOVE_FIRST_ATR = 0.25
LPS_WINDOW_RECEDING_ENABLED = False
LPS_BREAKOUT_DAY_CLOSE_ABOVE_PRIOR_HIGH_ATR = 0.1
LPS_BUY_DAY_READS_HIGH_ENABLED = False
LPS_REFUSALS_TO_GRADES_ENABLED = False
TURN_LINE_ENABLED = False
TURN_LINE_TREND_ENABLED = False
TURN_LINE_FLOOR_ATR = 0.75
LINE_WORD_SOS_ENABLED = False
LINE_WORD_LAST_SUPPER_ENABLED = False
LINE_WORD_PHASE_C_ENABLED = False
LINE_WORD_PHASE_D_ENABLED = False
LINE_WORD_MINI_ENABLED = False
LINE_WORD_AREA_ATR = 0.5
LINE_WORD_SOS_MIN_GROUND_ATR = 1.7
LINE_WORD_SUPPER_DIG_ATR = 1.5
LINE_WORD_SUPPER_MAX_DAYS = 4
LPS_CEILING_REST_MAX_BELOW_R_ATR = 0.3
BAND_RAILS_ENABLED = True
BAND_MAX_BOX_WIDTH = 0.23
BAND_EVENT_MIN_BARS = 2
BAND_EVENT_MAX_DEPTH_ATR = 5.0
BAND_EVENT_MAX_BARS = 20
STORY_POOL_ENABLED = True
CONTRACTION_RESCUE_ENABLED = False
NEAR_MISS_MAX_QUANTA = 1
NEAR_MISS_WIDTH_DEFICIT_MAX = 0.0081
NEAR_MISS_CRASH_DEFICIT_MAX = 0.0083
NEAR_MISS_DENSITY_DEFICIT_MAX = 0.011
NEAR_MISS_LANE_ENABLED = True
NEAR_MISS_TOP_K = 32
NEAR_MISS_WRITER_TICKER_CAP = 8
NEAR_MISS_WRITER_GLOBAL_CAP = 200
ELECTION_DETHRONE_ENABLED = True
ELECTION_DETHRONE_SESSIONS = 10
LPS_DRAW_MIN_DESCENT_FRAC = 0.4
LPS_ZONE_ATR_MULT = 0.5
BIN_C_UNDERCUT_ATR_MIN = 0.3
BIN_C_UNDERCUT_ATR_MAX = 3.0
BIN_C_UNDERCUT_BOX_MAX = 0.65
BIN_C_RECOVERY_BARS_MAX = 8
BIN_C_LINGER_BARS_MAX = 12
BIN_C_HOLD_BARS = 3
BIN_C_HOLD_TOL_ATR = 0.5
BIN_C_SIGNIF_UNDERCUT_ATR = 0.75
BIN_C_MIN_LINGER_BARS = 2
BIN_C_LATE_BOX_FRACTION = 0.5
PHASE_D_VTIP_LATE_FRACTION = 0.35
PHASE_D_VTIP_RECOVERY_BARS = 6
LPS_RANGE_PERCENTILE = 0.5
LPS_SPREAD_MUST_DECLINE = True
LPS_VOL_CONTRACTION_MAX = 0.87
STRUCTURE_EDGE_SKIP_BARS = 5
STRUCTURE_ATR_SAMPLE_OFFSET = 6
INNER_SEARCH_FRACTION = 0.5
INNER_TIGHTNESS_RATIO = 0.75
INNER_MIN_DAYS = 15
TIER_S_STRUCT = 62
TIER_A_STRUCT = 52
TIER_B_STRUCT = 42
TIER_C_STRUCT = 32
S_MAX_BOX_WIDTH = 0.15
SCORE_BASE_AGE = 22
BASE_AGE_CAP_DAYS = 120
BASE_AGE_DEADSPACE_WIDTH = 0.06
SCORE_TOUCH_DENSITY = 25
SCORE_VOL_CONTRACTION = 20
SCORE_LPS_TIGHTNESS = 20
SCORE_BOX_TIGHTNESS = 22
SCORE_ATR_SQUEEZE = 8
TIGHTNESS_ADR_AWARE = True
MAX_BOX_WIDTH_ADR = 4.5
CANDLE_GRADE_FLOOR = 0.55
CANDLE_SPREAD_BOX_CLEAN = 0.35
CANDLE_SPREAD_BOX_MESSY = 0.6
CANDLE_SPREAD_ATR_CLEAN = 0.9
CANDLE_SPREAD_ATR_MESSY = 1.4
CANDLE_TIGHTBAR_CLEAN = 0.65
CANDLE_TIGHTBAR_MESSY = 0.3
SCORE_SPRING = 0
TOUCH_POINT_RATE = 2.0
LPS_TIGHTNESS_SLOPE = 2.0
VOL_CONTRACTION_SLOPE = 2.0
SCORE_STORY_S_TESTS = 0
SCORE_STORY_R_REJECTIONS = 0
SCORE_STORY_ALTERNATIONS = 0
SCORE_STORY_TERMINAL_POSTURE = 0
STORY_COMPLETED_TESTS_FULL = 3
STORY_ALTERNATIONS_FULL = 2
STORY_UNREADABLE_NAN_BARS = 5
STORY_UNREADABLE_ZONE_COVERAGE = 0.5
EPISODE_MAX_GAP_BARS = 2
EPISODE_DRIFT_MIN_BARS = 3
EVENT_HOLD_MIN_BARS = 6
MINI_POSITION_TOL_ATR = 0.5
TA_WARN_TERMINAL_DRIFT = 1.0
TA_GRADE_WARNING_FLOOR = 0.5
LPS_SHRINK_MIN_TESTS = 3
STORY_RICHNESS_FULL = 0.15
TREND_BASE_COUNT_CAP = 4
TREND_BASE_WALK_MAX_ROOTS = 12
TOUCH_VOL_Z_NO_SUPPLY = -0.3
TOUCH_VOL_Z_SPRING = 0.3
TOUCH_VOL_Z_HEAVY_R = 0.5
TA_WARN_WEAK_MONTHLY = 1.0
FUNDAMENTALS_ENABLED = False
FUNDAMENTALS_EARNINGS_HISTORY_LIMIT = 12
FUNDAMENTALS_FILING_LAG_DAYS = 75
RS_LINE_ENABLED = False
RS_LINE_NEW_HIGH_LOOKBACK = 252
SECTOR_RANKING_ENABLED = False
SECTOR_RANKING_LOOKBACKS = (21, 63, 126)
RS_RATING_LOOKBACK = 252
SCORE_SETUP_QUALITY = 8.0
SETUP_QUALITY_W_COMPLETENESS = 0.7
SETUP_QUALITY_W_CHRONOLOGY = 0.3
SETUP_QUALITY_CHRONO_PARTIAL = 0.5
EVENT_MAP_ENABLED = True
ELECTION_STABILITY_ENABLED = False
ELECTION_STABILITY_LOOKBACK = 3
ELECTION_TRACE_EXPORT_ENABLED = False
STRATEGY_READ_ENABLED = False
ENGAGEMENT_MAX_EXCURSION_ATR = 1.5
SCORE_TRAVERSAL_QUALITY = 10
TRAVERSAL_QUALITY_DENSITY_FULL = 0.33
TRAVERSAL_QUALITY_DWELL_PENALTY = 8
MIN_STRONG_YEARLY_RETURN = 0.3
MAX_STRONG_YEARLY_RETURN = 0.6
SCORE_UPTREND_BONUS = 0
SCORE_RS_BONUS = 0
RS_LOOKBACK_BARS = 126
RS_MAX_EXCESS_RETURN = 0.3
SCORE_52W_HIGH_PROXIMITY = 8
HIGH_PROXIMITY_FULL_PCT = -0.05
HIGH_PROXIMITY_ZERO_PCT = -0.2
SCORE_BREADTH_BONUS = 8
BREADTH_FULL_PCT = 0.6
BREADTH_ZERO_PCT = 0.35
SCORE_CONTRACTION = 12
CONTRACTION_IDEAL_MIN = 2
CONTRACTION_IDEAL_MAX = 6
CONTRACTION_FINAL_TIGHT_PCT = 0.03
CONTRACTION_FINAL_LOOSE_PCT = 0.12
SCORE_ASCENDING_SUPPORT = 8
ASCENDING_SUPPORT_FULL_SLOPE = 0.1
ADR_WINDOW = 20
SCORE_ADR = 8
ADR_FULL_PCT = 5.0
TOUCH_BONUS_INDIVIDUAL = 3
TOUCH_BONUS_TOTAL = 6
TOUCH_BONUS_POINTS = 10
HTF_CONTEXT_ENABLED = True
DAILY_STRUCTURE_PERIOD = '2y'
HTF_STAGE_MA = 30
HTF_STAGE_MA_SLOPE_BARS = 4
HTF_WEEKLY_WINDOWS = {'MIN_BASE_DAYS': 6, 'STRUCTURE_EDGE_SKIP_BARS': 1, 'TREND_MIN_MOVE_BARS': 5, 'TREND_PRIOR_LOOKBACK': 26, 'LOCAL_PEAK_BARS': 8, 'ROOT_TREND_SMA': 30, 'PHASE_B_ATR_WINDOW': 8, 'AR_MAX_BARS': 4, 'MAX_CONSECUTIVE_OUTSIDE_DAYS': 3, 'PIVOT_ORDER_THRESHOLD': 12, 'EQ_MIN_TOUCHES_PER_RAIL': 2, 'LPS_SCAN_OFFSET_MAX': 2, 'LPS_LENGTH_MIN': 1, 'LPS_LENGTH_MAX': 4, 'BIN_C_RECOVERY_BARS_MAX': 3, 'BIN_C_LINGER_BARS_MAX': 4, 'BIN_C_HOLD_BARS': 1, 'BIN_C_MIN_LINGER_BARS': 1, 'PHASE_D_VTIP_RECOVERY_BARS': 2, 'BOTTOMING_BASE_LANE_ENABLED': False}
HTF_MONTHLY_WINDOWS = {'MIN_BASE_DAYS': 4, 'STRUCTURE_EDGE_SKIP_BARS': 1, 'TREND_MIN_MOVE_BARS': 3, 'TREND_PRIOR_LOOKBACK': 12, 'LOCAL_PEAK_BARS': 4, 'ROOT_TREND_SMA': 10, 'PHASE_B_ATR_WINDOW': 6, 'AR_MAX_BARS': 3, 'MAX_CONSECUTIVE_OUTSIDE_DAYS': 2, 'PIVOT_ORDER_THRESHOLD': 8, 'EQ_MIN_TOUCHES_PER_RAIL': 2, 'LPS_SCAN_OFFSET_MAX': 1, 'LPS_LENGTH_MIN': 1, 'LPS_LENGTH_MAX': 2, 'BIN_C_RECOVERY_BARS_MAX': 2, 'BIN_C_LINGER_BARS_MAX': 3, 'BIN_C_HOLD_BARS': 1, 'BIN_C_MIN_LINGER_BARS': 1, 'PHASE_D_VTIP_RECOVERY_BARS': 1, 'BOTTOMING_BASE_LANE_ENABLED': False}
POWER_PLAY_PRESET_ENABLED = True
POWER_PLAY_STORY_FORM_ENABLED = False
POWER_PLAY_WINDOWS = {'MIN_BASE_DAYS': 8, 'PIP_MACRO_MIN_BASE_BARS': 8}
POWER_PLAY_POLE_MIN_GAIN = 0.9
POWER_PLAY_POLE_WINDOW_BARS = 40
POWER_PLAY_BREAKOUT_DEPARTURE_ATR = 1.0
```

_Ops / data-fetch knobs (cache TTLs, Yahoo rate limits, admission/quarantine,
scheduler, dashboard) are deliberately NOT part of the engine identity — see
the "DELIBERATELY EXCLUDED" block in
[engine_alpha/freeze/manifest.py](../engine_alpha/freeze/manifest.py)._
<!-- END GENERATED: settings-quick-reference -->

---

## Acceptable Misses

**RE-RULED 2026-08-14 — operator: "Power Plays are wanted setups, amend acceptable
misses."** The young-fast-breakout class **contains the Power Play (Minervini)** — his
named examples: MAN, FTNT (*"a powerplay that the engine finds today! and we should model
after it"*), MRVL, ARM — and is **no longer an acceptable miss**: it is a wanted species
with an open, measure-first program. Nothing flips in this change — `MIN_BASE_DAYS`, the
occupancy floors, the story form and the baseline gate are all untouched today; see the
`decisions.md` row of the same date for the four-specimen diagnosis (the 25-bar reading
clock from the AR; the drift-up shelf dying at occupancy + story admission when
counterfactually seeded; the `sma50` baseline leg hiding a mid-correction Power Play;
FTNT as the model specimen the engine already reads — root 25+ bars old, two-sided
26-bar shelf).

*Superseded record (standing guidance until 2026-08-14, kept as the history of the
trade-off):* setups on **young bases that break out fast** (KEYS, BRZU, NE, CGON-style)
will not be caught by this engine and that is **by design** — the base-age requirement
(`MIN_BASE_DAYS = 20`, plus the sqrt-scaled scoring up to 120 days) explicitly trades
early-stage breakouts for higher-cause Wyckoff setups. These should not be treated as
bugs to fix.

---

## Parent + Inner — Nested Phase D Range (live)

The live reader calls `find_inner_box()` ([engine_alpha/structure/bricks.py](../engine_alpha/structure/bricks.py)) after the parent equilibrium box validates. The brick mirrors the inner-search half of `detect_boxes()` ([engine_alpha/structure/consolidation.py](../engine_alpha/structure/consolidation.py)): it tries both the mechanical midpoint (`INNER_SEARCH_FRACTION = 0.5`) and the detected inner climax (`detect_inner_root_swing`), then keeps the tighter valid inner box. The inner must be meaningfully tighter (`bw_inner < INNER_TIGHTNESS_RATIO * bw_outer`, i.e. at least 25% tighter at the default 0.75) and span `INNER_MIN_DAYS = 15`+ bars. If no qualifying inner exists, `inner` is `None`; the parent still remains the base of record either way.

`detect_boxes()` remains available for diagnostics and tools. It is no longer the live screener entry point.

Inner ⊂ outer is enforced **temporally**, not in price space — the inner can sit inside, above, or below the outer's R/S; the outer's boundary-respect gate already filters out wild outliers, so an inner found in the outer's recent half is structurally adjacent regardless. **Operator ruling (2026-07-20):** "nested" means found in the *vicinity* of the parent at a more advanced point of the accumulation, never bounded by the parent's original rails — the range's contraction naturally forms a new mini process with its **own** R and S, and a mini-consolidation forming ON the parent's Resistance, treating it as its new Support, is a common variation (8/17 live inners sit partly above parent R — measured 2026-07-19, all sanctioned).

**Position attribute (2026-08-23 unification ruling; re-ruled 2026-08-29/30, the rails-are-areas + touching-both signings).** The elected inner box is stamped with its rail-proximity band against the parent's rails — `mini_consolidation_position()` in [engine_alpha/structure/inner_box.py](../engine_alpha/structure/inner_box.py): the ruled FOUR-value closed set `at_ceiling` / `mid_range` / `on_support` / `touching_both` (the ONE declaration is `RULED_POSITION_VALUES` beside the producer), tolerance `MINI_POSITION_TOL_ATR` (0.5 — the ruled ±0.5-ATR rail area, promoted to `config/settings.py` + the frozen manifest at the Task-12 seam) in candidate-ATRs, inclusive band edges. A structure engaging BOTH bands reads `touching_both` — the 2026-08-30 honesty valve that replaced the ceiling-first tiebreak: a base about one bar tall carries no separating position information and must never fabricate an at-resistance read. Stamped ONCE inside `select_inner_box` (with an EC-19 write-time assertion against the closed set, and the raw signed ATR distances riding beside the band) — the live reader and the diagnostic mirror band identically because the tolerance ATR derives from the parent window via the election's own `_candidate_atr`, never a caller-supplied ATR. This executes the operator's ruling that the ceiling shelf and the inner mini-consolidation are ONE event ("no need to give it a new name just acknowledge its position"); the species lane's `resistance_contraction_admission` stays a ruled JUDGMENT over episode facts above this event and never elects geometry. Serialized since the ONE-Event-Map Task-10 seam: the `inner_position` (+ raw distances) archive family, the position TOKEN on the dashboard wire, and four engine-resolved position chips under the operator-signed labels (decisions.md 2026-08-30; `wireVocabulary.js POSITION_LABELS`). Two sibling instruments read this event: the dark `event_vocabulary.py` projection folds it as the `mini_consolidation` tape record, and `tools/reader_pin.py` pins the band's literal grid in its committed 88-chart baseline.

The key difference between `inner_zigzag` and `phase_b_zigzag`: the inner version scores each candidate over **its own** bar range (from the earlier of the two anchors onward) rather than the full inner window. Bars before the inner's first anchor were forming a different structure and would unfairly fail boundary-respect.

Historical backtest snapshots are calibration inputs, not permanent truth. When a missed visual winner clusters around a hard LPS gate, the next step is to measure that gate against forward outcomes before moving it into quality/selector evidence.

### Adaptive LPS geometry

The live LPS detector no longer hard-gates raw percent pullback depth. It uses a setup-profile unit so wide/spready bases get realistic absolute wiggle room while tight bases stay precise:

```
base_range_threshold = max(base spread quantile, 1.2 * ATR)
profile_unit = max(base_range_threshold, LPS_PROFILE_BOX_FRACTION_FLOOR * box_height)
pullback_profile = (anchor_bar_high - elected_lps_low) / profile_unit
```

The ordinary LPS low is the **last bar's Low**, the trigger is the **last bar's High**, and the candidate is actionable only while current price remains below that trigger. The terminal-low guard requires the last Low to sit within `LPS_TERMINAL_LOW_TOL_PROFILE` profile units of the window low. A fully clean down-swing can exceed the broad window-range guard because the useful measurement is the individual price-action swing from anchor high to final valley. Spread decline remains quality evidence; hard rejection is only "spread expanded too much for this setup profile."

**OVERSHOOT_R window rescope (`LPS_OVERSHOOT_WINDOW_ATR_ENABLED`, LIVE since
2026-07-16 — solve-the-engine task 10).** The window-localization guard
(`window_range ≤ LPS_MAX_WINDOW_BOX_RANGE × box_height`) mis-scales for a
breakout throwback resting ABOVE a **narrow** box: above the box, box height
is the wrong yardstick (CTOS's marked shelf measures 1.06 box-heights but
only 1.42 of the stock's own ATRs). Flag-on, for OVERSHOOT_R-zone windows
only, the denominator becomes `max(box_height,
LPS_OVERSHOOT_WINDOW_ATR_MULT × ATR)` (k = 2.0; k ≥ 1.67 admits CTOS).
Gate-only — the archived `window_range_pct_box` measure is unchanged;
`max()` can only grow the denominator, so wide boxes and INSIDE/UNDERCUT_S
zones are provably untouched; a non-finite ATR refuses the rescoped path.
Proof at the marks: combined with the holding-shelf flag, CTOS fires
2026-07-15 tier S at rails within tolerance (span overlap 1.0). At the live
flip the shadow fixture admitted ONE new fire — BBVA (tier A, the rescope's
narrow-box OVERSHOOT_R class) — and the operator's eyeball (2026-07-17)
ruled it **"just incomplete"**: nothing really going on. The dissection
agreed on the numbers, via cause maturity rather than the Phase-D label
(both BBVA and CTOS select a `v_tip` boundary): BBVA sat on a bare-minimum
20-bar base with 2 full traversals and 5R/4S touches; CTOS earned its
throwback with a 50-bar cause, 10 traversals, 16R/16S. **Hardening bound
(2026-07-17):** a throwback above R claims the cause below is COMPLETE, so
the rescoped ATR denominator only engages on a **matured cause** —
`base_len ≥ 2 × MIN_BASE_DAYS`, the same floor a terminal shakeout needs in
the boundary-event pool. Immature causes fall back to the raw window gate
(the pre-flip path, which already rejected them); knob-free, no new reject
key. BBVA's fixture frame is frozen as negative-corpus case
`BBVA@2026-06-05` ("incomplete throwback — immature 20-bar cause"); the
fixture drop was exactly BBVA, zero collateral (CTOS byte-identical).

The zone tolerance still adapts for tight boxes: if box width is below 10%, `_zone_tolerance()` uses `max(0.5 * ATR, 0.5 * box_height)`. This keeps tight inner boxes from rejecting reasonable breakout retests just above R or failed-seller tests just below S.

### Current calibration frontier

The reader should stay visually strict, but the LPS gates should be audited as
separate ideas: hard geometry, quality evidence, and active-setup selection.

**Post-LPS refutation (operator ruling 2026-07-17, measure-first — no gate
yet).** On the BBVA hardening eyeball the operator went deeper than the cause:
on that freeze the trend, AR, and base election are all CORRECT — the defect is
the **LPS pick standing refuted by the frame's own remaining bars**: "even in
the same snapshot, after said LPS we continue down as one prominent
movement/Down Swing — no way we can measure off an LPS when we know for a fact
that the price action continues down, and by a large margin." Verified: BBVA's
LPS window (bars 495–497, low 22.77) was followed in-frame by a break of the
window low (bar 498), a feeble bounce, and an edge close 1.0 ATR below the LPS
low and back BELOW R — the throwback claim was dead before the fire. The
`offset` allowance tolerates a stale LPS by TIME but never checks REFUTATION.
Next lever, measure-first per doctrine: archive on every fire the post-window
excursion below `window_low` (ATR units) and, for OVERSHOOT_R, whether R was
re-lost; calibrate any threshold from the archive + marks (the vol-0.87
method). The frozen corpus case `BBVA@2026-06-05` guards this exact frame
meanwhile.
`tools/lps_gate_audit.py --matrix lps-core` was the scoreboard for this (tool
retired 2026-07-18, 44f8293): it could soften descent, volume, spread,
terminal-low, and pullback-profile gates individually and report which tickers
would recover/drop. Volume contraction,
descent cleanliness, and zone/range tolerances are the next places to test
against forward outcomes before loosening or hardening anything.
