"""Build the ``universe_returns`` dataset that unblocks the base-rate null model.

Read-only, offline. Emits a parquet of ``(scan_date, ticker, mfe_20d)``: for each
scan_date on which the live archive has a MATURED screener episode, the 20d forward
MFE of that day's ELIGIBLE universe — every cached name that passed
``apply_baseline_filters`` as-of the scan bar (the "random liquid stock I could have
picked that day" denominator). MFE is computed with the archive's OWN math
(``core.archive.forward_returns._compute_returns``) so the comparison in
``core.backtest.null_model`` is apples-to-apples.

Run:
    python -m tools.build_universe_returns --out output/universe_returns.parquet

Then feed it to the harness:
    python -m tools.backtest_engine --universe output/universe_returns.parquet --json out.json

Read-only against the production archive (``mode=ro``) and the price cache; the only
thing written is the parquet you name — which may NOT be ``trading_journal.db`` nor
sit under ``webapp/backend``. Deterministic: no RNG, sorted iteration + output.

Survivorship caveat: the 5y cache holds only CURRENT survivors, so the eligible
universe is missing names that later delisted (disproportionately losers). That
inflates the null's median MFE, which makes the resulting edge a CONSERVATIVE lower
bound — the edge sign / ranking is trustworthy, the absolute null level is not.
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import logging
import os

import pandas as pd

try:  # works under `python -m tools.build_universe_returns` and bare-script
    from tools._bootstrap import configure_path, refuse_sealed_output
except ModuleNotFoundError:
    from _bootstrap import configure_path, refuse_sealed_output  # type: ignore

_PROJECT_ROOT = configure_path()

from config import settings
from core.archive.forward_returns import _compute_returns, _ticker_frame
from core.backtest.loader import load_episodes
from engine_alpha.evaluation import apply_baseline_filters
from core.pipeline.universe import DEFAULT_UNIVERSE_TYPE

log = logging.getLogger("chrollo.tools.build_universe_returns")

CACHE_FILE = os.path.join(_PROJECT_ROOT, "market_data_cache_5y.parquet")
META_FILE = os.path.join(_PROJECT_ROOT, "cache_meta.json")
METRIC_COL = "mfe_20d"


def _validate_out(out_path: str) -> str:
    """Refuse to clobber the live DB, the price cache, or anything under
    webapp/backend; require .parquet. Sealed-dir/corpus knowledge lives in
    the ONE shared guard (EC-3/EC-14) — this adds only this tool's inputs."""
    ap = os.path.abspath(refuse_sealed_output(out_path))
    base = os.path.basename(ap).lower()
    if base == "trading_journal.db":
        raise SystemExit("refusing: output must not be named trading_journal.db")
    # Never overwrite the as-traded price cache (or its sector/commodity siblings)
    # or the cache metadata sidecar — those are read-only inputs to this tool.
    if (base == "cache_meta.json"
            or fnmatch.fnmatch(base, "market_data_cache_5y*.parquet")):
        raise SystemExit("refusing: output must not overwrite the price cache "
                         "(market_data_cache_5y*.parquet / cache_meta.json)")
    backend = os.path.abspath(os.path.join(_PROJECT_ROOT, "webapp", "backend"))
    if ap.lower() == backend.lower() or ap.lower().startswith(backend.lower() + os.sep):
        raise SystemExit("refusing: output path is under webapp/backend (read-only zone)")
    if not ap.lower().endswith(".parquet"):
        raise SystemExit("refusing: output must be a .parquet file")
    return ap


def _read_parquet(path: str) -> pd.DataFrame:
    engine = getattr(settings, "PARQUET_ENGINE", None)
    return pd.read_parquet(path, engine=engine) if engine else pd.read_parquet(path)


def _load_cache() -> pd.DataFrame:
    """Load the as-traded 5y price cache once (wide (ticker, field) panel)."""
    if not os.path.exists(CACHE_FILE):
        raise SystemExit(f"price cache not found: {CACHE_FILE}")
    # Regime guard — mixing dividend-adjusted rows would corrupt the MFE basis.
    with open(META_FILE, encoding="utf-8") as f:
        meta = json.load(f)
    regime = meta.get("price_series")
    if regime != "as_traded":
        raise SystemExit(f"cache price_series is {regime!r}, expected 'as_traded' — aborting")
    panel = _read_parquet(CACHE_FILE)
    if getattr(panel.index, "tz", None) is not None:
        panel.index = panel.index.tz_localize(None)
    # Incremental patching can leave duplicate (ticker, field) columns; keep the last.
    panel = panel.loc[:, ~panel.columns.duplicated(keep="last")]
    return panel


def _matured_scan_dates(source: str) -> list[str]:
    """Distinct scan_dates on which the episode-collapsed screener has a matured
    mfe_20d — the exact grid the null model matches on."""
    eps = load_episodes(source=source, universe_type=DEFAULT_UNIVERSE_TYPE)
    if METRIC_COL not in eps.columns:
        raise SystemExit(f"archive episodes lack '{METRIC_COL}' — nothing matured to compare")
    matured = eps[pd.to_numeric(eps[METRIC_COL], errors="coerce").notna()]
    dates = sorted({str(d) for d in matured["scan_date"]})
    log.info("matured screener scan_dates: %d (from %d episodes)", len(dates), len(eps))
    return dates


def _universe_mfe_for_date(frames: dict[str, pd.DataFrame], scan_date: str) -> list[tuple]:
    """Per eligible ticker on ``scan_date``, its 20d forward MFE (archive math).

    ``frames`` is the pre-extracted {ticker -> full frame} cache from ``build``
    (each frame extracted once total, not once per scan_date)."""
    scan_ts = pd.Timestamp(scan_date)
    rows: list[tuple] = []
    for ticker, df in frames.items():
        if df.empty:
            continue
        df_slice = df[df.index <= scan_ts]
        if len(df_slice) < 200:
            continue  # short history — apply_baseline_filters would reject anyway
        if apply_baseline_filters(df_slice) is None:
            continue  # not eligible as-of this date (price/vol/trend/return gate)
        scan_close = float(df_slice["Close"].iloc[-1])
        if scan_close <= 0:
            continue
        fwd_df = df[df.index > scan_ts]
        if fwd_df.empty:
            continue
        res = _compute_returns(fwd_df, scan_close, None)  # trigger/s_level absent -> only MFE/MAE
        m = res.get(METRIC_COL)
        if m is None:
            continue  # < 20 forward bars -> immature; never zero-fill
        rows.append((scan_date, ticker, float(m)))
    return rows


def build(out_path: str, source: str = "screener") -> pd.DataFrame:
    out = _validate_out(out_path)
    scan_dates = _matured_scan_dates(source)
    if not scan_dates:
        raise SystemExit("no matured screener scan_dates — nothing to build")
    panel = _load_cache()
    tickers = sorted(set(panel.columns.get_level_values(0)) - {"SPY"})
    log.info("cache universe: %d tickers over %d scan_dates", len(tickers), len(scan_dates))

    # Extract each ticker's frame ONCE (was re-extracted per scan_date x ticker).
    # Insertion order follows the sorted ``tickers``; the final sort_values keeps
    # output order independent of this anyway.
    frames = {t: _ticker_frame(panel, t) for t in tickers}

    all_rows: list[tuple] = []
    for i, d in enumerate(scan_dates, 1):
        rows = _universe_mfe_for_date(frames, d)
        all_rows.extend(rows)
        log.info("[%d/%d] %s: %d eligible names with mfe_20d", i, len(scan_dates), d, len(rows))

    frame = pd.DataFrame(all_rows, columns=["scan_date", "ticker", METRIC_COL])
    frame = frame.sort_values(["scan_date", "ticker"]).reset_index(drop=True)
    engine = getattr(settings, "PARQUET_ENGINE", None)
    if engine:
        frame.to_parquet(out, engine=engine, index=False)
    else:
        frame.to_parquet(out, index=False)
    log.info("wrote %d rows -> %s", len(frame), out)
    return frame


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    ap = argparse.ArgumentParser(
        description="Build the eligible-universe MFE dataset (universe_returns) for the null model."
    )
    ap.add_argument("--out", required=True,
                    help="output .parquet (not under webapp/backend, not trading_journal.db)")
    ap.add_argument("--source", default="screener",
                    help="archive source whose matured scan_dates define the grid (default: screener)")
    args = ap.parse_args()
    frame = build(args.out, source=args.source)
    if not frame.empty:
        med = float(frame[METRIC_COL].median())
        print(f"\nuniverse_returns: {len(frame)} rows, {frame['scan_date'].nunique()} dates, "
              f"median {METRIC_COL} {med * 100:+.2f}%")
    else:
        print("\nuniverse_returns: 0 rows (no eligible names matured) — check per-date log above.")


if __name__ == "__main__":
    main()
