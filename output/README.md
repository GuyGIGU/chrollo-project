# output/ — runtime files, not code

The scan writes here: `screener_data.json` (and its per-universe variants, the data the
React app loads), watchlists, logs and scan metrics. Everything here except this README is
generated and gitignored.

The code that writes these files lives in `core/pipeline/screening/` (`dashboard.py`,
`terminal.py`, `scan_job.py`).

Research evidence that used to be force-added here moved to `research/evidence/` on
2026-09-24, under the same file names: `bar_state_census_2026-08-30.json`,
`miss_lane_census_2026-08-28.json`, `miss_lane_census_2026-08-29.json`,
`rail_area_census_2026-08-30.json`, `shape_profile_2026-08-29.json` and
`trend_terminal_ab_2026-08-31.json`. Older records (such as `docs/decisions.md`) still
cite the `output/` paths.
