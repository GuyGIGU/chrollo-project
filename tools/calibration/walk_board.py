"""The walk's board (task 10 of the two-eyes-reader build): on his 35 drawings, does the two-legs walk elect
his pair on his last receding day — from the reader as it stands, and from the one trend end into his box alone.

Per drawing, on the reader's own line built on the frame cut at his day:

* his two anchors on the line (the listing gate's reading: exact, by price, near, or not a turn);
* THE BOX the reader shows on his last receding day (`engine_alpha.two_eyes.walk.elect`): HIS (both lines to the
  cent), CLOSE (both within half a daily range of his), OTHER, or NONE — and which trend end it walked from:
  the transition into his box, one inside his box, or an earlier one;
* the same from the ONE trend end alone — the latest run end at or before his first anchor — which isolates
  stage 3 (the walk and the answering) from stage 4's question of which trend end is current;
* whether the walk LISTED his pair at all, after how many moves, and whether his pair is answered his way by
  the reader's rules (both lines by a swing within the area), and on which day it became a box;
* pairs tried, the walk's and the whole read's time against the plan's 0.2-second budget, the record's size.

Offline, read-only, sidecars only: it reads the frozen as-drawn frames and writes to a directory you name.

    python -m tools.calibration.walk_board                       # the board
    python -m tools.calibration.walk_board --pages OUT           # the board AND one OHLC page per drawing
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import statistics
import textwrap
import time
from typing import Optional

import pandas as pd

try:
    from tools._bootstrap import configure_path
except ImportError:  # invoked as a script from the repo root
    import os, sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from tools._bootstrap import configure_path  # type: ignore
_ROOT = configure_path(backend=True)

from engine_alpha import two_eyes  # noqa: E402
from engine_alpha.two_eyes import frame as two_eyes_frame  # noqa: E402
from engine_alpha.two_eyes import line as two_eyes_line  # noqa: E402
from engine_alpha.two_eyes import method_numbers as M  # noqa: E402
from engine_alpha.two_eyes import walk  # noqa: E402
from tools.calibration.listing_gate import anchor_turns  # noqa: E402
from tools.calibration.yardstick import his_last_lps_day, rails_close  # noqa: E402
from tools.regression.marks_corpus import load_corpus, setup_key  # noqa: E402
from core.calibration.replay import fixture_frame, load_sealed_fixture  # noqa: E402

#: The plan's named charts for task 10.
NAMED = ("VIK", "SYRE", "BMRN", "ALB", "FOSL", "MSGS", "ROIV")
BUDGET_SECONDS = 0.2
VERDICTS = ("HIS", "CLOSE", "OTHER", "NONE")


def _date(value) -> Optional[dt.date]:
    if value is None or isinstance(value, dt.date):
        return value
    return dt.date.fromisoformat(str(value)[:10])


def verdict(pair, rails: dict, unit: float) -> str:
    """The engine's box against his two lines."""
    if pair is None:
        return "NONE"
    if abs(pair.R - rails["R"]) < 0.005 and abs(pair.S - rails["S"]) < 0.005:
        return "HIS"
    return "CLOSE" if rails_close(rails["R"], rails["S"], pair.R, pair.S, unit) else "OTHER"


def where_from(pair, ends: tuple, first_bar: int) -> str:
    """Which trend end the box walked from: the transition into his box, one inside it, or an earlier one."""
    if pair is None:
        return "-"
    before = [e for e in ends if e["climax_bar"] <= first_bar]
    transition = before[-1]["climax_bar"] if before else None
    if pair.end_climax_bar == transition:
        return "the transition"
    return "inside his box" if pair.end_climax_bar > first_bar else "an earlier end"


def from_the_one_end(turns, ranges, ends: tuple, first_bar: int, read_bar: int):
    """The walk from the one trend end into his box alone (the latest run end at or before his first anchor),
    bounded like the reader's: to the next trend end's climax."""
    before = [k for k, e in enumerate(ends) if e["climax_bar"] <= first_bar and e["pair"] is not None]
    if not before:
        return None, []
    k = before[-1]
    later = [(i, e["known_bar"]) for e in ends[k + 1:] for i in (walk._climax_index(turns, e),) if i is not None]
    last_index, last_known = later[0] if later else (len(turns) - 1, len(turns) + read_bar)
    pairs = walk._walk_from(turns, ranges, ends[k], (*ends[k]["pair"], ends[k]["joined"]), last_index, last_known,
                            read_bar)
    return walk.box_of(pairs), pairs


def score_setup(setup: dict, raw) -> dict:
    as_of = _date(setup["as_of"])
    cut = raw.loc[:pd.Timestamp(as_of)]
    started = time.perf_counter()
    read = two_eyes.read(setup["ticker"], cut)
    read_seconds = time.perf_counter() - started
    prepared = two_eyes_frame.prepare(cut)
    line = two_eyes_line.build(prepared)
    days = [d.date() for d in prepared.index]
    ranges = prepared[two_eyes_frame.DAILY_RANGE].to_numpy(dtype=float)
    rails = setup["rails_drawn"]
    r_bar, s_bar = days.index(_date(setup["anchors"]["R"])), days.index(_date(setup["anchors"]["S"]))
    first_bar, last_bar = min(r_bar, s_bar), days.index(his_last_lps_day(setup))
    unit = float(ranges[max(r_bar, s_bar)])
    turns = list(line.turns)
    far = line.far(M.FAR_VIEW_FLOOR_RANGES)
    his = anchor_turns(turns, r_bar, s_bar, rails["R"], rails["S"], unit)
    known = walk.known_by(turns, last_bar)
    started = time.perf_counter()
    result = walk.elect(known, walk.known_by(far, last_bar), ranges, days=days, read_bar=last_bar)
    walk_seconds = time.perf_counter() - started
    one, one_pairs = from_the_one_end(known, ranges, result.ends, first_bar, last_bar)
    his_pair = None
    listed = None
    if his["R"] is not None and his["S"] is not None:
        r_i, s_i = his["R"], his["S"]
        listed = result.pairs.get((r_i, s_i))
        joined = max(int(turns[r_i].knowable_bar), int(turns[s_i].knowable_bar))
        his_pair = walk.measure(known, ranges, r_i, s_i, joined, 0, "BC", None, "his pair", last_bar)
    _, trail, _ = walk.record(result)
    return {
        "key": setup_key(setup), "ticker": setup["ticker"], "as_of": as_of, "days": days, "prepared": prepared,
        "turns": turns, "known": known, "ranges": ranges, "unit": unit, "rails": rails,
        "r_bar": r_bar, "s_bar": s_bar, "first_bar": first_bar, "last_bar": last_bar, "his": his,
        "result": result, "box": result.winner, "verdict": verdict(result.winner, rails, unit),
        "from": where_from(result.winner, result.ends, first_bar),
        "one": one, "one_verdict": verdict(one, rails, unit), "one_pairs": len(one_pairs),
        "listed": listed, "his_pair": his_pair,
        "pairs": len(result.pairs), "walk_seconds": walk_seconds, "read_seconds": read_seconds,
        "bytes": len(repr(trail)), "read": read,
    }


def run_board(setups: list, frames: dict) -> list:
    return [score_setup(s, fixture_frame(frames, setup_key(s), s["ticker"])) for s in setups]


# --------------------------------------------------------------------------- #
# The board                                                                   #
# --------------------------------------------------------------------------- #
def _day(d) -> str:
    return d.strftime("%a %d/%m/%Y")


def _med_worst(values, fmt="{:g}") -> str:
    values = [v for v in values if v is not None]
    if not values:
        return "-"
    return f"median {fmt.format(statistics.median(values))} · worst {fmt.format(max(values))}"


def _his_pair_words(row: dict) -> str:
    hp = row["his_pair"]
    if hp is None:
        return "not both on the line"
    if hp.birth_bar is not None:
        return f"born {row['days'][hp.birth_bar]:%d/%m}" + (" (15th day)" if hp.birth_bar == hp.fifteenth else "")
    if hp.unfit:
        return f"never: {hp.unfit}"
    missing = [n for n, got in (("R", hp.r_answer), ("S", hp.s_answer)) if got is None]
    return "not by his day: " + (" and ".join(missing) + " unanswered" if missing else "under 15 days")


def _difference(row: dict) -> str:
    box, rails, unit = row["box"], row["rails"], row["unit"]
    if box is None:
        return "no box on his day"
    parts = []
    for name, got, his in (("R", box.R, rails["R"]), ("S", box.S, rails["S"])):
        off = (got - his) / unit
        parts.append(f"{name} same" if abs(off) < 0.005 else f"{name} {got:.2f} vs his {his:.2f} ({off:+.2f} ranges)")
    days = row["days"]
    parts.append(f"from {row['from']} ({days[box.end_climax_bar]:%d/%m}), box on {days[box.birth_bar]:%d/%m}")
    return "; ".join(parts)


def format_board(rows: list) -> str:
    out = ["THE WALK ON HIS 35 — the box the reader shows on his last receding day (far floor "
           f"{M.FAR_VIEW_FLOOR_RANGES} ranges, area {M.LINE_WORD_AREA_ATR} range, {M.BOX_DAYS} days, tall floor "
           f"{M.BOX_MIN_HEIGHT_RANGES} range)", ""]
    for name, key in (("THE READER'S BOX", "verdict"), ("FROM THE ONE TREND END INTO HIS BOX ALONE", "one_verdict")):
        counts = {v: sum(1 for r in rows if r[key] == v) for v in VERDICTS}
        out.append(f"  {name}: " + " · ".join(f"{v} {counts[v]}" for v in VERDICTS) + f"  (of {len(rows)})")
    boxes = [r for r in rows if r["box"] is not None]
    out.append("  the reader's box walked from: " + " · ".join(
        f"{w} {sum(1 for r in boxes if r['from'] == w)}" for w in ("the transition", "inside his box", "an earlier end")))
    out.append(f"  his pair LISTED by the walk: {sum(1 for r in rows if r['listed'] is not None)} of {len(rows)}"
               f" · his pair a box by the reader's rules by his day: "
               f"{sum(1 for r in rows if r['his_pair'] is not None and r['his_pair'].birth_bar is not None)} of {len(rows)}")
    against = sum(1 for r in boxes if r["box"].opens_against_the_trend)
    out.append(f"  boxes opening against the price (his rule, checked on the result): {against} of {len(boxes)}")
    out.append(f"  pairs tried: {_med_worst([r['pairs'] for r in rows])} · walk seconds: "
               f"{_med_worst([r['walk_seconds'] for r in rows], '{:.3f}')} · whole read seconds: "
               f"{_med_worst([r['read_seconds'] for r in rows], '{:.3f}')} (budget {BUDGET_SECONDS}) · trail bytes: "
               f"{_med_worst([r['bytes'] for r in rows])}")
    named = [f"{t} {next((r['verdict'] for r in rows if r['ticker'] == t), '?')}" for t in NAMED]
    out.append("  named charts: " + " · ".join(named))
    out.append("")
    out.append(f"  {'drawing':<16}{'his anchors':<14}{'box':<7}{'one end':<9}{'listed':<9}{'his pair':<24}{'pairs':>6}"
               f"{'read s':>8}  where the box differs")
    for row in misses_first(rows):
        his = row["his"]
        anchors = f"{his['r_match'] or '-'}/{his['s_match'] or '-'}"
        listed = "-" if row["listed"] is None else f"{row['listed'].position} move(s)"
        out.append(f"  {row['key']:<16}{anchors:<14}{row['verdict']:<7}{row['one_verdict']:<9}{listed:<9}"
                   f"{_his_pair_words(row):<24}{row['pairs']:>6}{row['read_seconds']:>8.3f}  {_difference(row)}")
    return "\n".join(out)


def misses_first(rows: list) -> list:
    order = {v: i for i, v in enumerate(reversed(VERDICTS))}
    return sorted(rows, key=lambda r: (order[r["verdict"]], r["key"]))


# --------------------------------------------------------------------------- #
# The pictures — OHLC bars, never candles                                     #
# --------------------------------------------------------------------------- #
_HIS = "#d62728"        # his lines, red
_ENGINE = "#1f77b4"     # the reader's box, blue
_ONE = "#2e8b57"        # the box from the one trend end alone, when it differs
_LINE = "#8a8a8a"
_END = "#1f4e9c"
_LEAD_IN = 45


def render_pages(rows: list, setups: dict, out_dir: str) -> list:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from tools.research.full_package_render import _draw_bars

    os.makedirs(out_dir, exist_ok=True)
    pages = []
    for row in misses_first(rows):
        path = os.path.join(out_dir, f"{row['key'].replace(':', '_')}.png")
        _render_one(plt, _draw_bars, row, setups[row["key"]], path)
        pages.append(path)
    return pages


def _render_one(plt, draw_bars, row: dict, setup: dict, path: str):
    prepared, days, turns = row["prepared"], row["days"], row["turns"]
    box = row["box"]
    lo = max(0, min(row["first_bar"], box.opening_bar if box is not None else row["first_bar"]) - _LEAD_IN)
    if box is not None:
        lo = max(0, min(lo, box.end_climax_bar - 10))
    hi = min(len(days), row["last_bar"] + 6)
    view = prepared.iloc[lo:hi]
    x = lambda bar: bar - lo
    fig, ax = plt.subplots(figsize=(16, 8))
    draw_bars(ax, view["Open"].values, view["High"].values, view["Low"].values, view["Close"].values)

    rails, band = row["rails"], M.LINE_WORD_AREA_ATR * row["unit"]
    for price, name in ((rails["R"], "his R"), (rails["S"], "his S")):
        ax.axhspan(price - band, price + band, color=_HIS, alpha=.08, zorder=0)
        ax.axhline(price, color=_HIS, lw=1.7, zorder=4)
        ax.annotate(f"{name} {price:.2f}", (0.004, price), xycoords=("axes fraction", "data"), color=_HIS,
                    fontsize=9, va="bottom", zorder=5)
    ax.axvspan(x(row["first_bar"]), x(row["last_bar"]), color=_HIS, alpha=.05, zorder=0)
    for bar, price in ((row["r_bar"], rails["R"]), (row["s_bar"], rails["S"])):
        ax.plot([x(bar)], [price], marker="o", ms=13, mfc="none", mec=_HIS, mew=1.8, zorder=6)
    lps = setup.get("lps2") or setup.get("lps")
    if lps:
        a, b = days.index(_date(lps[0])), days.index(_date(lps[1]))
        ax.axvspan(x(a), x(b), color="#8a6d3b", alpha=.13, zorder=1)

    fine = [t for t in row["known"] if lo <= t.bar < hi]
    if fine:
        ax.plot([x(t.bar) for t in fine], [t.price for t in fine], color=_LINE, lw=.8, alpha=.7, zorder=2)

    if box is not None:
        for price, bar, name in ((box.R, box.r_bar, "R"), (box.S, box.s_bar, "S")):
            ax.plot([x(bar), x(hi - 1)], [price, price], color=_ENGINE, lw=1.6, ls="--", zorder=4)
            ax.plot([x(bar)], [price], marker="o", ms=9, color=_ENGINE, mfc="white", mew=1.8, zorder=6)
            ax.annotate(f"reader's {name} {price:.2f}", (0.70, price), xycoords=("axes fraction", "data"),
                        color=_ENGINE, fontsize=8.5, va="bottom", zorder=5)
        ax.axvline(x(box.birth_bar), color=_ENGINE, lw=1.2, ls=":", zorder=3)
        ax.annotate(f"reader's box on {days[box.birth_bar]:%d/%m}", (x(box.birth_bar), 0.03),
                    xycoords=("data", "axes fraction"), color=_ENGINE, fontsize=8, ha="left", va="bottom")
        end = next(e for e in row["result"].ends if e["climax_bar"] == box.end_climax_bar and e["kind"] == box.end_kind)
        if end["climax_bar"] >= lo:
            mark = "v" if end["kind"] == "BC" else "^"
            ax.plot([x(end["climax_bar"])], [end["climax_price"]], marker=mark, ms=13, color=_END, zorder=7,
                    mec="white", mew=.8)
            ax.annotate("trend end the box walked from", (x(end["climax_bar"]), end["climax_price"]),
                        xytext=(0, 14 if mark == "v" else -18), textcoords="offset points", color=_END, fontsize=8,
                        ha="center", zorder=8)
    one = row["one"]
    if one is not None and (box is None or one.feet != box.feet):
        for price in (one.R, one.S):
            ax.axhline(price, color=_ONE, lw=1.2, ls="-.", zorder=3)
        ax.annotate(f"from the one trend end alone: {one.R:.2f} / {one.S:.2f}", (0.35, one.R),
                    xycoords=("axes fraction", "data"), color=_ONE, fontsize=8.5, va="bottom", zorder=5)

    n = len(view)
    step = max(1, n // 12)
    ax.set_xticks(range(0, n, step))
    ax.set_xticklabels([days[lo + i].strftime("%d/%m/%y") for i in range(0, n, step)], fontsize=8)
    ax.set_xlim(-2, n + 1)
    ax.set_title(f"{row['key']}  —  {row['verdict']} (from the one trend end alone: {row['one_verdict']})",
                 fontsize=13, loc="left", fontweight="bold")
    ax.set_xlabel(textwrap.fill(_words(row), 210), fontsize=9.5, labelpad=8)
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)


def _words(row: dict) -> str:
    parts = []
    if row["his"]["why"]:
        parts.append(row["his"]["why"] + ".")
    parts.append(_difference(row).capitalize() + ".")
    parts.append(f"His pair by the reader's rules: {_his_pair_words(row)}"
                 + ("" if row["listed"] is None else f"; listed after {row['listed'].position} move(s)") + ".")
    box = row["box"]
    if box is not None:
        parts.append("The trail: " + " → ".join(s.saying for s in row["read"].trail if s.stage != "trend end") + ".")
    parts.append(f"{row['pairs']} pairs tried; the whole read took {row['read_seconds']:.3f}s.")
    return "  ".join(parts)


def write_contact_sheet(rows: list, pages: list, out_dir: str) -> str:
    klass = {"HIS": "hit", "CLOSE": "chance", "OTHER": "miss", "NONE": "miss"}
    cells = [f'<figure class="{klass[row["verdict"]]}"><img src="{os.path.basename(page)}" loading="lazy">'
             f'<figcaption><b>{row["key"]}</b> — {row["verdict"]} · from the one trend end alone: '
             f'{row["one_verdict"]}</figcaption></figure>' for row, page in zip(misses_first(rows), pages)]
    html = f"""<!doctype html><meta charset="utf-8">
<title>The walk on his 35</title>
<style>
 body{{font:14px/1.5 system-ui,sans-serif;margin:24px;background:#faf9f7;color:#222}}
 h1{{font-size:20px}}
 .grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(520px,1fr));gap:18px}}
 figure{{margin:0;padding:8px;border:2px solid #ddd;border-radius:6px;background:#fff}}
 figure.miss{{border-color:#d62728}} figure.chance{{border-color:#e8a33d}} figure.hit{{border-color:#2e8b57}}
 img{{width:100%;height:auto}} figcaption{{padding-top:6px;font-size:13px}}
</style>
<h1>The walk on his 35 — the box the reader shows on his last receding day</h1>
<p>OHLC bars. Red: his two lines, their areas, his anchors (circles), his box (shaded), his last receding days
 (brown). Grey: the reader's line as of his last receding day. Blue dashed: the reader's box, from its anchors
 (circles) to the right; blue dotted: the day it became a box; the blue wedge is the trend end it walked from.
 Green dash-dot: the box the walk from the one trend end into his box alone would show, when it differs. Misses
 first.</p>
<div class="grid">{''.join(cells)}</div>
"""
    path = os.path.join(out_dir, "index.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pages", metavar="DIR", help="also write one OHLC page per drawing and a contact sheet here")
    args = ap.parse_args()
    setups = load_corpus()
    frames, _ = load_sealed_fixture()
    started = time.perf_counter()
    rows = run_board(setups, frames)
    print(format_board(rows))
    print(f"  {len(rows)} drawings read in {time.perf_counter() - started:.1f}s")
    if args.pages:
        pages = render_pages(rows, {setup_key(s): s for s in setups}, args.pages)
        print(f"  {len(pages)} pages · contact sheet {write_contact_sheet(rows, pages, args.pages)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
