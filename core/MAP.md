# Map of the Engine (`core/`)

A plain-English tour of how the screener is organized. No coding knowledge needed —
this is the "where does X live?" cheat sheet.

The engine is built as **two engines and a conductor**, plus a measuring stick:

```
        core/pipeline/   "THE CONDUCTOR"
        runs the show, in order
                 │
        ┌────────┴────────┐
        ▼                 ▼
core/structure/      core/scoring/
"HOW WE SEE          "HOW WE RATE
 THE CHART"           THE SETUP"
 (measurement)        (opinion)

        core/archive/    "THE MEASURING STICK"
        records what happened, so we can learn
```

The golden rule: **structure measures, scoring judges, pipeline coordinates.**
The structure folder reports *facts* and never decides if a setup is good.
The scoring folder turns those facts into points and never looks at a chart itself.

---

## 1. `core/structure/` — the Visual Structure Engine ("how we SEE the chart")

Pure geometry and measurement. Give it price bars, it tells you *what is there* —
with zero opinion about whether it's worth buying. **This is the prime directive:
draw the consolidation accurately and measure its tightness faithfully.**

| File | What it does (in plain terms) |
|------|-------------------------------|
| `consolidation.py` | Finds the trading range (the "box"): where the ceiling (R) and floor (S) are, how many times price touched them, how tight it is. Also `measure_contractions` (the VCP coil footprint) and `measure_touch_volume` (was volume heavy or light at the edges?). |
| `lps.py` | Finds the **Last Point of Support** — the quiet, tight pullback that marks the launch pad. Classifies it: inside the box, a backtest above the ceiling, or a spring below the floor. |
| `indicators.py` | The math helpers — ATR (volatility), ADX (trend strength), and ADR% (absolute daily range). |

**Want to change how the box or LPS is *detected*?** This folder.

## 2. `core/scoring/` — the Scoring Engine ("how we RATE the setup")

The opinion layer. It takes the measured facts from the Structure Engine and turns
them into a number and a letter grade (S / A / B / C / D).

| File | What it does |
|------|--------------|
| `scoring.py` | `score_setup` adds up 14 ingredients (box tightness, touches, volume dry-up, contraction footprint, ADR%, 52-week-high proximity, market breadth, ...) into a total. `calculate_tier` maps that total to a letter. |

**Want to change how much a factor is *worth*?** Edit the numbers in `config/settings.py`
(the `SCORE_*` and `TIER_*` constants) — never the measurement code.

## 3. `core/pipeline/` — the Conductor ("runs the screen")

The only part that knows the *order of operations*. For each stock it: filters the
junk, asks the Structure Engine where the box/LPS is, asks the Scoring Engine how good
it is, and assembles the ranked list.

| File | What it does |
|------|--------------|
| `data.py` | Downloads and caches the market data (prices, volume, the SPY benchmark). |
| `screener.py` | The baseline filter + `run_screener` (the main entry point) + the per-stock evaluation that wires structure → scoring. |

## 4. `core/archive/` — the Measuring Stick ("learn from outcomes")

**Not part of the live screen.** It records every setup the engine finds, fills in what
actually happened afterward, and lets us study which setups won. This is how we earn
the right to re-tune the scoring.

| File | Run it with | What it does |
|------|-------------|--------------|
| `writer.py` | (automatic) | Saves each scan's results into the archive database. |
| `seed.py` | `python -m core.archive.seed` | Bootstraps the archive with known historical setups. |
| `forward_returns.py` | `python -m core.archive.forward_returns` | Fills in real outcomes once setups are old enough. |
| `analyze.py` | `python -m core.archive.analyze` | The report card: winner fingerprint, what predicted returns, bias warnings. |
| `purge.py` | `python -m core.archive.purge` | Cleans uncurated rows out of the archive. |

---

## The one-line flow

`python run_screener.py` → **pipeline** loads **data**, and for each stock asks
**structure** "what's here?" then **scoring** "how good?", ranks them, shows the
dashboard, and (if enabled) hands the results to **archive** to remember.
