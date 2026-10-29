"""The way-back board (task 6 of the two-eyes go-live plan): how long a box had failed before the reader gave it its
place back, on his drawings and on the junk fires, measured before his FRPH ruling of Fri 09/10/2026 is built.

The reader gives a box its place back (``walk.came_back_to``) on the first day the bars are back at both its lines
after the price left it downward and a lower box took its place — however long ago. His FRPH ruling: a box that
failed into a lower level that became its own thing for two months is not tied to the box any more. Per read that
RESTS on a way back (``approval_pack.rests_on_the_way_back``), on his buy day and on his last receding day, and on
every fire day of the 16 junk charts:

* the box given back (its two lines and its daily range);
* the day the price left it downward (the day after the last bar that reached the box's support area before the
  reader gave it up), the day the reader gave it up, and the day it came back;
* how long it had failed, in trading days, both from the day the price left and from the day it was given up;
* how far under the support the price went meanwhile, in that box's daily ranges.

And, for the cut's cost, every place given back anywhere in the history of his reads on his buy day (not only the
one the shown box rests on). ``--pictures`` draws FRPH's last fire day and the drawings of his named, on OHLC bars.
Offline, read-only, sidecars only.

    python -m tools.calibration.way_back_board                              # the board
    python -m tools.calibration.way_back_board --out FILE                   # the board, also written to FILE
    python -m tools.calibration.way_back_board --pictures DIR --his DLX MS  # and the pictures
"""
from __future__ import annotations

import argparse
import os
import sys
from typing import Optional

try:
    from tools._bootstrap import configure_path, refuse_sealed_output
except ImportError:  # invoked as a script from the repo root
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from tools._bootstrap import configure_path, refuse_sealed_output  # type: ignore
configure_path(backend=True)


def failed_for(box, high, low, given_up: int, back: int) -> dict:
    """One place given back, measured: the day the price left the box downward (the day after the last bar, on or
    before the day it was given up, that reached the support's area), the trading days from there and from the
    day it was given up to the day it came back, and how far under the support it went, in its daily ranges."""
    reached = [b for b in range(given_up, -1, -1) if high[b] >= box.S - box.area]
    left = (reached[0] + 1) if reached else 0
    floor = float(low[left:back].min()) if back > left else float(low[back])
    return {"R": box.R, "S": box.S, "unit": box.unit, "left": left, "given_up": given_up, "back": back,
            "failed_days": back - left, "given_up_days": back - given_up, "depth": (box.S - floor) / box.unit}


def way_backs(found, high, low) -> list:
    """Every place given back in a read's history, oldest first, each measured (``failed_for``) with its index
    in the read's lives."""
    from engine_alpha.two_eyes import walk

    lives = list(getattr(found, "lives", None) or ())
    return [{"index": k, **failed_for(life.pair, high, low, int(lives[k - 1].shown_bar), int(life.shown_bar))}
            for k, life in enumerate(lives) if life.why == walk.CAME_BACK and k >= 1]


def resting(found, high, low) -> Optional[dict]:
    """The place given back the shown box rests on (the approval pack's ``rests_on_the_way_back``), measured."""
    from engine_alpha.two_eyes import walk

    lives = list(getattr(found, "lives", None) or ())
    for k in range(len(lives) - 1, -1, -1):
        if lives[k].why == walk.CAME_BACK:
            return next(w for w in way_backs(found, high, low) if w["index"] == k)
        if lives[k].why in (walk.LIVE_TREND, walk.FIRST_BOX, walk.WRAPS):
            return None
    return None


def _arrays(read: dict) -> tuple:
    prepared = read["prepared"]
    return (prepared["High"].to_numpy(dtype=float), prepared["Low"].to_numpy(dtype=float),
            [d.date() for d in prepared.index])


def _entry(key: str, when: str, read: dict, setup=None) -> dict:
    high, low, days = _arrays(read)
    return {"key": key, "when": when, "day": read["day"], "read": read, "setup": setup, "days": days,
            "w": resting(read["found"], high, low)}


def collect() -> tuple:
    """``(his, junk, history)``: the resting way backs on his drawings (buy day and last receding day), on every
    junk fire day, and every place given back in his reads' histories on his buy day."""
    from tools.calibration import approval_pack, core_board
    from tools.regression.marks_corpus import load_sealed_standard

    setups, frames, _ = load_sealed_standard()
    his, history = [], []
    for row in core_board.run_board(setups, frames):
        for when, read in (("buy day", row["on_buy"]), ("last receding day", row["on_last"])):
            if read is None or read.get("found") is None:
                continue
            if when == "buy day":
                high, low, days = _arrays(read)
                history.extend((row["key"], w, days) for w in way_backs(read["found"], high, low))
            if approval_pack.rests_on_the_way_back(read["found"]):
                his.append(_entry(row["key"], when, read, row["setup"]))
    junk = [_entry(row["key"], "fire day", fire) for row in core_board.junk_rows() for fire in row["fires"]
            if approval_pack.rests_on_the_way_back(fire.get("found"))]
    return his, junk, history


def _line(who: str, day, w: dict, days) -> str:
    return (f"  {who:<34} {day:%a %d/%m/%Y}  box {w['R']:.2f} / {w['S']:.2f} (range {w['unit']:.2f})  "
            f"left {days[w['left']]:%d/%m/%Y}  given up {days[w['given_up']]:%d/%m/%Y}  "
            f"back {days[w['back']]:%d/%m/%Y}  failed {w['failed_days']:>3} days  "
            f"(given up {w['given_up_days']:>3})  under by {w['depth']:.1f} ranges")


def format_board(his: list, junk: list, history: list) -> str:
    lines = ["THE WAY-BACK BOARD: how long the box had failed before it took its place back",
             "  (failed = trading days from the day the price left the box downward to the day it came back;",
             "   given up = from the day the reader gave it up; under by = how far under its support, in its daily "
             "ranges)", "", "HIS DRAWINGS whose shown box rests on a way back"]
    lines += [_line(f"{e['key']} [{e['when']}]", e["day"], e["w"], e["days"]) for e in his]
    lines += ["", "THE JUNK FIRE DAYS whose shown box rests on a way back"]
    lines += [_line(e["key"], e["day"], e["w"], e["days"]) for e in junk]
    frph = [e["w"] for e in junk if e["key"].startswith("FRPH")]
    for name, field, unit in (("failed", "failed_days", "days"), ("given up", "given_up_days", "days"),
                              ("under by", "depth", "ranges")):
        mine = sorted({round(e["w"][field], 1) for e in his})
        theirs = sorted({round(w[field], 1) for w in frph})
        lines.append(f"  {name:<9} his five: {mine} {unit}; FRPH: {theirs} {unit}")
    lines += ["", "EVERY PLACE GIVEN BACK in the history of his reads on his buy day (what a cut would also touch)"]
    for key, w, days in sorted(history, key=lambda h: -h[1]["failed_days"]):
        lines.append(_line(key, days[w["back"]], w, days))
    return "\n".join(lines)


def render(entry: dict, path: str, title: str) -> str:
    """One OHLC-bar picture of a read that rests on a way back: the box given back (blue dashes) with the days it
    had failed shaded, the day it was given up and the day it came back marked, the box shown on the read day
    (dark), and his lines in red when the chart is his."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from tools.research.full_package_render import _draw_bars

    read, w, days = entry["read"], entry["w"], entry["days"]
    prepared, end = read["prepared"], days.index(entry["day"])
    start = max(0, w["left"] - 60)
    view = prepared.iloc[start:end + 1]
    fig, ax = plt.subplots(figsize=(16, 8))
    _draw_bars(ax, view["Open"].values, view["High"].values, view["Low"].values, view["Close"].values)
    x = lambda bar: bar - start     # noqa: E731
    ax.axvspan(x(w["left"]) - .5, x(w["back"]) - .5, color="#d9534f", alpha=.10, zorder=1)
    for price in (w["R"], w["S"]):
        ax.plot([0, x(end)], [price, price], color="#1f5fbf", lw=1.4, ls="--", zorder=4)
    ax.annotate(f"box given back {w['R']:.2f} / {w['S']:.2f}: failed {w['failed_days']} trading days, "
                f"{w['depth']:.1f} daily ranges under", (x(w["left"]), w["R"]), color="#1f5fbf", fontsize=9,
                va="bottom")
    for bar, word in ((w["given_up"], "given up"), (w["back"], "came back")):
        ax.axvline(x(bar), color="#555", lw=1, ls=":", zorder=2)
        ax.annotate(f"{word} {days[bar]:%d/%m/%Y}", (x(bar), 0.98), xycoords=("data", "axes fraction"),
                    color="#555", fontsize=8, rotation=90, ha="right", va="top")
    shown = read["read"].parent
    if shown is not None:
        for line in (shown.resistance, shown.support):
            ax.plot([0, x(end)], [line.price, line.price], color="#222", lw=1.0, zorder=3)
    if entry["setup"] is not None:
        for price in (entry["setup"]["rails_drawn"]["R"], entry["setup"]["rails_drawn"]["S"]):
            ax.axhline(price, color="#d62728", lw=1.2, zorder=3)
    ticks = list(range(0, len(view), 15))
    ax.set_xticks(ticks, [f"{days[start + t]:%d/%m/%y}" for t in ticks], fontsize=8)
    ax.set_title(title, fontsize=11)
    fig.tight_layout()
    fig.savefig(path, dpi=90)
    plt.close(fig)
    return path


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", metavar="FILE", help="also write the board to this file")
    ap.add_argument("--pictures", metavar="DIR", help="draw FRPH's last fire day and --his drawings here")
    ap.add_argument("--his", nargs="*", default=(), help="tickers of his drawings to draw beside FRPH")
    args = ap.parse_args(argv)
    for target in (args.out, args.pictures):
        if target:
            refuse_sealed_output(target)
    his, junk, history = collect()
    text = format_board(his, junk, history)
    print(text)
    if args.out:
        with open(args.out, "w", encoding="utf-8", newline="\n") as f:
            f.write(text + "\n")
    if args.pictures:
        os.makedirs(args.pictures, exist_ok=True)
        frph = [e for e in junk if e["key"].startswith("FRPH")][-1:]
        mine = [e for e in his if e["when"] == "buy day" and e["key"].split(":")[0] in set(args.his)]
        for e in frph + mine:
            name = e["key"].replace(":", "_").replace("@", "_")
            print(render(e, os.path.join(args.pictures, f"way_back_{name}.png"),
                         f"{e['key']} on its {e['when']} {e['day']:%a %d/%m/%Y}: the box given back failed "
                         f"{e['w']['failed_days']} trading days ({e['w']['depth']:.1f} daily ranges under)"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
