"""
Phase-B candidate-selection A/B — the "meat test" for Change B.

Runs the REAL per-ticker pipeline over the frozen shadow fixture twice:
  - select="best"     : today's behavior (global-best combined-score pair)
  - select="earliest" : root the outer box at the earliest valid range start

and reports the blast radius — which firing tickers DROP, which NEWLY fire, and
for the survivors how Score / Tier / R / S / Base Len / Box Width / LPS Length
move. This is "today's scan vs the new one" on the current firing universe,
fully offline (frozen parquet, no network).

Read-only: changes nothing, captures nothing. Just shows the gap so we can
decide whether earliest-valid is a net improvement before flipping the default.

    python -m tools.phaseb_ab
"""
from __future__ import annotations

import os
import sys

_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from config import settings
from core.pipeline.screener import apply_baseline_filters, _evaluate_ticker
from core.structure.consolidation import find_consolidation, find_outer_box
from core.structure.indicators import calculate_atr
from tools.shadow_diff import _load_fixture

# Fields we report movement on (superset of the shadow-diff canonical set, plus
# the scoping diagnostics this change is meant to improve).
_NUM_FIELDS = ("Score", "Base Len", "Box Width", "LPS Length", "_R", "_S")
_TAG_FIELDS = ("Setup", "Tier")


def _run(select: str) -> dict:
    frames, scalars = _load_fixture()
    spy_6m = float(scalars.get("spy_6m_return", 0.0))
    breadth = scalars.get("breadth_pct")
    breadth = float(breadth) if breadth is not None else None

    out: dict = {}
    for ticker in scalars["tickers"]:
        df = frames.get(ticker)
        if df is None:
            continue
        res = _evaluate_ticker(ticker, df, spy_6m, breadth, select=select)
        if res is not None:
            out[ticker] = res
    return out


def _fmt(v) -> str:
    if isinstance(v, float):
        return f"{v:.2f}"
    return str(v)


def _trace(tickers: list[str]) -> None:
    """Deep per-ticker structural trace: the consolidation tuple + fire result
    under both selection rules, so a drop/downgrade can be reasoned about."""
    frames, scalars = _load_fixture()
    spy_6m = float(scalars.get("spy_6m_return", 0.0))
    breadth = scalars.get("breadth_pct")
    breadth = float(breadth) if breadth is not None else None

    for ticker in tickers:
        raw = frames.get(ticker)
        print("=" * 70)
        print(f"  {ticker}")
        print("=" * 70)
        if raw is None:
            print("  (not in fixture)")
            continue
        base = apply_baseline_filters(raw.copy())
        if base is None:
            print("  baseline filter rejects")
            continue
        df, _yr = base
        df = df.copy()
        df["ATR_10"] = calculate_atr(df, 10)
        df["ATR_50"] = calculate_atr(df, 50)
        n = len(df)
        for sel in ("best", "earliest"):
            t = find_consolidation(df, min_days=settings.MIN_BASE_DAYS, select=sel)
            base_len, R, S, bw = t[0], t[1], t[2], t[3]
            rt, st = t[4], t[5]
            is_inner = t[11]
            pbs = n - base_len
            close = float(df["Close"].iloc[-1])
            res = _evaluate_ticker(ticker, frames[ticker], spy_6m, breadth, select=sel)
            print(f"  [{sel:8}] base_len={base_len:3}  R={R:.2f} S={S:.2f}  "
                  f"box={bw:.3f}  touches r/s={rt}/{st}  inner={is_inner}  "
                  f"phase_b_start_bar={pbs}  close={close:.2f}  "
                  f"fires={'YES' if res else 'no'}"
                  + (f" (Score {res['Score']:.1f} {res['Tier']})" if res else ""))
        # extension / crash filter context (common drop reasons)
        print(f"  close vs filters: crash<{S * settings.CRASH_FILTER_MULT:.2f}  "
              f"extension>={R * settings.EXTENSION_FILTER_MULT:.2f}")

        # Full candidate landscape for the chosen anchor (sorted earliest-first).
        cands = find_outer_box(df, min_days=settings.MIN_BASE_DAYS, select="debug")
        if cands:
            best_combined = max(c["combined"] for c in cands)
            print(f"  candidate landscape ({len(cands)} valid pairs, earliest-first):")
            print(f"    {'start':>5} {'baseLen':>7} {'box':>6} {'r/s':>7} "
                  f"{'combined':>8} {'%ofBest':>7}")
            for c in cands:
                pct = 100.0 * c["combined"] / best_combined if best_combined else 0.0
                mark = ""
                if c["combined"] == best_combined:
                    mark += " <-best"
                if c is cands[0]:
                    mark += " <-earliest"
                print(f"    {c['cand_start']:>5} {c['base_len']:>7} {c['box_width']:>6.3f} "
                      f"{c['r_touches']}/{c['s_touches']:<5} {c['combined']:>8.3f} "
                      f"{pct:>6.0f}%{mark}")


def main() -> None:
    if len(sys.argv) > 1:
        _trace([a.upper() for a in sys.argv[1:]])
        return
    best = _run("best")
    earliest = _run("earliest")

    best_t, early_t = set(best), set(earliest)
    dropped = sorted(best_t - early_t)
    added = sorted(early_t - best_t)
    common = sorted(best_t & early_t)

    print("=" * 78)
    print("  PHASE-B A/B  —  select='best' (today)  vs  select='earliest' (Change B)")
    print("=" * 78)
    print(f"  fixture firing (best): {len(best_t)}   firing (earliest): {len(early_t)}")
    print(f"  DROPPED (fire today, not under earliest): {len(dropped)}")
    print(f"  NEW     (fire under earliest, not today): {len(added)}")

    if dropped:
        print("\n  DROPPED tickers (the regression risk to triage):")
        for t in dropped:
            b = best[t]
            print(f"    {t:8} Score {_fmt(b.get('Score')):>6}  Tier {b.get('Tier')}  "
                  f"BaseLen {b.get('Base Len')}  Box {_fmt(b.get('Box Width'))}")
    if added:
        print("\n  NEW tickers (potential gains):")
        for t in added:
            e = earliest[t]
            print(f"    {t:8} Score {_fmt(e.get('Score')):>6}  Tier {e.get('Tier')}  "
                  f"BaseLen {e.get('Base Len')}  Box {_fmt(e.get('Box Width'))}")

    # Survivors whose canonical structure moved.
    movers = []
    tier_changes = []
    score_deltas = []
    for t in common:
        b, e = best[t], earliest[t]
        changed = []
        for f in _NUM_FIELDS:
            bv, ev = b.get(f), e.get(f)
            if isinstance(bv, (int, float)) and isinstance(ev, (int, float)):
                if abs(float(bv) - float(ev)) > 1e-6:
                    changed.append((f, bv, ev))
            elif bv != ev:
                changed.append((f, bv, ev))
        for f in _TAG_FIELDS:
            if b.get(f) != e.get(f):
                changed.append((f, b.get(f), e.get(f)))
                if f == "Tier":
                    tier_changes.append((t, b.get("Tier"), e.get("Tier")))
        if changed:
            movers.append((t, changed))
        bs, es = b.get("Score"), e.get("Score")
        if isinstance(bs, (int, float)) and isinstance(es, (int, float)):
            score_deltas.append((t, float(es) - float(bs)))

    print(f"\n  SURVIVORS with structural movement: {len(movers)} / {len(common)}")
    if tier_changes:
        print(f"  TIER changes: {len(tier_changes)}")
        for t, a, c in tier_changes:
            print(f"    {t:8} {a} -> {c}")

    if score_deltas:
        ups = [d for _, d in score_deltas if d > 0.05]
        downs = [d for _, d in score_deltas if d < -0.05]
        flat = len(score_deltas) - len(ups) - len(downs)
        print(f"\n  SCORE deltas (earliest - best): "
              f"{len(ups)} up / {len(downs)} down / {flat} flat (|d|<=0.05)")
        worst = sorted(score_deltas, key=lambda x: x[1])[:10]
        bestmv = sorted(score_deltas, key=lambda x: x[1], reverse=True)[:10]
        print("    biggest DROPS:")
        for t, d in worst:
            if d < -0.05:
                print(f"      {t:8} {d:+.2f}  ({_fmt(best[t].get('Score'))} -> {_fmt(earliest[t].get('Score'))})")
        print("    biggest GAINS:")
        for t, d in bestmv:
            if d > 0.05:
                print(f"      {t:8} {d:+.2f}  ({_fmt(best[t].get('Score'))} -> {_fmt(earliest[t].get('Score'))})")

    # A few full per-field traces for the largest movers, for eyeballing.
    print("\n  TOP STRUCTURAL MOVERS (per-field):")
    movers_sorted = sorted(
        movers,
        key=lambda m: abs(float(best[m[0]].get("Score", 0)) - float(earliest[m[0]].get("Score", 0))),
        reverse=True,
    )
    for t, changed in movers_sorted[:12]:
        print(f"    {t}:")
        for f, bv, ev in changed:
            print(f"        {f:12} {_fmt(bv):>8}  ->  {_fmt(ev):>8}")


if __name__ == "__main__":
    main()
