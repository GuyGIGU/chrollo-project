"""The walk's board (stages 2 to 4 of the two-eyes reader, on the rule of the pair he settled on Thu 01/10/2026):
on his drawings, does the reader show his pair on his last receding day, does the box's life keep it to his buy
day — and what does the rule itself say of his own two anchors.

Per drawing, on the reader's own line built on the frame cut at his day:

* his two anchors on the line (the listing gate's reading: exact, by price, near, or not a turn);
* THE BOX the reader shows on his last receding day (`engine_alpha.two_eyes.walk.elect`): HIS (both lines to the
  cent), CLOSE (both within half a daily range of his), OTHER, or NONE — and why it is shown: the first pair to
  become a box, or a hand-over (the box before it was anchored inside a live trend; the price left the box
  before it for good; a dip came back and the box took its place again);
* the box's life: the box shown on his BUY day, and how many boxes the reader handed over before his day (kept
  in the record as earlier boxes);
* HIS OWN PAIR read by the rule: whether it is a pair the rule lists (two swing ends a swing connects), whether
  it can be a box (a daily range tall, a counter move that took back a part only), the day the bars came back
  to each rail, the day it became a box — and, when it is a box by his buy day, whether a later pair takes its
  place before his buy by the reader's two hand-over rules;
* pairs listed, the walk's and the whole read's time against the plan's 0.2-second budget, the record's size.

And on the 16 junk charts: the box the reader shows on the frame's last day, and whether the price trades in it
— his dead-space rule (a box the price left and never came back to is no candidate; BMRN, OHI).

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
    from tools._bootstrap import configure_path, refuse_sealed_output
except ImportError:  # invoked as a script from the repo root
    import os, sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from tools._bootstrap import configure_path, refuse_sealed_output  # type: ignore
_ROOT = configure_path(backend=True)

from engine_alpha import two_eyes  # noqa: E402
from engine_alpha.two_eyes import frame as two_eyes_frame  # noqa: E402
from engine_alpha.two_eyes import line as two_eyes_line  # noqa: E402
from engine_alpha import two_eyes_numbers as M  # noqa: E402
from engine_alpha.two_eyes import walk  # noqa: E402
from tools.calibration.listing_gate import anchor_turns  # noqa: E402
from tools.calibration.yardstick import his_last_lps_day, rails_close  # noqa: E402
from tools.regression import negative_corpus  # noqa: E402
from tools.regression.marks_corpus import (load_corpus, load_sealed_standard, setup_key,  # noqa: E402
                                           stamp_line)
from core.calibration.replay import fixture_frame, load_sealed_fixture  # noqa: E402

#: The plan's named charts for tasks 10 and 11 (BMRN and OHI are junk charts: see the junk board).
NAMED = ("VIK", "SYRE", "ALB", "FOSL", "MSGS", "ROIV", "EWTX", "NGL", "VLO", "ST", "NOK")
BUDGET_SECONDS = 0.2
VERDICTS = ("HIS", "CLOSE", "OTHER", "NONE")
WHYS = (walk.FIRST_BOX, walk.LIVE_TREND, walk.LEFT_FOR_GOOD, walk.CAME_BACK)


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


def his_own_pair(found, r_bar: int, s_bar: int, rails: dict):
    """His two anchors as a pair the rule lists — two swing ends a swing connects, on his bars, at his prices to
    the cent — or None."""
    return next((p for p in found.pairs.values() if (p.r_bar, p.s_bar) == (r_bar, s_bar)
                 and abs(p.R - rails["R"]) < 0.005 and abs(p.S - rails["S"]) < 0.005), None)


def gives_way(pair, found, high, low, day: int):
    """The first later pair, in the order boxes are tried, that takes ``pair``'s place by ``day`` by the
    reader's two hand-over rules: ``(the pair, why)``, or None."""
    for other in sorted((p for p in found.pairs.values() if p.birth_bar is not None), key=walk._key):
        if other.opening_bar <= pair.opening_bar:
            continue
        if walk.left_for_good(pair, other, high, low, pair.birth_bar, day) is not None:
            return other, walk.LEFT_FOR_GOOD
        if walk.inside_a_live_trend(pair, other, found.ends, day) is not None:
            return other, walk.LIVE_TREND
    return None


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
    high, low = prepared["High"].to_numpy(dtype=float), prepared["Low"].to_numpy(dtype=float)
    rails = setup["rails_drawn"]
    r_bar, s_bar = days.index(_date(setup["anchors"]["R"])), days.index(_date(setup["anchors"]["S"]))
    first_bar, last_bar = min(r_bar, s_bar), days.index(his_last_lps_day(setup))
    unit = float(ranges[max(r_bar, s_bar)])
    turns = list(line.turns)
    far = line.far(M.FAR_VIEW_FLOOR_RANGES)

    def on(day: int):
        return walk.elect(walk.known_by(turns, day), walk.known_by(far, day), ranges, high, low, days=days,
                          read_bar=day)

    started = time.perf_counter()
    result = on(last_bar)
    walk_seconds = time.perf_counter() - started
    buy_bar = min(days.index(_date(setup["trigger"])) if setup.get("trigger") else last_bar, len(days) - 1)
    on_buy = on(buy_bar)
    his_pair = his_own_pair(on_buy, r_bar, s_bar, rails)
    _, trail, _ = walk.record(result)
    return {
        "key": setup_key(setup), "ticker": setup["ticker"], "as_of": as_of, "days": days, "prepared": prepared,
        "known": walk.known_by(turns, last_bar), "unit": unit, "rails": rails,
        "r_bar": r_bar, "s_bar": s_bar, "first_bar": first_bar, "last_bar": last_bar,
        "his": anchor_turns(turns, r_bar, s_bar, rails["R"], rails["S"], unit),
        "result": result, "box": result.winner, "verdict": verdict(result.winner, rails, unit),
        "why": result.lives[-1].why if result.lives else None,
        "buy_bar": buy_bar, "on_buy": on_buy, "buy_verdict": verdict(on_buy.winner, rails, unit),
        "hand_overs": max(0, len(result.lives) - 1),
        "his_pair": his_pair,
        "his_gives_way": None if his_pair is None or his_pair.birth_bar is None else
        gives_way(his_pair, on_buy, high, low, buy_bar),
        "pairs": len(result.pairs), "walk_seconds": walk_seconds, "read_seconds": read_seconds,
        "bytes": len(repr(trail)), "read": read,
    }


def run_board(setups: list, frames: dict) -> list:
    return [score_setup(s, fixture_frame(frames, setup_key(s), s["ticker"])) for s in setups]


# --------------------------------------------------------------------------- #
# The board                                                                   #
# --------------------------------------------------------------------------- #
def _med_worst(values, fmt="{:g}") -> str:
    values = [v for v in values if v is not None]
    if not values:
        return "-"
    return f"median {fmt.format(statistics.median(values))} · worst {fmt.format(max(values))}"


def _his_pair_words(row: dict) -> str:
    """His own pair by the rule, on his buy day."""
    hp, days = row["his_pair"], row["days"]
    if hp is None:
        return "not a pair the rule lists"
    if hp.unfit:
        return f"never a box: {hp.unfit}"
    if hp.birth_bar is None:
        missing = [n for n, got in (("resistance", hp.r_back), ("support", hp.s_back)) if got is None]
        return "no box by his buy: " + ("the bars not back at " + " and ".join(missing) if missing
                                        else "under 15 days")
    words = f"a box on {days[hp.birth_bar]:%d/%m}" + (" (15th day)" if hp.birth_bar == hp.fifteenth else "")
    if row["his_gives_way"] is not None:
        other, _ = row["his_gives_way"]
        words += f"; gives way to {other.R:.2f}/{other.S:.2f}"
    return words


def _difference(row: dict) -> str:
    box, rails, unit, days = row["box"], row["rails"], row["unit"], row["days"]
    if box is None:
        return "no box on his day"
    parts = []
    for name, got, his in (("R", box.R, rails["R"]), ("S", box.S, rails["S"])):
        off = (got - his) / unit
        parts.append(f"{name} same" if abs(off) < 0.005 else f"{name} {got:.2f} vs his {his:.2f} ({off:+.2f} ranges)")
    life = row["result"].lives[-1]
    parts.append(f"opened {days[box.opening_bar]:%d/%m}, shown from {days[life.shown_bar]:%d/%m}: {life.why}")
    return "; ".join(parts)


def format_board(rows: list) -> str:
    out = [f"THE WALK ON HIS {len(rows)} — the box the reader shows on his last receding day (far floor "
           f"{M.FAR_VIEW_FLOOR_RANGES} ranges, area {M.LINE_WORD_AREA_ATR} range, {M.BOX_DAYS} days, tall floor "
           f"{M.BOX_MIN_HEIGHT_RANGES} range)", ""]
    counts = {v: sum(1 for r in rows if r["verdict"] == v) for v in VERDICTS}
    out.append("  THE READER'S BOX: " + " · ".join(f"{v} {counts[v]}" for v in VERDICTS) + f"  (of {len(rows)})")
    out.append("  shown because: " + " · ".join(f"{w} {sum(1 for r in rows if r['why'] == w)}" for w in WHYS))
    buy = {v: sum(1 for r in rows if r["buy_verdict"] == v) for v in VERDICTS}
    ended = sorted(r["key"] for r in rows if r["his_gives_way"] is not None)
    out.append("  THE BOX'S LIFE — on his BUY day: " + " · ".join(f"{v} {buy[v]}" for v in VERDICTS)
               + f" · his own box gives way before his buy: {len(ended)} of {len(rows)}"
               + (f" ({', '.join(ended)})" if ended else "")
               + f" · boxes handed over before his day: {_med_worst([r['hand_overs'] for r in rows])}")
    listed = [r for r in rows if r["his_pair"] is not None]
    out.append(f"  his pair is a pair the rule LISTS: {len(listed)} of {len(rows)}"
               f" · a box by the rule by his buy day: {sum(1 for r in listed if r['his_pair'].birth_bar is not None)}"
               f" of {len(rows)}")
    out.append(f"  pairs listed: {_med_worst([r['pairs'] for r in rows])} · walk seconds: "
               f"{_med_worst([r['walk_seconds'] for r in rows], '{:.3f}')} · whole read seconds: "
               f"{_med_worst([r['read_seconds'] for r in rows], '{:.3f}')} (budget {BUDGET_SECONDS}) · trail bytes: "
               f"{_med_worst([r['bytes'] for r in rows])}")
    named = [f"{t} {next((r['verdict'] for r in rows if r['ticker'] == t), '?')}" for t in NAMED]
    out.append("  named charts: " + " · ".join(named))
    out.append("")
    out.append(f"  {'drawing':<16}{'his anchors':<14}{'box':<7}{'buy day':<9}{'earlier':>8}  "
               f"{'his pair by the rule':<46}{'pairs':>6}{'read s':>8}  where the box differs")
    for row in misses_first(rows):
        his = row["his"]
        anchors = f"{his['r_match'] or '-'}/{his['s_match'] or '-'}"
        out.append(f"  {row['key']:<16}{anchors:<14}{row['verdict']:<7}{row['buy_verdict']:<9}"
                   f"{row['hand_overs']:>8}  {_his_pair_words(row):<46}{row['pairs']:>6}"
                   f"{row['read_seconds']:>8.3f}  {_difference(row)}")
    return "\n".join(out)


# --------------------------------------------------------------------------- #
# The junk: a box the price left and never came back to is no candidate       #
# --------------------------------------------------------------------------- #
def junk_rows() -> list:
    """The 16 junk charts read on the fixture's last day: the box shown, where the last bar sits against its
    lines (inside their areas, or how many of the box's daily ranges beyond), the boxes handed over."""
    frames, _ = negative_corpus._load_fixture()
    rows = []
    for key, raw in frames.items():
        read = two_eyes.read(key, raw)
        box = read.parent
        high, low = float(raw["High"].iloc[-1]), float(raw["Low"].iloc[-1])
        if box is None:
            rows.append({"key": key, "box": None, "beyond": None, "earlier": 0, "read": read})
            continue
        # ONE judgment of "the price has run on past the box": the reader's own (state.side). The board only
        # adds how far, in the box's ranges.
        from engine_alpha.two_eyes import record as words, state as edge
        where = edge.side(high, low, box.resistance.price, box.support.price, M.LINE_WORD_AREA_ATR * box.daily_range)
        beyond = 0.0
        if where == words.BEYOND_R:
            beyond = (low - box.resistance.price) / box.daily_range
        elif where == words.UNDER_S:
            beyond = -(box.support.price - high) / box.daily_range
        rows.append({"key": key, "box": box, "beyond": beyond,
                     "earlier": sum(1 for b in read.boxes if b.role == two_eyes.ROLE_EARLIER), "read": read})
    return rows


def format_junk(rows: list) -> str:
    inside = [r for r in rows if r["box"] is not None and r["beyond"] == 0.0]
    out = [f"  THE JUNK, on the fixture's last day: the price trades in the box shown on {len(inside)} of {len(rows)}"
           f" · no box {sum(1 for r in rows if r['box'] is None)}"]
    for r in sorted(rows, key=lambda r: (r["box"] is not None, -abs(r["beyond"] or 0), r["key"])):
        box = r["box"]
        if box is None:
            out.append(f"    {r['key']:<16}no box")
            continue
        where = ("in the box" if r["beyond"] == 0.0 else
                 f"{abs(r['beyond']):.1f} ranges {'above' if r['beyond'] > 0 else 'under'} it")
        out.append(f"    {r['key']:<16}{box.resistance.price:.2f}/{box.support.price:.2f} opened "
                   f"{box.opened_day:%d/%m/%y}: {where}; {r['earlier']} earlier box(es) in the record")
    return "\n".join(out)


def misses_first(rows: list) -> list:
    order = {v: i for i, v in enumerate(reversed(VERDICTS))}
    return sorted(rows, key=lambda r: (order[r["verdict"]], r["key"]))


# --------------------------------------------------------------------------- #
# The pictures — OHLC bars, never candles                                     #
# --------------------------------------------------------------------------- #
_HIS = "#d62728"        # his lines, red
_ENGINE = "#1f77b4"     # the reader's box, blue
_EARLIER = "#9ec5e6"    # the boxes the reader handed over before his day
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
    prepared, days = row["prepared"], row["days"]
    box = row["box"]
    trend = walk._trend_before(row["result"], box) if box is not None else None
    lo = max(0, min(row["first_bar"], box.opening_bar if box is not None else row["first_bar"]) - _LEAD_IN)
    if trend is not None:
        lo = max(0, min(lo, trend["climax_bar"] - 10))
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

    # The boxes the reader handed over before his day: faint, from their anchors to the day their lines stop.
    for life in row["result"].lives[:-1]:
        p = life.pair
        if life.ended_bar < lo:
            continue
        for price, bar in ((p.R, p.r_bar), (p.S, p.s_bar)):
            ax.plot([x(max(bar, lo)), x(life.ended_bar)], [price, price], color=_EARLIER, lw=1.3, zorder=3)
        ax.annotate(f"earlier box, ended {days[life.ended_bar]:%d/%m}", (x(life.ended_bar), p.R), xytext=(4, 4),
                    textcoords="offset points", color=_EARLIER, fontsize=7.5, zorder=5)

    if box is not None:
        for price, bar, name in ((box.R, box.r_bar, "R"), (box.S, box.s_bar, "S")):
            ax.plot([x(bar), x(hi - 1)], [price, price], color=_ENGINE, lw=1.6, ls="--", zorder=4)
            ax.plot([x(bar)], [price], marker="o", ms=9, color=_ENGINE, mfc="white", mew=1.8, zorder=6)
            ax.annotate(f"reader's {name} {price:.2f}", (0.70, price), xycoords=("axes fraction", "data"),
                        color=_ENGINE, fontsize=8.5, va="bottom", zorder=5)
        ax.axvline(x(box.birth_bar), color=_ENGINE, lw=1.2, ls=":", zorder=3)
        ax.annotate(f"reader's box on {days[box.birth_bar]:%d/%m}", (x(box.birth_bar), 0.03),
                    xycoords=("data", "axes fraction"), color=_ENGINE, fontsize=8, ha="left", va="bottom")
        if trend is not None and trend["climax_bar"] >= lo:
            mark = "v" if trend["kind"] == "BC" else "^"
            ax.plot([x(trend["climax_bar"])], [trend["climax_price"]], marker=mark, ms=13, color=_END, zorder=7,
                    mec="white", mew=.8)
            ax.annotate("trend end the box follows", (x(trend["climax_bar"]), trend["climax_price"]),
                        xytext=(0, 14 if mark == "v" else -18), textcoords="offset points", color=_END, fontsize=8,
                        ha="center", zorder=8)

    n = len(view)
    step = max(1, n // 12)
    ax.set_xticks(range(0, n, step))
    ax.set_xticklabels([days[lo + i].strftime("%d/%m/%y") for i in range(0, n, step)], fontsize=8)
    ax.set_xlim(-2, n + 1)
    ax.set_title(f"{row['key']}  —  {row['verdict']}", fontsize=13, loc="left", fontweight="bold")
    ax.set_xlabel(textwrap.fill(_words(row), 210), fontsize=9.5, labelpad=8)
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)


def _words(row: dict) -> str:
    parts = []
    if row["his"]["why"]:
        parts.append(row["his"]["why"] + ".")
    parts.append(_difference(row).capitalize() + ".")
    parts.append(f"His own pair by the rule: {_his_pair_words(row)}.")
    if row["box"] is not None:
        parts.append("The trail: " + " → ".join(s.saying for s in row["read"].trail if s.stage != "trend end") + ".")
    if row["buy_verdict"] != row["verdict"]:
        parts.append(f"On his buy day the box is {row['buy_verdict']}.")
    parts.append(f"{row['pairs']} pairs listed; the whole read took {row['read_seconds']:.3f}s.")
    return "  ".join(parts)


def write_contact_sheet(rows: list, pages: list, out_dir: str) -> str:
    klass = {"HIS": "hit", "CLOSE": "chance", "OTHER": "miss", "NONE": "miss"}
    cells = [f'<figure class="{klass[row["verdict"]]}"><img src="{os.path.basename(page)}" loading="lazy">'
             f'<figcaption><b>{row["key"]}</b> — {row["verdict"]}</figcaption></figure>'
             for row, page in zip(misses_first(rows), pages)]
    html = f"""<!doctype html><meta charset="utf-8">
<title>The walk on his drawings</title>
<style>
 body{{font:14px/1.5 system-ui,sans-serif;margin:24px;background:#faf9f7;color:#222}}
 h1{{font-size:20px}}
 .grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(520px,1fr));gap:18px}}
 figure{{margin:0;padding:8px;border:2px solid #ddd;border-radius:6px;background:#fff}}
 figure.miss{{border-color:#d62728}} figure.chance{{border-color:#e8a33d}} figure.hit{{border-color:#2e8b57}}
 img{{width:100%;height:auto}} figcaption{{padding-top:6px;font-size:13px}}
</style>
<h1>The walk on his drawings — the box the reader shows on his last receding day</h1>
<p>OHLC bars. Red: his two lines, their areas, his anchors (circles), his box (shaded), his last receding days
 (brown). Grey: the reader's line as of his last receding day. Blue dashed: the reader's box, from its anchors
 (circles) to the right; blue dotted: the day it became a box; the blue wedge is the trend end it follows.
 Pale blue: the earlier boxes, handed over, as this day's read tells them (the reader keeps no memory), each to
 the day its lines stop. Misses first.</p>
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
    # EC-14: every write path is checked before anything is read (council review 2026-10-09, finding 9).
    if args.pages:
        refuse_sealed_output(args.pages)
    setups, frames, stamp = load_sealed_standard()     # the drawings and their bars, one set (EC-13)
    print(stamp_line(stamp))
    started = time.perf_counter()
    rows = run_board(setups, frames)
    print(format_board(rows))
    print(f"  {len(rows)} drawings read in {time.perf_counter() - started:.1f}s")
    print()
    print(format_junk(junk_rows()))
    if args.pages:
        pages = render_pages(rows, {setup_key(s): s for s in setups}, args.pages)
        print(f"  {len(pages)} pages · contact sheet {write_contact_sheet(rows, pages, args.pages)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
