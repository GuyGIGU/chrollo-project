# research/ — evidence, not code

What the engine's claims rest on: the raw outputs of studies and the renders the operator
judged, kept so any ruling in `docs/decisions.md` or a dated study in `docs/` can be
re-read against the data that produced it. Nothing in production imports from here.

| Folder | What it holds |
|---|---|
| `evidence/` | Raw JSON sidecars of dated censuses (`bar_state_census_*`, `miss_lane_census_*`, `rail_area_census_*`, `shape_profile_*`, `trend_terminal_ab_*`). Each is cited by the study in `docs/` of the same name. |
| `fidelity/` | Chart renders, logs and loss sheets from fidelity A/Bs. Most generators have since been deleted, so these cannot be regenerated. Keep them. |

## Where the rest of the research loop lives

The lifecycle is **scan → detection → archive → outcome maturation → analysis → evidence**:

| Stage | Home | Notes |
|---|---|---|
| Scan | `core/pipeline/screening/` | One scan: fetch, evaluate every ticker, write the payload, hand the result to the archive. |
| Detection | `engine_alpha/structure/` + `engine_alpha/scoring/` | Measures the chart, then judges it. |
| Archive | `core/archive/writer.py` | One row per ticker per scan day: a **daily observation**. |
| Maturation | `core/archive/forward_returns.py` | Fills forward returns, MFE/MAE and the trigger once a row is old enough. |
| Analysis | `core/archive/analyze.py`, `core/backtest/` | Reads **episodes**. `core/archive/episodes.py` collapses a base re-flagged day after day into one episode, so it counts once in any win rate. `core/backtest/` is production code (the backend's edge tile imports it); it is not a scratch area. |
| Instruments | `tools/research/` | The census and study scripts that produce the files here. |
| Reports | `docs/*_2026-*.md` | The dated write-ups; `docs/decisions.md` holds the rulings they led to. |

Daily observations are the raw archive rows; episodes are the unit every statistic should
count. Do not redesign that split for tidiness: episode aggregation is where the
repeated-setup dedup lives.

Sealed ground truth is **not** here: the operator's marks corpus lives in `docs/marks/` and
the regression baselines in `tests/baselines/`, and both are write-protected by
`tools/_bootstrap.py`.
