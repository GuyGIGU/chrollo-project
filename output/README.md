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
`trend_terminal_ab_2026-08-31.json`. The signal-edge verdict run that branch
`revive/signal-edge` carried as `output/signal_edge_2026-09-03/` landed as
`research/evidence/signal_edge_2026-09-03/`. The consolidation-method program's three
evidence folders (branch `claude/eager-chatelet-65e8d4`, carried as
`output/consolidation_evidence_2026-08-31/`, `-09-01/` and `-09-02/`) landed as
`research/evidence/consolidation_evidence_2026-08-31/`, `-09-01/` and `-09-02/`. Older records
(such as `docs/decisions.md` and `docs/consolidation_method_2026-09.md`) still
cite the `output/` paths.
