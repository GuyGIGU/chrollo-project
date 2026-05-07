# Chrollo

Wyckoff VCP/LPS screener. Live pipeline lives in `core/screener_v2.py`; legacy and experimental code live in `Screeners/` and `experiments/` for reference.

## Layout

- `core/` — active screener pipeline (`screener_v2.py`)
- `Screeners/` — legacy screener (kept for reference)
- `config/` — settings and ticker universe
- `output/` — generated dashboard data, watchlists, logs (large data files are gitignored)
- `webapp/` — FastAPI backend + frontend for trading journal / IBKR integration
- `experiments/` — exploratory / dead-end code

## Setup

```powershell
pip install -r requirements.txt
```

## Run

```powershell
python run_screener.py
```
