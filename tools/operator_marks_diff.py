"""Operator trend-end / AR marks vs what the engine actually reads.

The instrument behind the 2026-08-14 ruling on ``AR_FIRST_REACTION_ENABLED``
(docs/anchor_marks_ruling_2026-08-14.md). That flag was RULED DELETED 2026-09-08,
so the flip half of this tool retired with it and what remains is the ANCHOR half
— which is the live instrument for the climax-anchor program, still open. Reads
the append-only marks corpus
``docs/trend_end_marks_2026-08.json`` and puts each operator mark next to the
engine's own Phase-A anchor and its ``segment_trends`` terminals, in DATES, on
the faithful live frame.

FAITHFULNESS: ``_prep_live`` below (baseline filter ->
_trim_to_period to DAILY_STRUCTURE_PERIOD (2y) -> ATR_10/50 -> atr =
ATR_10.iloc[-6]) and ``read_structure`` on that SAME frame, captured with
the live engine. Read-only: no network, no backend, no renders, nothing live
imports it.

What the summary measures:
  * distance from the operator's own AR (context, no longer a flip question);
  * whether ``segment_trends`` holds a terminal at his trend end at all, and
    whether the resolved climax is early or late — THE anchor question, and the
    reason this tool survived the flag's deletion.

Elections are not stable day to day: a name that fired when the marks were taken
may not fire today. Those fall back to the dates RECORDED in the corpus and are
labelled ``recorded`` in the source column — never silently mixed with a live
read. A name that is out of universe today (baseline-gated, e.g. IRMD/CYRX on
2026-08-14) is read on the ungated frame for its trend structure ONLY, and says so.

    python -m tools.operator_marks_diff
    python -m tools.operator_marks_diff --marks docs/trend_end_marks_2026-08.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys

_THIS = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.normpath(os.path.join(_THIS, ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import pandas as pd

from config import settings
from core.pipeline.market_data.downloads import _trim_to_period
from engine_alpha.evaluation import apply_baseline_filters
from engine_alpha.structure.metrics.indicators import calculate_atr
from engine_alpha.structure.events.market_structure import (
    read_market_structure, segment_trends)
from engine_alpha.structure.narrative.reader import read_structure
from tools._bootstrap import refuse_sealed_output
from tools.marks_json import load_marks_json, marks_json_fingerprint

_DEFAULT_MARKS = os.path.join(_ROOT, "docs", "trend_end_marks_2026-08.json")
_TERMINAL_TOL = 3          # bars: "segment_trends found his trend end"


def _load_cache():
    d = pd.read_parquet(settings.CACHE_FILENAME, engine=settings.PARQUET_ENGINE)
    return d, set(d.columns.get_level_values(0))


def _prep_live(raw: pd.DataFrame):
    """The exact daily frame the screener reads: baseline filter, trim to
    DAILY_STRUCTURE_PERIOD, ATR cols. Mirrors evaluation._evaluate_ticker.
    Returns (df, atr) or (None, reason).

    Moved here verbatim 2026-09-08 from ``tools/ar_first_reaction_diff.py`` when
    that module was deleted with ``AR_FIRST_REACTION_ENABLED``. It is frame prep,
    not AR machinery, and this tool's surviving half needs it."""
    base = apply_baseline_filters(raw.copy())
    if base is None:
        return None, "rejected at baseline filters"
    df, _ = base
    df = _trim_to_period(df, settings.DAILY_STRUCTURE_PERIOD).copy()
    if len(df) < settings.STRUCTURE_ATR_SAMPLE_OFFSET:
        return None, "too few bars after trim"
    df["ATR_10"] = calculate_atr(df, 10)
    df["ATR_50"] = calculate_atr(df, 50)
    atr = float(df["ATR_10"].iloc[-settings.STRUCTURE_ATR_SAMPLE_OFFSET])
    if not (atr > 0):
        return None, "non-positive ATR snapshot"
    return df, atr


def _ungated_frame(raw):
    """The same trim WITHOUT the universe gate — a baseline-gated ticker can
    still be read for its trend structure (the gate filters the universe, it is
    not part of the reader)."""
    df = _trim_to_period(raw.copy(), settings.DAILY_STRUCTURE_PERIOD).copy()
    df["ATR_10"] = calculate_atr(df, 10)
    df["ATR_50"] = calculate_atr(df, 50)
    return df, float(df["ATR_10"].iloc[-settings.STRUCTURE_ATR_SAMPLE_OFFSET])


def _bar_of(df, iso):
    """Index of the bar closest to an ISO date (marks are calendar dates; a
    mark on a holiday still names the session either side of it)."""
    if not iso:
        return None
    idx = df.index.tz_localize(None) if getattr(df.index, "tz", None) else df.index
    return int(abs(idx - pd.Timestamp(iso)).argmin())


def _date_of(df, bar):
    return None if bar is None else str(pd.Timestamp(df.index[int(bar)]).date())


def measure(mark, cache_col):
    """One row: the operator's marks and the engine's, resolved to bars on one
    frame. Returns a dict, or None when the ticker cannot be framed at all."""
    raw = cache_col.dropna()
    gated = False
    prepped = _prep_live(raw)
    df, atr = prepped
    if df is None:
        df, atr = _ungated_frame(raw)
        gated = True

    off = read_structure(df, atr)
    rec = mark.get("engine_2026_08_14", {})

    if off is not None:
        source = "live"
        cx = int(off.climax_bar)
        ar_off = int(off.ar_bar)
        box_start = int(off.box.start_bar)
    else:
        source = "recorded"
        cx = _bar_of(df, rec.get("climax"))
        ar_off = _bar_of(df, rec.get("ar_off"))
        box_start = _bar_of(df, rec.get("box_start"))

    op_cx = _bar_of(df, mark.get("trend_end"))
    op_ar = _bar_of(df, mark.get("ar"))

    terminals = [int(s["terminal_bar"])
                 for s in segment_trends(read_market_structure(df).get("points", []))]
    found = (op_cx is not None
             and any(abs(t - op_cx) <= _TERMINAL_TOL for t in terminals))

    return {
        "ticker": mark["ticker"], "source": source, "gated": gated,
        "op_trend_end": mark.get("trend_end"), "op_ar": mark.get("ar"),
        "derived": mark.get("trend_end_source") == "derived",
        "climax": _date_of(df, cx), "ar_off": _date_of(df, ar_off),
        "box_start": _date_of(df, box_start),
        "d_climax": None if (cx is None or op_cx is None) else cx - op_cx,
        "d_ar_off": None if (ar_off is None or op_ar is None) else ar_off - op_ar,
        "ar_is_box_open": (ar_off is not None and ar_off == box_start),
        "terminal_at_trend_end": found,
    }


def _median(vals):
    """True median — the even case averages the middle pair, so the printed
    figure matches the one quoted in docs/anchor_marks_ruling_2026-08-14.md."""
    s = sorted(vals)
    mid = len(s) // 2
    return s[mid] if len(s) % 2 else (s[mid - 1] + s[mid]) / 2


def report(rows):
    print(f"\n  {'ticker':<7} {'src':<9} {'his end':<11} {'his AR':<11} "
          f"{'climax':<11} {'dCx':>5}  {'AR off':<11} {'d':>5}  {'AR on':<11} {'d':>5}")
    print("  " + "-" * 104)
    n = lambda v: "" if v is None else f"{v:+d}"
    s = lambda v: v or "-"
    for r in rows:
        print(f"  {r['ticker']:<7} {r['source']:<9} {s(r['op_trend_end']):<11} "
              f"{s(r['op_ar']):<11} {s(r['climax']):<11} {n(r['d_climax']):>5}  "
              f"{s(r['ar_off']):<11} {n(r['d_ar_off']):>5}")

    ar = [abs(r["d_ar_off"]) for r in rows if r["d_ar_off"] is not None]
    if ar:
        print("")
        print("  DISTANCE FROM HIS OWN AR (%d names)" % len(ar))
        print(f"    total |error| : {sum(ar):>4} bars   median {_median(ar):.4g}")

    # Derived trend ends were read back off an engine dot (ar_off == box.start_bar),
    # so scoring the engine against them measures the engine against itself. They
    # are reported, never counted.
    dated = [r for r in rows if r["op_trend_end"] and not r["derived"]]
    found = sum(1 for r in dated if r["terminal_at_trend_end"])
    cx = [r["d_climax"] for r in dated if r["d_climax"] is not None]
    print(f"\n  THE ANCHOR QUESTION  (operator-typed dates only)")
    print(f"    segment_trends holds a terminal within {_TERMINAL_TOL} bars of his "
          f"trend end : {found} of {len(dated)}")
    if cx:
        early = sum(1 for v in cx if v < 0)
        print(f"    resolved climax EARLIER than his trend end          : "
              f"{early} of {len(cx)}   (median {_median(cx):+.4g} bars)")
    derived = [r["ticker"] for r in rows if r["derived"]]
    if derived:
        print(f"    excluded as CIRCULAR (trend end read off an engine dot): "
              f"{' '.join(derived)}")
    box_open = [r for r in rows if r["source"] == "live"]
    if box_open:
        eq = sum(1 for r in box_open if r["ar_is_box_open"])
        print(f"    drawn OFF ar_bar == box.start_bar                   : "
              f"{eq} of {len(box_open)} live reads")
    gated = [r["ticker"] for r in rows if r["gated"]]
    if gated:
        print(f"\n  out of universe today (baseline-gated, trend read only): "
              f"{' '.join(gated)}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--marks", default=_DEFAULT_MARKS,
                    help="marks corpus JSON (default docs/trend_end_marks_2026-08.json)")
    ap.add_argument("--json", metavar="PATH", help="also dump the rows as JSON")
    a = ap.parse_args()

    marks = load_marks_json(a.marks)
    d, level0 = _load_cache()

    rows = []
    scored = []
    for mark in marks:
        t = mark["ticker"]
        if t not in level0:
            print(f"  [skip {t}] not in cache")
            continue
        try:
            row = measure(mark, d[t])
        except Exception as e:                       # one bad frame never stops the sweep
            print(f"  [skip {t}] {type(e).__name__}: {e}")
            continue
        if row:
            rows.append(row)
            scored.append(mark)

    # EC-13: every marks-consuming report stamps its population name and the
    # fingerprint of EXACTLY the set it scored — this tool FILTERS (cache
    # absences and failed frames skip), so the stamp binds the post-filter
    # set, on the stdout report AND the JSON dump (2026-08-17 review, Hunt).
    population = os.path.basename(a.marks)
    fp = marks_json_fingerprint(scored)
    print(f"\n  population {population} · scored {len(scored)}/{len(marks)} "
          f"marks · fingerprint {fp[:12]}")
    report(rows)
    if a.json:
        with open(refuse_sealed_output(a.json), "w", encoding="utf-8") as fh:
            json.dump({"population": population, "marks_fingerprint": fp,
                       "scored": len(scored), "loaded": len(marks),
                       "rows": rows}, fh, indent=2)
        print(f"\n  wrote {a.json}")


if __name__ == "__main__":
    main()
