# Handoff: Implement GAP 3 (ADR% absolute volatility) in the Chrollo screener

You are continuing work on **Chrollo**, a Wyckoff/VCP/LPS stock screener (Python core +
FastAPI/React webapp + IBKR integration). The repo is already cloned and on branch `main`,
clean and pushed. Your job is to implement the next roadmap pillar, **GAP 3**, by following
an established pattern that two prior features (GAP 1, GAP 2) already laid down. Read this
whole brief before touching code.

---

## 0. CRITICAL SAFETY CONSTRAINT — read first, non-negotiable
- This project connects to a LIVE brokerage (IBKR / Interactive Brokers).
- **DO NOT start the backend yourself**, and **DO NOT set or export
  `IBKR_LIVE_CONFIRMED=true`** under any circumstance. That env var bypasses a
  human-confirmation gate for live trading. The human owner starts the backend
  themselves via `start_dashboard.bat`.
- **Never execute trades, move money, place orders, or auto-confirm anything brokerage-related.**
- You may run the *screener pipeline* and *archive tooling* (pure data/compute, no broker),
  run Python imports/compiles, run the frontend lint/build. You may NOT boot the webapp backend.
- All verification must be done WITHOUT a running backend (compile checks, unit-level Python
  runs, frontend `eslint`/`vite build`). Leave anything that needs the live app for the human
  to verify, and say so explicitly in your summary.

---

## 1. What this project is (mental model)
A discretionary trader uses this screener as an *idea source*. Strategy blend:
**Minervini VCP** (progressive volatility contraction) + **Qullamaggie** (momentum, higher
lows surfing a rising EMA, volatile movers resting in tight bases) + the user's own discretion.
It is NOT textbook Wyckoff — the **prime directive is accurate detection of tight visual
structure** in a base, surfaced as scannable cards.

Architecture is split into named engines under `core/` (plain-English guide at `core/MAP.md` —
READ IT FIRST):

```
core/
  MAP.md                <- plain-English tour of the whole engine; start here
  structure/            <- "Visual Structure Engine": PURE MEASUREMENT, no opinion
    consolidation.py    <- find the box/LPS, measure tightness, contractions, support slope, touch-volume
    lps.py              <- detect_lps (the final pullback / launch pad)
    indicators.py       <- reusable indicators (ATR, etc.)
    __init__.py         <- re-exports the public functions
  scoring/
    scoring.py          <- "Scoring Engine": OPINION. score_setup() + calculate_tier()
  pipeline/
    data.py             <- yfinance download + parquet cache (incremental/cold paths)
    screener.py         <- "The Conductor": wires structure -> scoring per ticker; run_screener()
  archive/
    writer.py / seed.py / forward_returns.py / analyze.py / purge.py
config/settings.py      <- ALL tunables live here
output/dashboard.py     <- writes output/screener_data.json that the React app reads
webapp/backend/         <- FastAPI (main.py, routers/, archive_models.py) -- DO NOT BOOT
webapp/frontend/        <- React (Vite). Components in src/components/
docs/strategy_v2.md     <- human-facing scoring doc
run_screener.py         <- CLI entry point: runs the full pipeline + writes dashboard JSON
```

---

## 2. The "measure-first" philosophy — obey it strictly
Every new structural signal is added as a **bonus sub-score**:
- It is **never a gate** (never filters a ticker out).
- It **never penalizes** (a stock lacking the trait simply earns 0 points on that axis).
- The raw measurement is **persisted to the archive** so a later calibration pass can test
  whether it actually predicts forward returns. Measure now, prove later.
- Sub-scores are clamped to a configured cap and summed into the total. Tier thresholds
  (S/A/B/C) are NOT recalibrated when a new sub-score is added — that waits for live data.

---

## 3. The exact pattern to follow (GAP 1 & GAP 2 are your templates)
GAP 1 added "VCP progressive contraction" (`measure_contractions`, sub-score `contraction`,
tag "VCP Coil"). GAP 2 added "Ascending Support / higher lows" (`measure_support_slope`,
sub-score `ascending_support`, tag "Ascending Support"). **Study GAP 2 end-to-end before
writing anything** — your GAP 3 changes touch the *same set of files in the same way*. Use:

```
git log --oneline -n 8
git show <gap2-commit>      # the commit titled like "GAP 2 (ascending support) ..."
```

to see precisely which files changed and how. Mirror it.

The data flow for any sub-score is:
`measurement (core/structure) -> quality passed into score_setup (core/scoring) ->
emitted as _-prefixed fields on the result dict (core/pipeline/screener.py) ->
persisted (core/archive/writer.py + seed.py + webapp DB) ->
exposed (webapp/backend/routers/archive.py + output/dashboard.py) ->
surfaced as a tag chip (webapp/frontend SetupTags.jsx) + archive card (ArchiveCard.jsx) ->
analyzable (core/archive/analyze.py)`.

---

## 4. THE TASK — GAP 3: ADR% (Average Daily Range %, absolute volatility)
**Why:** Qullamaggie selects volatile *movers* (ADR% >= ~5%) — a stock that travels enough
each day to be worth trading. The engine today only measures volatility *relatively*
(ATR-squeeze inside the base). ADR% is the missing **absolute** volatility-character axis: a
high-ADR stock resting in a tight base is the ideal momentum-continuation setup. As always:
**bonus only, no gate, no penalty.**

**Definition (standard Qullamaggie ADR%):**
```
ADR%(window) = 100 * ( mean( High_i / Low_i  for the last `window` bars ) - 1 )
```
Compute at the latest bar over a 20-bar window. (Equivalently 100*(SMA20(High/Low) - 1).)
Guard against div-by-zero / NaN / Inf — return 0.0 on any degenerate input (a flat or
zero-low bar). This matters: a single NaN in the dashboard payload 500s the
`/screener-data/` endpoint (Starlette serializes with `allow_nan=False`). `output/dashboard.py`
already has a `_json_safe()` sanitizer as a backstop, but DO NOT rely on it — guard at source.

### 4a. config/settings.py — add near the GAP 1/GAP 2 block
```python
ADR_WINDOW   = 20     # bars used for the Average Daily Range %
SCORE_ADR    = 8      # cap for the ADR sub-score
ADR_FULL_PCT = 5.0    # ADR% >= 5.0 earns full credit (Qullamaggie's ~5% mover threshold)
ADR_TAG      = 0.80   # sub-score >= 0.80*cap fires the "High ADR" tag chip
```

### 4b. core/structure/indicators.py — add the measurement
```python
def adr_pct(df, window: int = 20) -> float:
    """Average Daily Range % over the last `window` bars (Qullamaggie ADR%).
    Absolute daily volatility: how much the stock travels per day. Returns a
    plain percent (e.g. 6.2 means 6.2%). 0.0 on degenerate/insufficient input."""
    # use the last `window` rows of High/Low; ratio mean; (mean-1)*100;
    # return 0.0 if len(df) < window, or if any non-finite result.
```
Export it from `core/structure/__init__.py` (add to both the import block and `__all__`).

### 4c. core/scoring/scoring.py — add the sub-score
- `score_setup(...)` gains a new trailing param `adr_quality: float = 0.0` (keyword/defaulted so
  nothing else breaks — mirror how `support_quality` was added in GAP 2).
- Add: `s_adr = _clamp(adr_quality * settings.SCORE_ADR, settings.SCORE_ADR)`
- Add `s_adr` into `total`.
- Add `'adr': round(s_adr, 2)` to the returned sub-score dict.

### 4d. core/pipeline/screener.py — `_evaluate_ticker`
After the GAP 2 `support = measure_support_slope(...)` call:
```python
adr_value   = adr_pct(df, settings.ADR_WINDOW)          # measure on the full df, not the base window
adr_quality = min(adr_value / settings.ADR_FULL_PCT, 1.0) if settings.ADR_FULL_PCT else 0.0
```
Pass `adr_quality` into `score_setup(...)` (last arg), and emit on the result dict:
```python
'_adr_pct':     float(adr_value),
'_adr_quality': float(adr_quality),
```
Import `adr_pct` from `core.structure`.

### 4e. Persist + surface (mirror GAP 2 exactly)
- **core/archive/writer.py** — add to `_NEW_COLUMNS` and the `values` dict:
  `adr_pct` (= result `_adr_pct`) and `score_adr` (= `sub.get("adr")`).
- **core/archive/seed.py** — parity: compute `adr_pct` + quality at the historical eval date,
  pass quality into `score_setup`, write the two columns.
- **webapp/backend/archive_models.py** — 2 `Column(Float)`: `adr_pct`, `score_adr`.
- **webapp/backend/main.py** — 2 self-healing `ALTER TABLE ... ADD COLUMN` migrations (copy the
  GAP 2 ones; they're idempotent try/except blocks).
- **webapp/backend/routers/archive.py** — 2 `Optional[float]` fields on `SetupOut`: `adr_pct`,
  `score_adr`.
- **output/dashboard.py** — add `'adr'` to the sub-score key tuple in `_extract_chart_data`,
  and add `'adr_pct': row.get('_adr_pct')` to the `chart_data[ticker]` dict.
- **core/archive/analyze.py** — add `adr_pct` to the structural-feature list and `score_adr`
  to the `SUB_SCORES` list.

### 4f. Frontend
- **webapp/frontend/src/components/SetupTags.jsx**
  - Add `adr: 8` to `SUB_SCORE_CAPS`.
  - Add a new tag definition. Put it in the **`trend` group (green)** — ADR is a
    momentum/leadership *character* trait. Match the existing tooltip voice
    ("what it is + how to read it"):
    ```js
    {
      id: 'high_adr',
      label: '⚡ High ADR',
      group: 'trend',
      title: 'High Average Daily Range — this stock is a volatile mover (Qullamaggie ADR% ≥ ~5%). How to read it: it is CAPABLE of big, fast moves, so a breakout here can actually pay. Strongest combined with a tight base (loaded spring + strong spring). Respect the volatility — size smaller and give the stop more room than you would on a calm stock.',
      weight: 62,
      fires: (s) => FIRE(s, 'adr', 0.80),
    }
    ```
  - It will automatically join the green "Trend" group in the legend (no legend change needed).
- **webapp/frontend/src/components/ArchiveCard.jsx** — in `subScoresFromSetup`, add
  `adr: s.score_adr`.

### 4g. Docs & memory
- **docs/strategy_v2.md** — add an "ADR%" row to the scoring table, a short prose section
  describing the metric + the 3 new settings, and bump the component count (13 -> 14) and
  max-score note (~194 -> ~202).
- **Memory file `project_screener_quality.md`** (under the user's `.claude` projects memory dir)
  — mark **GAP 3 SHIPPED**. If you can't locate/write it, skip and note it for the human.

---

## 5. Conventions you MUST respect
- All tunables go in `config/settings.py`. No magic numbers in logic files.
- `_evaluate_ticker` is pickled by `ProcessPoolExecutor` — keep it a top-level function and keep
  new args to `score_setup` defaulted so old call sites don't break.
- Underscore-prefixed result keys (`_adr_pct`) = internal/archive fields; non-underscore =
  human-facing display columns. Follow the existing split.
- Numeric fields are returned as numbers, never pre-formatted strings.
- Guard EVERY new float against NaN/Inf at the source (the 500-error trap is real; it bit GAP 2).
- Match existing code style; no drive-by refactors of unrelated code.
- DB migrations must be idempotent (additive `ALTER TABLE ADD COLUMN`, wrapped so a re-run on an
  already-migrated DB is a no-op).

---

## 6. Verification (do all of these; none require the backend)
1. **Unit sanity** of the measurement in a Python shell:
   - A synthetic df where High/Low ~= 1.06 every bar -> `adr_pct ~= 6.0`.
   - A flat df (High == Low) -> `adr_pct == 0.0` (no NaN/Inf, no crash).
   - `len(df) < window` -> `0.0`.
2. **Imports/compile:**
   `python -c "from core.structure import adr_pct"` and
   `python -m py_compile output/dashboard.py core/pipeline/screener.py core/scoring/scoring.py core/structure/indicators.py core/archive/writer.py core/archive/seed.py`
3. **Live pipeline run (no backend):** `python run_screener.py` completes; open
   `output/screener_data.json` and confirm chart entries carry a numeric `adr_pct` and an
   `adr` sub-score, and that other scores only shift by the new additive `adr` component.
   Confirm a known high-volatility name fires the tag (sub-score `adr` >= 6.4 = 0.8*8).
4. **Archive round-trip:** `python -m core.archive.seed` then `python -m core.archive.analyze`;
   confirm `adr_pct` / `score_adr` populate (non-null) in the output.
5. **Frontend:** from `webapp/frontend/`:
   `npx eslint src/components/SetupTags.jsx src/components/ArchiveCard.jsx` (expect 0 errors;
   a single pre-existing `react-refresh/only-export-components` *warning* in SetupTags.jsx is
   fine), then `npx vite build` (expect success; the ~500kB chunk-size warning is pre-existing).
6. Leave the running-webapp visual check to the human (you cannot boot the backend). Note it.

---

## 7. Finishing up
- Stage ONLY source files. Confirm `output/screener_data.json`, `*.parquet`, `cache_meta.json`,
  `market_context.json`, `output/sector_etf_cache.json`, and `dist/` are gitignored and NOT
  staged (`git status --short` should show only the source files you edited).
- Commit with a clear message (the project ends commit messages with a `Co-Authored-By:` line —
  match the existing style; check `git log`).
- **Push to `main`** when all verification passes.
- Write a short summary: what changed, verification results, the new max-score (~202), and an
  explicit note that the running-webapp visual check + the tier-recalibration decision are
  deferred to the human (per measure-first, do NOT touch tier thresholds).

If anything here conflicts with what `core/MAP.md` or the GAP 2 commit show, trust the actual
code/commit and flag the discrepancy in your summary.
