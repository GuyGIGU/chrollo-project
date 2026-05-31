# Chrollo

Wyckoff VCP/LPS screener. The engine is split into two clean halves plus a conductor —
see [core/MAP.md](core/MAP.md) for the plain-English tour.

## Layout

- `core/` — the screener engine, organized by role:
  - `core/structure/` — **Visual Structure Engine**: pure geometry/measurement (boxes, LPS, contractions). No opinion.
  - `core/scoring/` — **Scoring Engine**: turns measured facts into points + a tier. All knobs live in `config/settings.py`.
  - `core/pipeline/` — **the conductor**: data loading + per-ticker orchestration that wires structure → scoring.
  - `core/archive/` — **the measuring stick**: record outcomes, backfill forward returns, analyze winners.
- `config/` — settings and ticker universe
- `output/` — generated dashboard data, watchlists, logs (large data files are gitignored)
- `webapp/` — FastAPI backend + frontend for trading journal / IBKR integration
- `tools/` — dev/backtest harnesses (not part of the live run)

## Setup

```powershell
pip install -r requirements.txt
```

## Run

```powershell
python run_screener.py
```
