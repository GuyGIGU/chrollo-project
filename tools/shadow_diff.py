"""
Shadow-output diff guard - proves a code change did NOT silently alter the
screener's existing outputs.

It runs the REAL per-ticker pipeline (``core.pipeline.screener._evaluate_ticker``)
on a FROZEN input fixture (committed OHLCV frames + frozen market scalars),
serializes the canonical output fields per ticker, and compares against a
captured baseline.

Only the canonical fields are frozen - ticker set, setup type, score, tier,
R/S levels, trigger price, box width, LPS length, and the displayed ranking. Any
NEW diagnostic field a future change adds is ignored, so measure-first additions
never trip the guard. A drift in any canonical field is reported with the exact
ticker and field so an unintended change is impossible to miss.

Hermetic: reads the frozen fixture parquet, never the network. The fixture is
self-curating - ``--build-fixture`` keeps exactly the tickers that currently fire
among the candidates, so a ticker that later stops firing shows up as a drop.

Usage:
    python -m tools.shadow_diff --build-fixture   # one-time, after a real scan
    python -m tools.shadow_diff --capture          # snapshot current outputs as baseline
    python -m tools.shadow_diff --check            # fail (exit 1) on canonical-field drift
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys

import pandas as pd

try:  # works under both `python -m tools.shadow_diff` and `python tools/shadow_diff.py`
    from tools._bootstrap import configure_path
except ModuleNotFoundError:
    from _bootstrap import configure_path

_PROJECT_ROOT = configure_path()

from config import settings
from core.pipeline.evaluation import EVAL_ERROR
from core.pipeline.screener import _evaluate_ticker

_BASELINE_DIR = os.path.join(_PROJECT_ROOT, "tests", "baselines")
_FIXTURE_PARQUET = os.path.join(_BASELINE_DIR, "shadow_fixture.parquet")
_FIXTURE_SCALARS = os.path.join(_BASELINE_DIR, "shadow_fixture_scalars.json")
_BASELINE_PATH = os.path.join(_BASELINE_DIR, "shadow_baseline.json")
_DB_PATH = os.path.join(_PROJECT_ROOT, "webapp", "backend", "trading_journal.db")
_CACHE_PATH = os.path.join(_PROJECT_ROOT, settings.CACHE_FILENAME)

# The screener outputs frozen by the guard. New diagnostic fields are NOT here,
# so they are free to appear/differ without tripping it.
CANONICAL_FIELDS = (
    "Setup", "Score", "Tier", "Base Len", "Box Width", "LPS Length",
    "_R", "_S", "_trigger_price",
)


# ------------------------------------------------------------------
# Pure logic (unit-tested; no DB / no network)
# ------------------------------------------------------------------
def canonical_fields(result: dict) -> dict:
    """Project a screener result dict down to the frozen canonical fields.

    Floats are rounded to 6 dp so float-noise never reads as drift.
    """
    out: dict = {}
    for key in CANONICAL_FIELDS:
        val = result.get(key)
        if isinstance(val, float):
            val = round(val, 6)
        out[key] = val
    return out


def diff_against_baseline(current: dict, baseline: dict) -> tuple[bool, list[str]]:
    """Compare a fresh fixture run against a captured baseline.

    Returns ``(ok, lines)``. Fails on any canonical drift: a ticker that stopped
    firing (DROPPED), a ticker that newly fires (NEW - possibly intended, but
    surfaced so it can't change silently), a changed canonical field, or a
    changed ranking. New diagnostic fields are invisible here by construction.
    """
    lines: list[str] = []
    ok = True

    cur_f = current.get("fields", {})
    base_f = baseline.get("fields", {})
    cur_t, base_t = set(cur_f), set(base_f)

    dropped = sorted(base_t - cur_t)
    if dropped:
        ok = False
        lines.append(f"DROPPED ({len(dropped)}) - fired in baseline, not now: {', '.join(dropped)}")

    added = sorted(cur_t - base_t)
    if added:
        ok = False
        lines.append(f"NEW ({len(added)}) - fires now, absent from baseline (re-capture if intended): {', '.join(added)}")

    field_drift = 0
    for ticker in sorted(cur_t & base_t):
        for key in CANONICAL_FIELDS:
            a, b = base_f[ticker].get(key), cur_f[ticker].get(key)
            if a != b:
                ok = False
                field_drift += 1
                lines.append(f"  {ticker}.{key}: {a} -> {b}")
    if field_drift:
        lines.insert(
            len(lines) - field_drift,
            f"FIELD DRIFT ({field_drift}) - canonical values changed:",
        )

    if baseline.get("ranking") != current.get("ranking"):
        ok = False
        lines.append("RANKING changed:")
        lines.append(f"  baseline: {baseline.get('ranking')}")
        lines.append(f"  current:  {current.get('ranking')}")

    if ok:
        lines.append(f"no canonical drift - {len(cur_t)} firing tickers, all fields and ranking unchanged.")
    return ok, lines


# ------------------------------------------------------------------
# Fixture run (loads frozen parquet, runs the real pipeline)
# ------------------------------------------------------------------
def _load_fixture() -> tuple[dict[str, pd.DataFrame], dict]:
    if not os.path.exists(_FIXTURE_PARQUET) or not os.path.exists(_FIXTURE_SCALARS):
        raise FileNotFoundError(
            "No fixture - run `python -m tools.shadow_diff --build-fixture` first "
            "(requires a populated data cache from a real scan)."
        )
    data = pd.read_parquet(_FIXTURE_PARQUET, engine=settings.PARQUET_ENGINE)
    with open(_FIXTURE_SCALARS, "r", encoding="utf-8") as f:
        scalars = json.load(f)
    level0 = set(data.columns.get_level_values(0))
    frames = {t: data[t].dropna() for t in scalars["tickers"] if t in level0}
    return frames, scalars


def run_fixture() -> dict:
    """Run the real per-ticker pipeline over the frozen fixture.

    Returns ``{"fields": {ticker: canonical}, "ranking": [ticker, ...]}``.
    Ranking is a total order (score desc, ticker asc) so it is deterministic
    across runs regardless of dict/iteration order.
    """
    frames, scalars = _load_fixture()
    spy_6m = float(scalars.get("spy_6m_return", 0.0))
    breadth = scalars.get("breadth_pct")
    breadth = float(breadth) if breadth is not None else None

    fields: dict = {}
    scored: list[tuple[str, float]] = []
    for ticker in scalars["tickers"]:
        df = frames.get(ticker)
        if df is None:
            continue
        result = _evaluate_ticker(ticker, df, spy_6m, breadth)
        # EVAL_ERROR (a swallowed eval crash) is DROPPED exactly like None (a
        # structural reject): the guard measures output STABILITY, and a ticker
        # the engine can no longer evaluate is a dropped ticker, not a canonical
        # dict. Passing EVAL_ERROR (an Enum, no ``.get``) into canonical_fields
        # would raise AttributeError and crash the CI drift guard.
        if result is None or result is EVAL_ERROR:
            continue
        fields[ticker] = canonical_fields(result)
        scored.append((ticker, float(result["Score"])))

    ranking = [t for t, _ in sorted(scored, key=lambda x: (-x[1], x[0]))]
    return {"fields": fields, "ranking": ranking}


# ------------------------------------------------------------------
# Fixture build (one-time; reads the live data cache, writes frozen files)
# ------------------------------------------------------------------
def _recent_firing_tickers(db_path: str) -> list[str]:
    """Distinct tickers from the most recent archived screener scan (candidates)."""
    if not os.path.exists(db_path):
        return []
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        row = con.execute(
            "SELECT MAX(scan_date) FROM setup_archive WHERE source = 'screener'"
        ).fetchone()
        latest = row[0] if row else None
        if not latest:
            return []
        cur = con.execute(
            "SELECT DISTINCT ticker FROM setup_archive WHERE source = 'screener' AND scan_date = ?",
            (latest,),
        )
        return sorted(t for (t,) in cur.fetchall())
    finally:
        con.close()


def build_fixture(cache_path: str = _CACHE_PATH, db_path: str = _DB_PATH,
                  extra_tickers: list[str] | None = None) -> dict:
    """Freeze a fixture from the live data cache + the archive's firing set.

    Keeps only tickers that CURRENTLY fire among the candidates, so the baseline
    reflects real, non-empty pipeline output.
    """
    if not os.path.exists(cache_path):
        raise FileNotFoundError(
            f"Data cache not found at {cache_path} - run a real scan first "
            "(`python run_screener.py`) so the parquet exists."
        )
    data = pd.read_parquet(cache_path, engine=settings.PARQUET_ENGINE)
    level0 = set(data.columns.get_level_values(0))

    candidates = _recent_firing_tickers(db_path) + list(extra_tickers or [])
    candidates = [t for t in dict.fromkeys(candidates) if t in level0]
    if not candidates:
        raise RuntimeError(
            "No candidate tickers - the archive has no screener rows and no "
            "--tickers were passed. Run a scan (which archives results) first."
        )

    # Frozen market scalars. Exact production accuracy is irrelevant - the guard
    # only needs the SAME frozen values on capture and check; what it tests is
    # output STABILITY across code versions on identical inputs.
    spy = settings.SPY_SYMBOL
    spy_6m = 0.0
    if spy in level0:
        spy_close = data[spy]["Close"].dropna()
        if len(spy_close) > settings.RS_LOOKBACK_BARS:
            spy_6m = float(spy_close.iloc[-1] / spy_close.iloc[-settings.RS_LOOKBACK_BARS - 1] - 1.0)

    cand_frames = {t: data[t].dropna() for t in candidates}

    # Breadth over the WHOLE cached universe (not just candidates) so the frozen
    # value matches production semantics - candidates are all already-passing
    # stocks, so measuring breadth over them alone would read ~100%.
    breadth_count = breadth_total = 0
    for t in level0:
        if t == spy:
            continue
        close = data[t]["Close"].dropna()
        if len(close) >= 50:
            mean_50 = float(close.iloc[-50:].mean())
            if pd.notna(mean_50):
                breadth_total += 1
                if float(close.iloc[-1]) > mean_50:
                    breadth_count += 1
    breadth_pct = (breadth_count / breadth_total) if breadth_total else None

    firing = [t for t, df in cand_frames.items()
              if _evaluate_ticker(t, df, spy_6m, breadth_pct) is not None]
    if not firing:
        raise RuntimeError(
            f"None of the {len(candidates)} candidate tickers fire under the "
            "current engine - cannot build a meaningful fixture."
        )

    os.makedirs(_BASELINE_DIR, exist_ok=True)
    cols = [c for c in data.columns if c[0] in set(firing)]
    data.loc[:, cols].to_parquet(_FIXTURE_PARQUET, engine=settings.PARQUET_ENGINE)
    scalars = {
        "spy_6m_return": spy_6m,
        "breadth_pct": breadth_pct,
        "tickers": sorted(firing),
    }
    with open(_FIXTURE_SCALARS, "w", encoding="utf-8") as f:
        json.dump(scalars, f, indent=2)

    print(f"Built fixture: {len(firing)}/{len(candidates)} candidates fire -> {_FIXTURE_PARQUET}")
    print(f"  frozen scalars: spy_6m={spy_6m * 100:.2f}%, "
          f"breadth={'n/a' if breadth_pct is None else f'{breadth_pct * 100:.1f}%'}")
    return scalars


# ------------------------------------------------------------------
# Capture / check
# ------------------------------------------------------------------
def capture_baseline() -> dict:
    snapshot = run_fixture()
    os.makedirs(_BASELINE_DIR, exist_ok=True)
    with open(_BASELINE_PATH, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, indent=2)
    print(f"Captured shadow baseline -> {_BASELINE_PATH}")
    print(f"  {len(snapshot['fields'])} firing tickers, ranking of {len(snapshot['ranking'])}.")
    return snapshot


def check_baseline() -> bool:
    if not os.path.exists(_BASELINE_PATH):
        print(f"No baseline at {_BASELINE_PATH} - run with --capture first.")
        return False
    with open(_BASELINE_PATH, "r", encoding="utf-8") as f:
        baseline = json.load(f)

    current = run_fixture()
    ok, lines = diff_against_baseline(current, baseline)

    print("=" * 64)
    print("  SHADOW-OUTPUT GUARD - current pipeline vs. captured baseline")
    print("=" * 64)
    for line in lines:
        print(line)
    print()
    print("PASS - existing outputs unchanged." if ok
          else "FAIL - existing outputs drifted; see above.")
    return ok


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser(description="Shadow-output regression guard for the screener.")
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--build-fixture", action="store_true",
                       help="Freeze a fixture from the live data cache + archive firing set")
    group.add_argument("--capture", action="store_true",
                       help="Snapshot current canonical outputs as the baseline")
    group.add_argument("--check", action="store_true",
                       help="Fail (exit 1) if any canonical output drifted")
    ap.add_argument("--tickers", nargs="*", default=None,
                    help="Extra candidate tickers to include when building the fixture")
    args = ap.parse_args()

    try:
        if args.build_fixture:
            build_fixture(extra_tickers=args.tickers)
        elif args.capture:
            capture_baseline()
        elif args.check:
            sys.exit(0 if check_baseline() else 1)
    except (FileNotFoundError, RuntimeError) as e:
        print(str(e))
        sys.exit(2)


if __name__ == "__main__":
    main()
