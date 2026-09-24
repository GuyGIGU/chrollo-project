# output/ — runtime files, not code

The scan writes here: `screener_data.json` (and its per-universe variants, the data the
React app loads), watchlists, logs and scan metrics. Everything here except this README is
generated and gitignored.

The code that writes these files lives in `core/pipeline/screening/` (`dashboard.py`,
`terminal.py`, `scan_job.py`). Research evidence that used to be force-added here lives in
`research/`.
