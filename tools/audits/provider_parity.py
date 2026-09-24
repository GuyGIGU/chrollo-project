"""
Provider-parity harness — proves a candidate market-data vendor is safe to swap
in for the incumbent (Yahoo) BEFORE it ever feeds a real or archiveable scan.

A vendor swap is a *recalibration* event, not a clean infra swap: the engine's
structural thresholds are tuned against the incumbent's adjusted OHLC series, so
a different split/dividend adjustment can silently move boxes, LPS reads, and
tiers. Coverage/speed/cost benchmarks miss this entirely. This harness answers
the only question that gates the swap: **does the engine produce the same read on
the same stock from the new vendor's data?**

It compares two "sources" on two layers:

  1. PRICE PARITY  — per-ticker, per-field relative diffs over the overlapping
     dates, plus a constant-ratio fingerprint that flags an *adjustment-convention
     mismatch* (the whole series off by a near-constant multiple — the classic
     "vendor B back-adjusts splits differently" tell that perturbs geometry).

  2. ENGINE PARITY — runs the REAL per-ticker pipeline (`_evaluate_ticker`) on
     each source's frames and diffs the same canonical output fields the shadow
     guard freezes (Setup/Score/Tier/box/LPS/R/S/trigger). Both sides are fed
     IDENTICAL market scalars (computed from the left/reference panel) so a
     divergence reflects per-ticker OHLC geometry, not a global breadth/SPY shift.
     This is the verdict layer; price parity is the diagnosis.

A "source" is one of:
  - ``cache``            the live incumbent parquet (settings.CACHE_FILENAME); no fetch
  - ``<provider-name>``  a registered provider (core.pipeline.market_data.providers), fetched live
  - ``<path>.parquet``   a frozen snapshot written earlier by ``--snapshot``

Usage:
    # Freeze today's incumbent as the reference side (non-disruptive read of the cache)
    python -m tools.audits.provider_parity --snapshot --source cache \
        --tickers AAPL MSFT NVDA --out output/parity_ref.parquet

    # Compare a candidate vendor against that frozen reference
    python -m tools.audits.provider_parity --compare \
        --left output/parity_ref.parquet --right eodhd \
        --tickers AAPL MSFT NVDA

    # Smoke-test the harness end-to-end with only Yahoo wired (both sides identical)
    python -m tools.audits.provider_parity --compare --left cache --right yahoo --tickers AAPL MSFT

Exit codes: 0 = pass; 1 = drift (engine fire-flip / canonical field change, OR a
systematic constant-ratio price mismatch); 2 = usage/data error.
"""
from __future__ import annotations

import argparse
import os
import sys

import numpy as np
import pandas as pd

try:  # works under both `python -m tools.audits.provider_parity` and `python tools/audits/provider_parity.py`
    from tools._bootstrap import configure_path, refuse_sealed_output
except ModuleNotFoundError:  # a direct script run: put the repo root on sys.path first
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from tools._bootstrap import configure_path, refuse_sealed_output

_PROJECT_ROOT = configure_path()

from config import settings
from engine_alpha.evaluation import EVAL_ERROR
from core.pipeline.market_data.providers import available_providers, get_provider
from core.pipeline.screening.screener import _evaluate_ticker
from tools.regression.shadow_diff import CANONICAL_FIELDS, canonical_fields

# Tolerances. PRICE_REL_TOL mirrors "noise" (sub-0.1% is rounding/feed jitter);
# ADJ_DRIFT_TOL matches the live split-probe threshold (settings.SPLIT_PROBE_
# DRIFT_THRESHOLD = 0.5%) — a near-constant ratio above it is an adjustment-
# convention mismatch, the geometry-perturbing case.
PRICE_REL_TOL = 0.001
ADJ_DRIFT_TOL = 0.005
PRICE_FIELDS = ("Open", "High", "Low", "Close")
_MIN_OVERLAP_BARS = 2


# ------------------------------------------------------------------
# Source resolution
# ------------------------------------------------------------------
def _index_symbols() -> list[str]:
    return list(getattr(settings, "INDEX_SYMBOLS", [settings.SPY_SYMBOL]))


def _subset_panel(panel: pd.DataFrame, tickers: list[str] | None) -> pd.DataFrame:
    """Keep only requested tickers (+ index symbols) when a ticker set is given."""
    if tickers is None:
        return panel
    keep = set(tickers) | set(_index_symbols())
    cols = [c for c in panel.columns if isinstance(c, tuple) and c[0] in keep]
    return panel.loc[:, cols]


def _read_parquet(path: str) -> pd.DataFrame:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Snapshot parquet not found: {path}")
    panel = pd.read_parquet(path, engine=settings.PARQUET_ENGINE)
    if hasattr(panel.index, "tz") and panel.index.tz is not None:
        panel.index = panel.index.tz_localize(None)
    return panel


def resolve_source(spec: str, tickers: list[str] | None) -> pd.DataFrame:
    """Turn a source spec (``cache`` / provider name / ``*.parquet``) into a panel."""
    if spec == "cache":
        cache_path = os.path.join(_PROJECT_ROOT, settings.CACHE_FILENAME)
        if not os.path.exists(cache_path):
            raise FileNotFoundError(
                f"Live cache not found at {cache_path} — run a scan first, or pass a "
                "provider name / snapshot parquet instead."
            )
        return _subset_panel(_read_parquet(cache_path), tickers)
    if spec.endswith(".parquet"):
        return _subset_panel(_read_parquet(spec), tickers)
    # Otherwise: a registered provider, fetched live.
    if spec not in available_providers():
        raise ValueError(
            f"Unknown source {spec!r}: expected 'cache', a snapshot '*.parquet', or "
            f"one of providers [{', '.join(available_providers())}]."
        )
    if not tickers:
        raise ValueError(f"--tickers is required to fetch from provider {spec!r}.")
    return get_provider(spec).fetch(tickers)


# ------------------------------------------------------------------
# Market scalars (mirrors shadow_diff.build_fixture; exact accuracy irrelevant —
# both engine runs get the SAME values, isolating per-ticker geometry).
# ------------------------------------------------------------------
def panel_scalars(panel: pd.DataFrame) -> tuple[float, float | None]:
    level0 = set(panel.columns.get_level_values(0))
    spy = settings.SPY_SYMBOL

    spy_6m = 0.0
    if spy in level0:
        spy_close = panel[spy]["Close"].dropna()
        if len(spy_close) > settings.RS_LOOKBACK_BARS:
            spy_6m = float(spy_close.iloc[-1] / spy_close.iloc[-settings.RS_LOOKBACK_BARS - 1] - 1.0)

    breadth_count = breadth_total = 0
    for t in level0:
        if t == spy:
            continue
        close = panel[t]["Close"].dropna()
        if len(close) >= 50:
            mean_50 = float(close.iloc[-50:].mean())
            if pd.notna(mean_50):
                breadth_total += 1
                if float(close.iloc[-1]) > mean_50:
                    breadth_count += 1
    breadth_pct = (breadth_count / breadth_total) if breadth_total else None
    return spy_6m, breadth_pct


# ------------------------------------------------------------------
# Layer 1 — price parity
# ------------------------------------------------------------------
def _field_rel_diff(left: pd.Series, right: pd.Series) -> tuple[float, float, int]:
    """Median and max |right-left|/|left| over the overlapping index; bar count."""
    l = left.dropna()
    r = right.dropna()
    idx = l.index.intersection(r.index)
    if len(idx) < _MIN_OVERLAP_BARS:
        return (float("nan"), float("nan"), len(idx))
    l = l.loc[idx].astype("float64")
    r = r.loc[idx].astype("float64")
    denom = l.abs().replace(0.0, np.nan)
    rel = ((r - l).abs() / denom).replace([np.inf, -np.inf], np.nan).dropna()
    if rel.empty:
        return (float("nan"), float("nan"), len(idx))
    return (float(rel.median()), float(rel.max()), len(idx))


def _adjustment_fingerprint(left_close: pd.Series, right_close: pd.Series) -> tuple[float, bool]:
    """Return (relative drift of the mean close ratio, is-near-constant).

    A near-constant ratio materially off 1.0 is an adjustment-convention mismatch
    (split/dividend back-adjustment differs), which shifts box/LPS geometry.
    """
    l = left_close.dropna()
    r = right_close.dropna()
    idx = l.index.intersection(r.index)
    if len(idx) < _MIN_OVERLAP_BARS:
        return (float("nan"), False)
    ratios = (r.loc[idx].astype("float64") / l.loc[idx].astype("float64"))
    ratios = ratios.replace([np.inf, -np.inf], np.nan).dropna()
    if len(ratios) < _MIN_OVERLAP_BARS:
        return (float("nan"), False)
    ratio_mean = float(ratios.mean())
    ratio_std = float(ratios.std()) if len(ratios) > 1 else 0.0
    rel_drift = abs(ratio_mean - 1.0)
    is_constant = ratio_std < max(0.001, 0.2 * rel_drift)
    return (rel_drift, is_constant)


def price_parity(left: pd.DataFrame, right: pd.DataFrame, tickers: list[str]) -> dict:
    """Per-ticker OHLC(+Volume) diff summary classifying each as clean / drift /
    adjustment-mismatch / no-overlap / missing-a-side."""
    left0 = set(left.columns.get_level_values(0))
    right0 = set(right.columns.get_level_values(0))

    rows: list[dict] = []
    missing: list[str] = []
    for t in tickers:
        if t not in left0 or t not in right0:
            missing.append(t)
            continue
        worst_ohlc = 0.0
        overlap = 0
        for field in PRICE_FIELDS:
            try:
                _, mx, n = _field_rel_diff(left[t][field], right[t][field])
            except KeyError:
                continue
            overlap = max(overlap, n)
            if not np.isnan(mx):
                worst_ohlc = max(worst_ohlc, mx)
        vol_med = float("nan")
        if ("Volume" in left[t].columns) and ("Volume" in right[t].columns):
            vol_med, _, _ = _field_rel_diff(left[t]["Volume"], right[t]["Volume"])
        drift, is_constant = _adjustment_fingerprint(left[t]["Close"], right[t]["Close"])
        adjustment_mismatch = (not np.isnan(drift)) and drift > ADJ_DRIFT_TOL and is_constant

        if overlap < _MIN_OVERLAP_BARS:
            verdict = "no_overlap"
        elif adjustment_mismatch:
            verdict = "adjustment_mismatch"
        elif worst_ohlc > PRICE_REL_TOL:
            verdict = "drift"
        else:
            verdict = "clean"
        rows.append({
            "ticker": t,
            "verdict": verdict,
            "worst_ohlc_rel": worst_ohlc,
            "overlap_bars": overlap,
            "close_ratio_drift": drift,
            "constant_ratio": is_constant,
            "volume_med_rel": vol_med,
        })
    return {"rows": rows, "missing": missing}


# ------------------------------------------------------------------
# Layer 2 — engine parity (the verdict)
# ------------------------------------------------------------------
def _diff_canonical(left_res: dict, right_res: dict) -> list[tuple[str, object, object]]:
    lf, rf = canonical_fields(left_res), canonical_fields(right_res)
    return [(k, lf.get(k), rf.get(k)) for k in CANONICAL_FIELDS if lf.get(k) != rf.get(k)]


def engine_parity(left: pd.DataFrame, right: pd.DataFrame, tickers: list[str],
                  spy_6m: float, breadth: float | None) -> dict:
    """Run the real pipeline on both sides with shared scalars; classify each
    ticker as same / differ / fire-flip / neither."""
    left0 = set(left.columns.get_level_values(0))
    right0 = set(right.columns.get_level_values(0))

    same: list[str] = []
    differ: list[dict] = []
    left_only: list[str] = []
    right_only: list[str] = []
    neither: list[str] = []

    for t in tickers:
        if t not in left0 or t not in right0:
            continue
        lframe = left[t].dropna()
        rframe = right[t].dropna()
        lres = _evaluate_ticker(t, lframe, spy_6m, breadth)
        rres = _evaluate_ticker(t, rframe, spy_6m, breadth)
        # EVAL_ERROR (a swallowed eval crash) counts as NOT-fired, exactly like
        # None: the engine could not read the ticker, so it is dropped rather
        # than diffed. It is an Enum (no ``.get``), so it must never reach
        # _diff_canonical -> canonical_fields, which would raise AttributeError.
        lfire = lres is not None and lres is not EVAL_ERROR
        rfire = rres is not None and rres is not EVAL_ERROR

        if not lfire and not rfire:
            neither.append(t)
        elif lfire and not rfire:
            left_only.append(t)
        elif rfire and not lfire:
            right_only.append(t)
        else:
            field_diffs = _diff_canonical(lres, rres)
            if field_diffs:
                differ.append({"ticker": t, "fields": field_diffs})
            else:
                same.append(t)

    drift = bool(differ or left_only or right_only)
    return {
        "same": sorted(same),
        "differ": differ,
        "left_only": sorted(left_only),
        "right_only": sorted(right_only),
        "neither": sorted(neither),
        "drift": drift,
    }


# ------------------------------------------------------------------
# Verdict — the gate. Fails on engine drift OR a systematic (constant-ratio)
# price mismatch. The latter is scale-invariant for box geometry so it can slip
# past engine parity on non-firing tickers, yet it still seams the archive
# (absolute R/S/trigger levels) and shifts any firing setup — so it must gate.
# ------------------------------------------------------------------
def verdict(price: dict, engine: dict) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if engine["drift"]:
        reasons.append("engine output drifted (fire-flip or canonical field change)")
    if any(r["verdict"] == "adjustment_mismatch" for r in price["rows"]):
        reasons.append("systematic price/adjustment mismatch (constant-ratio drift) - seams the archive")
    return (not reasons, reasons)


# ------------------------------------------------------------------
# Reporting
# ------------------------------------------------------------------
def _fmt_pct(x: float) -> str:
    return "n/a" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x * 100:.3f}%"


def print_report(left_spec: str, right_spec: str, price: dict, engine: dict,
                 left_scalars: tuple, right_scalars: tuple) -> None:
    bar = "=" * 70
    print(bar)
    print(f"  PROVIDER PARITY - left={left_spec!r}  vs  right={right_spec!r}")
    print(bar)

    ls, rs = left_scalars, right_scalars
    print("Market scalars (left feeds BOTH engine runs; right shown for reference):")
    print(f"  spy_6m : left {_fmt_pct(ls[0])}   right {_fmt_pct(rs[0])}")
    print(f"  breadth: left {_fmt_pct(ls[1])}   right {_fmt_pct(rs[1])}")
    print()

    # ---- price layer ----
    rows = price["rows"]
    buckets: dict[str, list[dict]] = {}
    for r in rows:
        buckets.setdefault(r["verdict"], []).append(r)
    print(f"PRICE PARITY - {len(rows)} ticker(s) compared")
    for v in ("clean", "drift", "adjustment_mismatch", "no_overlap"):
        print(f"  {v:20s}: {len(buckets.get(v, []))}")
    if price["missing"]:
        print(f"  {'missing-a-side':20s}: {len(price['missing'])} "
              f"({', '.join(price['missing'][:12])}{'...' if len(price['missing']) > 12 else ''})")
    offenders = sorted(
        (r for r in rows if r["verdict"] in ("drift", "adjustment_mismatch")),
        key=lambda r: (r["verdict"] != "adjustment_mismatch", -r["worst_ohlc_rel"]),
    )
    if offenders:
        print("  worst offenders:")
        for r in offenders[:12]:
            extra = ""
            if r["verdict"] == "adjustment_mismatch":
                extra = f"  [constant close-ratio drift {_fmt_pct(r['close_ratio_drift'])}]"
            print(f"    {r['ticker']:8s} {r['verdict']:20s} "
                  f"worstOHLC={_fmt_pct(r['worst_ohlc_rel'])} "
                  f"vol_med={_fmt_pct(r['volume_med_rel'])}{extra}")
    print()

    # ---- engine layer (verdict) ----
    print("ENGINE PARITY - real pipeline on each side, shared scalars")
    print(f"  both fire, identical : {len(engine['same'])}")
    print(f"  both fire, DIFFER    : {len(engine['differ'])}")
    print(f"  left-only (drop)     : {len(engine['left_only'])}"
          f"{'  ' + ', '.join(engine['left_only'][:12]) if engine['left_only'] else ''}")
    print(f"  right-only (new)     : {len(engine['right_only'])}"
          f"{'  ' + ', '.join(engine['right_only'][:12]) if engine['right_only'] else ''}")
    print(f"  neither fires        : {len(engine['neither'])}")
    if engine["differ"]:
        print("  canonical field drift:")
        for d in engine["differ"][:20]:
            deltas = ", ".join(f"{k}: {a} -> {b}" for k, a, b in d["fields"])
            print(f"    {d['ticker']:8s} {deltas}")
    print()

    ok, reasons = verdict(price, engine)
    print(bar)
    if ok:
        print("  PASS - identical engine reads and no systematic price mismatch.")
    else:
        print("  FAIL - this vendor would change what the screener sees and/or stores;")
        print("         recalibrate + re-backfill before adopting. Reasons:")
        for r in reasons:
            print(f"           - {r}")
    print(bar)


# ------------------------------------------------------------------
# CLI
# ------------------------------------------------------------------
def _compare_tickers(left: pd.DataFrame, right: pd.DataFrame,
                     explicit: list[str] | None) -> list[str]:
    if explicit:
        return sorted(dict.fromkeys(explicit))
    common = set(left.columns.get_level_values(0)) & set(right.columns.get_level_values(0))
    return sorted(common)


def run_compare(left_spec: str, right_spec: str, tickers: list[str] | None) -> bool:
    left = resolve_source(left_spec, tickers)
    right = resolve_source(right_spec, tickers)

    cmp_all = _compare_tickers(left, right, tickers)
    index_syms = set(_index_symbols())
    engine_tickers = [t for t in cmp_all if t not in index_syms]  # indexes aren't screened

    left_scalars = panel_scalars(left)
    right_scalars = panel_scalars(right)

    price = price_parity(left, right, cmp_all)
    engine = engine_parity(left, right, engine_tickers, left_scalars[0], left_scalars[1])

    print_report(left_spec, right_spec, price, engine, left_scalars, right_scalars)
    return verdict(price, engine)[0]


def run_snapshot(source: str, tickers: list[str] | None, out: str) -> None:
    refuse_sealed_output(out)   # pre-flight: fail before any fetch (EC-14)
    panel = resolve_source(source, tickers)
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    panel.to_parquet(out, engine=settings.PARQUET_ENGINE, compression=settings.PARQUET_COMPRESSION)
    n_tickers = len(set(panel.columns.get_level_values(0)))
    print(f"Snapshot written: {n_tickers} ticker(s) x {len(panel)} bars from "
          f"source={source!r} -> {out}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Provider-parity harness for the screener data feed.")
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--compare", action="store_true",
                      help="Diff two sources on price + engine output")
    mode.add_argument("--snapshot", action="store_true",
                      help="Freeze a source's panel to a parquet for later comparison")
    ap.add_argument("--left", default="cache", help="Compare: left/reference source (default: cache)")
    ap.add_argument("--right", help="Compare: right/candidate source")
    ap.add_argument("--source", help="Snapshot: source to freeze (cache / provider / *.parquet)")
    ap.add_argument("--out", help="Snapshot: output parquet path")
    ap.add_argument("--tickers", nargs="*", default=None,
                    help="Ticker set to compare/snapshot (defaults to the panels' overlap on --compare)")
    args = ap.parse_args()

    try:
        if args.snapshot:
            if not args.source or not args.out:
                ap.error("--snapshot requires --source and --out")
            run_snapshot(args.source, args.tickers, args.out)
        else:
            if not args.right:
                ap.error("--compare requires --right")
            ok = run_compare(args.left, args.right, args.tickers)
            sys.exit(0 if ok else 1)
    except (FileNotFoundError, ValueError, RuntimeError) as e:
        print(f"error: {e}")
        sys.exit(2)


if __name__ == "__main__":
    main()
