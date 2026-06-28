"""
Detection-fidelity grading harness — the visual analogue of the recall guard.

The recall guard asks "does the engine still fire on the winners I curated?"
This asks the parallel, outcome-free question: **"does the engine's Phase-D
read match what I see on the chart?"** It needs no forward-return clock — only
the human eye — so it runs today.

Workflow (three steps, you only do step 2):

    1.  python tools/fidelity_harness.py --render
        Renders ~12 firing charts with the engine's Phase A/B/D bands + the
        tight LPS candidate-bar box into tools/fidelity/charts/<TICKER>.png,
        and writes a blank-verdict template to tools/fidelity/labels.csv.

    2.  YOU flip through the PNGs and fill two columns per row in labels.csv:
          phase_d_verdict   ok | early | late
          lps_zone_verdict  ok | high  | low | wrong
        (optionally your_phase_d_date = YYYY-MM-DD, and free-text notes).
        See the verdict key in tools/fidelity/README.txt.

    3.  python tools/fidelity_harness.py --grade
        Reads the filled CSV and prints the fidelity score + the misreads to
        look at.

Hermetic: renders from the committed shadow fixture (the same frozen frames the
shadow-diff guard uses), so the set is reproducible across machines and dates.
No network, no webapp, no backend boot.
"""
from __future__ import annotations

import argparse
import csv
import os
import random
import sys

try:  # works under both `python -m tools.fidelity_harness` and `python tools/fidelity_harness.py`
    from tools._bootstrap import configure_path
except ModuleNotFoundError:
    from _bootstrap import configure_path

configure_path()

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))

_OUT_DIR = os.path.join(_THIS_DIR, "fidelity")
_CHARTS_DIR = os.path.join(_OUT_DIR, "charts")
_LABELS_CSV = os.path.join(_OUT_DIR, "labels.csv")
_README = os.path.join(_OUT_DIR, "README.txt")

# CSV columns: the first block is engine output (do not edit); the second block
# is for the human to fill.
_ENGINE_COLS = [
    "ticker", "snapshot_date", "tier", "score",
    "engine_phase_d_date", "engine_lps_low", "engine_lps_high",
    "has_mini", "has_spring",
]
_HUMAN_COLS = ["phase_d_verdict", "lps_zone_verdict", "your_phase_d_date", "notes"]

_PHASE_D_VERDICTS = {"ok", "early", "late"}
_LPS_VERDICTS = {"ok", "high", "low", "wrong"}

_README_TEXT = """\
FIDELITY LABELS — verdict key
=============================

Open each chart in tools/fidelity/charts/, compare the engine's drawn bands to
where YOUR eye places the right-most region, then fill two columns in labels.csv.

What the chart shows:
  - grey band   = Phase A (climax / lead-in)
  - purple band = Phase B (equilibrium body)
  - blue band   = Phase D (the right-most region)      <-- the one that matters
  - yellow box  = the exact LPS candidate bars (tight in time AND price)
  - pink dashed = Phase C spring (only on undercut-support setups)
  - dashed lines = R (resistance) and S (support)

phase_d_verdict  -> is the BLUE band's LEFT edge where Phase D begins?
    ok     the blue band starts about where you'd start the right-most region
    early  the blue band starts too far LEFT (it grabbed body that isn't Phase D)
    late   the blue band starts too far RIGHT (it missed the start of Phase D)

lps_zone_verdict -> is this an LPS you'd actually act on? (placement AND quality)
    ok     a real LPS, on the right bars, that you'd trust
    high   the box sits above the real LPS
    low    the box sits below the real LPS
    wrong  misplaced, OR no LPS here yet, OR a bad/stretched LPS you wouldn't
           trust (e.g. formed far above the base -> Last Supper shakeout risk)

Optional:
    your_phase_d_date  YYYY-MM-DD where YOU would start Phase D (for day-error stats)
    notes              anything worth remembering about this chart

Leave a row's verdict columns blank to skip it; --grade ignores unscored rows.
"""


# ---------------------------------------------------------------------------
# Engine side — gather firing setups from the hermetic fixture
# ---------------------------------------------------------------------------
def _firing_setups():
    """Return [(ticker, df, result_dict), ...] for every fixture ticker that fires.

    Reuses the shadow-diff fixture loader so the set is the exact frozen frames
    the regression guard runs on (hermetic, reproducible).
    """
    from core.pipeline.screener import _evaluate_ticker
    from tools.shadow_diff import _load_fixture

    frames, scalars = _load_fixture()
    spy_6m = scalars.get("spy_6m_return", 0.0)
    breadth = scalars.get("breadth_pct")

    out = []
    for ticker in sorted(frames):
        df = frames[ticker]
        try:
            result = _evaluate_ticker(ticker, df, spy_6m, breadth)
        except Exception as exc:  # noqa: BLE001 — harness must never abort mid-sweep
            print(f"  [skip {ticker}] {type(exc).__name__}: {exc}", file=sys.stderr)
            continue
        if result is not None:
            out.append((ticker, df, result))
    return out


def _sample(setups, n, seed):
    """Deterministic mixed-representative sample of n setups."""
    if n >= len(setups):
        return list(setups)
    return random.Random(seed).sample(setups, n)


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------
def _date_strings(plot_df):
    if "Date" in plot_df.columns:
        return [str(d)[:10] for d in plot_df["Date"]]
    if "index" in plot_df.columns:
        return [str(d)[:10] for d in plot_df["index"]]
    return [str(d)[:10] for d in plot_df.iloc[:, 0]]


def _x_on_or_after(dates, target):
    """First x-position whose date >= target (mirrors the JS overlay), or None."""
    if not target:
        return None
    for i, d in enumerate(dates):
        if d >= target:
            return i
    return None


def _render_one(ticker, df, result, out_path, window=None):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle

    # Base-focused window: show the consolidation + Phase D large enough to
    # grade, with a lead-in strip for Phase A context. A flat wide window
    # squishes Phase D / the LPS zone into an ungradeable sliver on the right.
    if window:
        show = min(window, len(df))
    else:
        base_len = int(result.get("_base_len") or result.get("Base Len") or 60)
        show = min(len(df), base_len + 45)
    plot_df = df.tail(show).copy().reset_index()
    dates = _date_strings(plot_df)
    o = plot_df["Open"].values
    h = plot_df["High"].values
    low = plot_df["Low"].values
    c = plot_df["Close"].values
    xs = list(range(len(plot_df)))
    last_x = len(xs) - 1

    fig, ax = plt.subplots(figsize=(15, 7.5))

    # Phase bands (vertical regions), drawn behind the bars.
    xa = _x_on_or_after(dates, result.get("_phase_a_start_date"))
    xb = _x_on_or_after(dates, result.get("_phase_b_start_date"))
    xd = _x_on_or_after(dates, result.get("_phase_d_start_date"))
    xc = _x_on_or_after(dates, result.get("_phase_c_event_date"))
    if xa is not None and xb is not None and xb > xa:
        ax.axvspan(xa, xb, color="#9aa1b2", alpha=0.10, lw=0)
    if xb is not None and xd is not None and xd > xb:
        ax.axvspan(xb, xd, color="#8b5cf6", alpha=0.10, lw=0)
    if xd is not None:
        ax.axvspan(xd, last_x, color="#3b82f6", alpha=0.14, lw=0)
        ax.axvline(xd, color="#3b82f6", alpha=0.5, lw=1.2)

    # LPS zone — a tight box wrapping the EXACT LPS candidate bars in both
    # axes (Chrollo's convention), not a level stretched across Phase D.
    z_low, z_high = result.get("_lps_zone_low"), result.get("_lps_zone_high")
    zx0 = _x_on_or_after(dates, result.get("_lps_zone_start_date"))
    zx1 = _x_on_or_after(dates, result.get("_lps_zone_end_date"))
    if z_low is not None and z_high is not None and zx0 is not None:
        if zx1 is None or zx1 < zx0:
            zx1 = last_x
        ax.add_patch(Rectangle(
            (zx0 - 0.42, z_low), (zx1 - zx0) + 0.84, max(z_high - z_low, 1e-9),
            facecolor="#eab308", alpha=0.20, edgecolor="#c79a06", lw=1.4, zorder=2,
        ))

    # R / S context lines.
    if result.get("_R") is not None:
        ax.axhline(float(result["_R"]), color="#5b8aff", ls="--", lw=0.9, alpha=0.7)
    if result.get("_S") is not None:
        ax.axhline(float(result["_S"]), color="#5b8aff", ls="--", lw=0.9, alpha=0.7)

    # OHLC bars (the user reads bars, not candles): a high-low vertical wick,
    # a left tick for the open, a right tick for the close. Thicker and higher
    # contrast than candles so the structure reads at a glance.
    tick = 0.34
    bar_lw = 1.1 if len(xs) > 90 else 1.4
    for i in xs:
        up = c[i] >= o[i]
        col = "#1f9d8b" if up else "#e04848"
        ax.plot([i, i], [low[i], h[i]], color=col, lw=bar_lw, zorder=3,
                solid_capstyle="round")
        ax.plot([i - tick, i], [o[i], o[i]], color=col, lw=bar_lw, zorder=3,
                solid_capstyle="round")
        ax.plot([i, i + tick], [c[i], c[i]], color=col, lw=bar_lw, zorder=3,
                solid_capstyle="round")

    # Phase C spring marker.
    if xc is not None:
        ax.axvline(xc, color="#ec4899", ls="--", lw=1.0, alpha=0.7)
        ax.scatter([xc], [low[xc]], marker="D", s=42, color="#ec4899",
                   edgecolor="#e8eaf0", zorder=4)

    tags = []
    if result.get("_has_mini_consolidation"):
        tags.append("MINI")
    if result.get("_phase_c_event_date"):
        tags.append("SPRING")
    tag_str = ("  [" + " ".join(tags) + "]") if tags else ""
    ax.set_title(
        f"{ticker}   {result.get('Tier', '?')}   score={result.get('Score', '?')}"
        f"   conf={result.get('_scope_confidence', '?')}{tag_str}",
        fontsize=12, fontweight="bold",
    )

    # Sparse date ticks.
    step = max(1, len(xs) // 8)
    ax.set_xticks(xs[::step])
    ax.set_xticklabels([dates[i] for i in xs[::step]], rotation=30, fontsize=8, ha="right")
    ax.set_xlim(-1, last_x + 1)
    ax.margins(y=0.05)
    ax.grid(True, alpha=0.12)
    fig.tight_layout()
    fig.savefig(out_path, dpi=135)
    plt.close(fig)


def render(n=12, seed=7, window=None):
    os.makedirs(_CHARTS_DIR, exist_ok=True)
    setups = _firing_setups()
    if not setups:
        print("No firing setups in the fixture — nothing to render.")
        return
    chosen = _sample(setups, n, seed)
    chosen.sort(key=lambda t: t[0])

    rows = []
    for ticker, df, result in chosen:
        out_path = os.path.join(_CHARTS_DIR, f"{ticker}.png")
        _render_one(ticker, df, result, out_path, window=window)
        rows.append({
            "ticker": ticker,
            "snapshot_date": str(df.index[-1])[:10],
            "tier": result.get("Tier", ""),
            "score": result.get("Score", ""),
            "engine_phase_d_date": result.get("_phase_d_start_date") or "",
            "engine_lps_low": result.get("_lps_zone_low") if result.get("_lps_zone_low") is not None else "",
            "engine_lps_high": result.get("_lps_zone_high") if result.get("_lps_zone_high") is not None else "",
            "has_mini": int(bool(result.get("_has_mini_consolidation"))),
            "has_spring": int(bool(result.get("_phase_c_event_date"))),
            "phase_d_verdict": "",
            "lps_zone_verdict": "",
            "your_phase_d_date": "",
            "notes": "",
        })

    with open(_LABELS_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_ENGINE_COLS + _HUMAN_COLS)
        writer.writeheader()
        writer.writerows(rows)
    with open(_README, "w", encoding="utf-8") as f:
        f.write(_README_TEXT)

    print(f"Rendered {len(rows)} charts -> {_CHARTS_DIR}")
    print(f"Label template -> {_LABELS_CSV}")
    print(f"Verdict key    -> {_README}")
    print("\nNext: open the PNGs, fill phase_d_verdict + lps_zone_verdict in the CSV,")
    print("      then run:  python tools/fidelity_harness.py --grade")


# ---------------------------------------------------------------------------
# Grading (pure core + CSV reader)
# ---------------------------------------------------------------------------
def summarize_fidelity(rows):
    """Pure: compute fidelity metrics from labeled rows.

    ``rows`` is a list of dicts with at least phase_d_verdict / lps_zone_verdict
    (and optionally engine_phase_d_date + your_phase_d_date for day-error). Rows
    with a blank phase_d_verdict are treated as unscored and ignored.

    Returns a dict:
        n_total, n_scored,
        phase_d_ok, phase_d_ok_pct, phase_d_early, phase_d_late,
        lps_ok, lps_ok_pct, lps_breakdown (dict),
        day_errors (list[int]), median_day_error (float|None),
        misreads (list[dict]) — scored rows where either verdict != ok
    """
    scored = [r for r in rows if (r.get("phase_d_verdict") or "").strip().lower() in _PHASE_D_VERDICTS]

    pd_ok = pd_early = pd_late = 0
    lps_ok = 0
    lps_breakdown = {v: 0 for v in _LPS_VERDICTS}
    day_errors = []
    misreads = []

    for r in scored:
        pdv = (r.get("phase_d_verdict") or "").strip().lower()
        lpv = (r.get("lps_zone_verdict") or "").strip().lower()
        if pdv == "ok":
            pd_ok += 1
        elif pdv == "early":
            pd_early += 1
        elif pdv == "late":
            pd_late += 1
        if lpv in lps_breakdown:
            lps_breakdown[lpv] += 1
            if lpv == "ok":
                lps_ok += 1

        eng = (r.get("engine_phase_d_date") or "").strip()
        yours = (r.get("your_phase_d_date") or "").strip()
        if eng and yours:
            err = _day_diff(eng, yours)
            if err is not None:
                day_errors.append(err)

        if pdv != "ok" or (lpv and lpv != "ok"):
            misreads.append({
                "ticker": r.get("ticker", "?"),
                "phase_d_verdict": pdv,
                "lps_zone_verdict": lpv,
                "notes": (r.get("notes") or "").strip(),
            })

    n_scored = len(scored)
    n_lps_scored = sum(lps_breakdown.values())
    median_day_error = _median([abs(e) for e in day_errors]) if day_errors else None
    return {
        "n_total": len(rows),
        "n_scored": n_scored,
        "phase_d_ok": pd_ok,
        "phase_d_ok_pct": round(100.0 * pd_ok / n_scored, 1) if n_scored else 0.0,
        "phase_d_early": pd_early,
        "phase_d_late": pd_late,
        "lps_ok": lps_ok,
        "lps_ok_pct": round(100.0 * lps_ok / n_lps_scored, 1) if n_lps_scored else 0.0,
        "lps_breakdown": lps_breakdown,
        "day_errors": day_errors,
        "median_day_error": median_day_error,
        "misreads": misreads,
    }


def _median(values):
    if not values:
        return None
    s = sorted(values)
    mid = len(s) // 2
    if len(s) % 2:
        return float(s[mid])
    return (s[mid - 1] + s[mid]) / 2.0


def _day_diff(date_a, date_b):
    """Signed calendar-day difference (b - a), or None if unparseable."""
    import datetime
    try:
        da = datetime.date.fromisoformat(date_a[:10])
        db = datetime.date.fromisoformat(date_b[:10])
    except (ValueError, TypeError):
        return None
    return (db - da).days


def _read_labels(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def grade(labels_path=_LABELS_CSV):
    if not os.path.exists(labels_path):
        print(f"No labels file at {labels_path}. Run --render first, then fill it in.")
        return
    rows = _read_labels(labels_path)
    s = summarize_fidelity(rows)

    print("=" * 64)
    print("  DETECTION-FIDELITY REPORT — engine Phase D vs. your eye")
    print("=" * 64)
    if s["n_scored"] == 0:
        print(f"  {s['n_total']} rows, 0 scored. Fill phase_d_verdict in the CSV.")
        return
    print(f"  scored {s['n_scored']}/{s['n_total']} charts\n")
    print(f"  Phase D start : {s['phase_d_ok_pct']:.1f}% ok "
          f"({s['phase_d_ok']} ok / {s['phase_d_early']} early / {s['phase_d_late']} late)")
    print(f"  LPS zone      : {s['lps_ok_pct']:.1f}% ok  "
          f"(breakdown {s['lps_breakdown']})")
    if s["median_day_error"] is not None:
        print(f"  Day error     : median |engine - you| = {s['median_day_error']:.1f} days "
              f"(n={len(s['day_errors'])})")
    if s["misreads"]:
        print("\n  Misreads to inspect:")
        for m in s["misreads"]:
            extra = f" — {m['notes']}" if m["notes"] else ""
            print(f"    {m['ticker']:<8} phase_d={m['phase_d_verdict'] or '-':<6} "
                  f"lps={m['lps_zone_verdict'] or '-':<6}{extra}")
    print()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Detection-fidelity grading harness.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--render", action="store_true", help="render chart PNGs + labels template")
    group.add_argument("--grade", action="store_true", help="grade the filled labels CSV")
    parser.add_argument("--n", type=int, default=12, help="number of charts to render")
    parser.add_argument("--seed", type=int, default=7, help="sampling seed (reproducible set)")
    parser.add_argument("--window", type=int, default=0,
                        help="bars shown per chart (0 = auto, base-focused)")
    args = parser.parse_args(argv)

    if args.render:
        render(n=args.n, seed=args.seed, window=args.window)
    else:
        grade()


if __name__ == "__main__":
    main()
