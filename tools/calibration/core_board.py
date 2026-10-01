"""The core's board and the core sitting's pictures (task 12a of the two-eyes-reader build): on his 35 drawings
and on the 16 junk charts, the reader's OWN box, its LPS and its trigger — nothing else.

Per drawing, read on his last receding day as the scan would read it (the long frame cut at the day, the universe
door before the read):

* the box the reader shows against his two lines: HIS (both to the cent), CLOSE (both within half a daily range),
  OTHER;
* the LPS: whether the reader fires that day, on his day, at his trigger; when it does not, why — the door, the
  day does not recede, or which of his four sentences refused the pullback;
* his buy day: crossed (nothing on the board), or — when the day made a lower low as well — the pullback going on.

Per junk chart, on every day of its fired window: the fire days, and for the silent days the sentence that refused.

Offline, read-only, sidecars only: it reads the frozen as-drawn frames and writes to a directory you name.

    python -m tools.calibration.core_board                       # the board
    python -m tools.calibration.core_board --pages OUT           # the board AND one OHLC page per chart
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
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
from engine_alpha.evaluation import apply_baseline_filters_with_reason  # noqa: E402
from engine_alpha.two_eyes import lps, walk  # noqa: E402
from engine_alpha.two_eyes import method_numbers as M  # noqa: E402
from tools.calibration.yardstick import his_last_lps_day, rails_close  # noqa: E402
from tools.regression import negative_corpus  # noqa: E402
from tools.regression.marks_corpus import load_corpus, setup_key  # noqa: E402
from core.calibration.replay import fired_window_sessions, fixture_frame, load_sealed_fixture  # noqa: E402

VERDICTS = ("HIS", "CLOSE", "OTHER", "NONE")
#: The same verdicts on the pages, which speak to him.
_TO_HIM = {"HIS": "YOURS", "CLOSE": "CLOSE", "OTHER": "OTHER", "NONE": "NONE"}
DOOR = "the universe door"
ADVANCES = "the day does not recede"
NO_BOX = "no box"


def _date(value) -> Optional[dt.date]:
    if value is None or isinstance(value, dt.date):
        return value
    return dt.date.fromisoformat(str(value)[:10])


def _day(d) -> str:
    return d.strftime("%a %d/%m/%Y")


def read_day(ticker: str, raw, day) -> dict:
    """One day's read as the scan would make it, with the pullback the reader measured (fired or refused)."""
    cut = raw.loc[:pd.Timestamp(day)]
    started = time.perf_counter()
    read = two_eyes.read(ticker, cut)
    seconds = time.perf_counter() - started
    admitted, reason = apply_baseline_filters_with_reason(cut)
    out = {"day": _date(day), "read": read, "seconds": seconds, "door": None if admitted is not None else reason[0],
           "fired": bool(read.fired and admitted is not None), "pullback": None, "prepared": None, "raw": raw}
    if read.failed or read.parent is None:
        return out
    prepared = two_eyes.prepare(cut)
    line = two_eyes.build_line(prepared)
    ranges = prepared[two_eyes.DAILY_RANGE].to_numpy(dtype=float)
    far = line.far(M.FAR_VIEW_FLOOR_RANGES)
    high, low = prepared["High"].to_numpy(dtype=float), prepared["Low"].to_numpy(dtype=float)
    found = walk.elect(line.committed, [t for t in far if t.committed], ranges, high, low,
                       read_bar=len(prepared) - 1)
    won = found.winner
    out.update(prepared=prepared, won=won, found=found, line=line,
               pullback=lps.read(high, low, ranges, line.committed, R=won.R, S=won.S, box_unit=won.unit,
                                 born_bar=won.birth_bar))
    return out


def why_silent(row: dict) -> Optional[str]:
    """Why the day shows no fire, in one phrase; None when it fires."""
    if row["fired"]:
        return None
    read, pullback = row["read"], row["pullback"]
    if read.failed:
        return f"the read failed: {read.refusal}"
    if row["door"] is not None:
        return f"{DOOR} ({row['door']})"
    if read.parent is None:
        return NO_BOX
    if pullback is None:
        return ADVANCES
    if pullback.end_bar < len(row["prepared"]) - 1:
        return ADVANCES + (": the buy day" if read.state == lps.CROSSED else "")
    if pullback.refused:
        return "; ".join(pullback.refused)
    return "the box was not yet a box"


def verdict(box, rails: dict, unit: float) -> str:
    if box is None:
        return "NONE"
    if abs(box.resistance.price - rails["R"]) < 0.005 and abs(box.support.price - rails["S"]) < 0.005:
        return "HIS"
    close = rails_close(rails["R"], rails["S"], box.resistance.price, box.support.price, unit)
    return "CLOSE" if close else "OTHER"


def score_setup(setup: dict, raw) -> dict:
    days = [d.date() for d in raw.index]
    last = his_last_lps_day(setup)
    buy = _date(setup.get("trigger"))
    on_last = read_day(setup["ticker"], raw, last)
    on_buy = read_day(setup["ticker"], raw, buy) if buy in days else None
    rails = setup["rails_drawn"]
    unit = None
    if on_last["prepared"] is not None:
        # His pair's own unit, as the reader measures a pair: the range of its second anchor's day.
        prepared = on_last["prepared"]
        second = max(pd.Timestamp(setup["anchors"]["R"]), pd.Timestamp(setup["anchors"]["S"]))
        unit = float(prepared[two_eyes.DAILY_RANGE].loc[second])
    read = on_last["read"]
    his_trigger = on_last["fired"] and read.lps.end_day == last and \
        abs(read.lps.trigger_price - float(setup["trigger_price"])) < 0.005
    return {"key": setup_key(setup), "ticker": setup["ticker"], "setup": setup, "raw": raw, "last": last, "buy": buy,
            "on_last": on_last, "on_buy": on_buy, "unit": unit,
            "box": "NONE" if unit is None else verdict(read.parent, rails, unit),
            "strict": bool(his_trigger), "why": why_silent(on_last)}


def run_board(setups: list, frames: dict) -> list:
    return [score_setup(s, fixture_frame(frames, setup_key(s), s["ticker"])) for s in setups]


def junk_row(case: dict, raw) -> dict:
    """One junk chart on every day of its fired window (the junk corpus's own window)."""
    sessions, _ = fired_window_sessions(raw, raw.index[-1], [])
    reads = [read_day(case["ticker"], raw, ts.date()) for ts in sessions]
    return {"key": case.get("key", case["ticker"]), "ticker": case["ticker"], "label": case["label"], "raw": raw,
            "reads": reads, "fires": [r for r in reads if r["fired"]]}


def junk_rows() -> list:
    frames, meta = negative_corpus._load_fixture()
    return [junk_row(case, frames[case.get("key", case["ticker"])]) for case in meta["cases"]]


# --------------------------------------------------------------------------- #
# The board                                                                   #
# --------------------------------------------------------------------------- #
def _names(rows) -> str:
    return ", ".join(sorted(r["key"] for r in rows)) or "none"


def format_board(rows: list) -> str:
    n = len(rows)
    out = [f"THE CORE ON HIS {n} — the reader's own box, its LPS and its trigger, on his last receding day", ""]
    counts = {v: sum(1 for r in rows if r["box"] == v) for v in VERDICTS}
    out.append("  THE BOX: " + " · ".join(f"{v} {counts[v]}" for v in VERDICTS))
    strict = [r for r in rows if r["strict"]]
    out.append(f"  FIRES ON HIS DAY AT HIS TRIGGER: {len(strict)} of {n}")
    silent = {}
    for r in rows:
        if not r["strict"]:
            silent.setdefault(r["why"] or "fired, not on his day at his trigger", []).append(r)
    for why, group in sorted(silent.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        out.append(f"      {len(group)} · {why}: {_names(group)}")
    exact = [r for r in rows if r["strict"] and r["box"] == "HIS"]
    out.append(f"  his box to the cent AND a fire on his day at his trigger: {len(exact)} of {n} ({_names(exact)})")
    bought = [r for r in strict if r["on_buy"] is not None]
    crossed = [r for r in bought if r["on_buy"]["read"].state == lps.CROSSED]
    goes_on = [r for r in bought if r["on_buy"]["read"].state == lps.FIRED]
    out.append(f"  ON HIS BUY DAY, of the {len(bought)} that fired: crossed, nothing on the board {len(crossed)} · the "
               f"day made a lower low too and the pullback goes on {len(goes_on)} ({_names(goes_on)})")
    seconds = sorted(r["on_last"]["seconds"] for r in rows)
    out.append(f"  the whole read: median {seconds[len(seconds) // 2]:.3f}s · worst {seconds[-1]:.3f}s (budget 0.2)")
    out.append("")
    out.append(f"  {'drawing':<18}{'box':<7}{'his day':<26}the reader's words")
    for r in misses_first(rows):
        said = next((s.saying for s in r["on_last"]["read"].trail if s.stage == "LPS"), "")
        his_day = "FIRES, his trigger" if r["strict"] else (r["why"] or "fires elsewhere")
        out.append(f"  {r['key']:<18}{r['box']:<7}{his_day[:24]:<26}{said[:150]}")
    return "\n".join(out)


def format_junk(rows: list) -> str:
    firing = [r for r in rows if r["fires"]]
    out = ["", f"THE JUNK — charts that fire on any day of their window: {len(firing)} of {len(rows)} "
               f"({_names(firing)}) · silent: {_names([r for r in rows if not r['fires']])}"]
    for r in sorted(rows, key=lambda r: (-len(r["fires"]), r["key"])):
        fires = ", ".join(f"{f['day']:%d/%m} at {f['read'].lps.trigger_price:.2f}" for f in r["fires"]) or "none"
        whys = {}
        for read in r["reads"]:
            why = why_silent(read)
            if why is not None and not why.startswith(ADVANCES):
                whys[why] = whys.get(why, 0) + 1
        refused = "; ".join(f"{k} x{v}" for k, v in sorted(whys.items(), key=lambda kv: -kv[1])) or "-"
        box = r["reads"][-1]["read"].parent
        lines = "no box" if box is None else f"{box.resistance.price:.2f} / {box.support.price:.2f}"
        out.append(f"  {r['key']:<18}{r['label'][:34]:<36}box {lines:<18} fires: {fires}")
        out.append(f"  {'':<18}silent days: {refused}")
    return "\n".join(out)


def misses_first(rows: list) -> list:
    order = {"OTHER": 0, "NONE": 0, "CLOSE": 1, "HIS": 2}
    return sorted(rows, key=lambda r: (r["strict"], order[r["box"]], r["key"]))


# --------------------------------------------------------------------------- #
# The pictures — OHLC bars, never candles                                     #
# --------------------------------------------------------------------------- #
_HIS = "#d62728"        # his lines, red
_BOX = "#1f77b4"        # the reader's box, blue
_EARLIER = "#9ec5e6"    # a box the reader handed over
_LPS = "#2e8b57"        # the reader's LPS, green
_CROSSED = "#c77d0a"    # the LPS whose trigger the read day crossed: the buy day
_REFUSED = "#7a7a7a"    # a pullback one of his sentences refused
_LEAD_IN = 45
_AFTER = 6
_LONGEST = 260          # calendar days of box shown before the read day, at most


def _draw_box(ax, box, at, first_day, last_x, colour, width, label=None):
    """A box's two lines, each from its own anchor day (or the picture's left edge) to the day it ended."""
    end = last_x if box.end_day is None else at(box.end_day)
    for line, name in ((box.resistance, "R"), (box.support, "S")):
        start = at(max(line.anchor_day, first_day))
        if end is None or start is None or end < start:
            continue
        ax.plot([start, end], [line.price, line.price], color=colour, lw=width, ls="--", zorder=4)
        if label:
            ax.annotate(f"{label} {name} {line.price:.2f}", (0.70, line.price), xycoords=("axes fraction", "data"),
                        color=colour, fontsize=8.5, va="bottom", zorder=5)


def pullback_look(row: dict) -> tuple:
    """How a day's pullback is drawn: ``(colour, word)`` — the LPS green with its trigger (said so when the door
    refuses the day), the LPS bought that day amber, anything else grey."""
    read = row["read"]
    if read.fired:
        return _LPS, "trigger" if row["door"] is None else "not scanned; trigger"
    if read.state == lps.CROSSED:
        return _CROSSED, "crossed"
    return _REFUSED, "no LPS"


def _draw_pullback(ax, pullback, at, days, colour: str, word: str):
    top, end = at(days[pullback.top_bar]), at(days[pullback.end_bar])
    if top is None or end is None:
        return
    ax.axvspan(top - .4, end + .4, color=colour, alpha=.16, zorder=1)
    ax.plot([end - .4, end + 3.5], [pullback.trigger, pullback.trigger], color=colour, lw=1.8, zorder=6)
    ax.annotate(f"{word} {pullback.trigger:.2f}", (end + 3.6, pullback.trigger), color=colour, fontsize=8.5,
                va="center", zorder=7)


def _render(plt, draw_bars, row: dict, path: str, title: str, words: str, his: Optional[dict] = None,
            marks: Optional[list] = None):
    """One chart: the bars, the reader's box (blue), the boxes it handed over (pale), its pullback (green when it
    is the LPS, grey when one of his sentences refused it), the trigger; his lines and his days in red. The
    chart is READ on the dotted day; the few bars after it are what came next, and the reader never saw them."""
    read, pullback = row["read"], row["pullback"]
    box = read.parent
    days = [d.date() for d in row["prepared"].index]
    first = box.opened_day if his is None else min(box.opened_day, _date(his["box"][0]))
    first = max(first, row["day"] - dt.timedelta(days=_LONGEST))
    sessions = [d.date() for d in row["raw"].index]
    lo = max(0, next(i for i, d in enumerate(sessions) if d >= first) - _LEAD_IN)
    hi = min(len(sessions), sessions.index(row["day"]) + 1 + _AFTER)
    view = row["raw"].iloc[lo:hi]
    shown = sessions[lo:hi]
    where = {d: i for i, d in enumerate(shown)}
    at = where.get
    fig, ax = plt.subplots(figsize=(16, 8))
    draw_bars(ax, view["Open"].values, view["High"].values, view["Low"].values, view["Close"].values)
    ax.axvline(at(row["day"]) + .5, color="#444", lw=1, ls=":", zorder=2)
    ax.annotate(f"read on {_day(row['day'])}", (at(row["day"]) + .5, 0.985), xycoords=("data", "axes fraction"),
                color="#444", fontsize=8, ha="right", va="top", rotation=90)
    if his is not None:
        rails = his["rails_drawn"]
        for price, name in ((rails["R"], "your R"), (rails["S"], "your S")):
            ax.axhline(price, color=_HIS, lw=1.2, zorder=3)
            ax.annotate(f"{name} {price:.2f}", (0.004, price), xycoords=("axes fraction", "data"), color=_HIS,
                        fontsize=9, va="bottom", zorder=5)
        span = his.get("lps2") or his.get("lps")
        if span and at(_date(span[0])) is not None and at(_date(span[1])) is not None:
            floor = float(view["Low"].min())
            ax.plot([at(_date(span[0])) - .4, at(_date(span[1])) + .4], [floor] * 2, color=_HIS, lw=4,
                    solid_capstyle="butt", zorder=6)
            ax.annotate("your LPS days", (at(_date(span[0])), floor), xytext=(0, 6), textcoords="offset points",
                        color=_HIS, fontsize=8)
        if his.get("trigger_price") and at(_date(his.get("trigger"))) is not None:
            ax.plot([at(_date(his["trigger"]))], [his["trigger_price"]], marker="^", ms=10, color=_HIS, zorder=7)
    for earlier in (b for b in read.boxes if b.role == two_eyes.ROLE_EARLIER):
        if earlier.end_day is not None and earlier.end_day >= shown[0]:
            _draw_box(ax, earlier, at, shown[0], None, _EARLIER, 1.2)
    _draw_box(ax, box, at, shown[0], at(row["day"]), _BOX, 1.7, "reader's")
    if pullback is not None:
        _draw_pullback(ax, pullback, at, days, *pullback_look(row))
    for mark in marks or []:
        if at(mark["day"]) is not None:
            ax.plot([at(mark["day"])], [mark["price"]], marker="v", ms=9, color=_LPS, zorder=7)
    n = len(view)
    step = max(1, n // 12)
    ax.set_xticks(range(0, n, step))
    ax.set_xticklabels([shown[i].strftime("%d/%m/%y") for i in range(0, n, step)], fontsize=8)
    ax.set_xlim(-2, n + 4)
    ax.set_title(title, fontsize=13, loc="left", fontweight="bold")
    ax.set_xlabel(textwrap.fill(words, 210), fontsize=9.5, labelpad=8)
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)


def _words(read, door: Optional[str]) -> str:
    box = next((s.saying for s in read.trail if s.stage == "box"), "")
    said = next((s.saying for s in read.trail if s.stage == "LPS"), "")
    closed = f"  The universe door refuses the day ({door}): not scanned." if door else ""
    return f"The box: {box}.  {said[:1].upper()}{said[1:]}.{closed}"


def render_pages(rows: list, junk: list, out_dir: str) -> tuple:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from tools.research.full_package_render import _draw_bars

    os.makedirs(out_dir, exist_ok=True)
    his_pages, junk_pages = [], []
    for row in misses_first(rows):
        on_last = row["on_last"]
        if on_last["prepared"] is None:
            continue
        path = os.path.join(out_dir, f"his_{row['key'].replace(':', '_')}.png")
        fire = "FIRES on your day at your trigger" if row["strict"] else f"no fire on your day: {row['why']}"
        _render(plt, _draw_bars, on_last, path, f"{row['key']}  —  box {_TO_HIM[row['box']]} · {fire}",
                _words(on_last["read"], on_last["door"]), his=row["setup"])
        his_pages.append((row, path))
    for row in sorted(junk, key=lambda r: (-len(r["fires"]), r["key"])):
        shown = (row["fires"] or [r for r in row["reads"] if r["prepared"] is not None])[-1:]
        if not shown:
            continue
        last = shown[0]
        marks = [{"day": f["day"], "price": f["read"].lps.trigger_price} for f in row["fires"] if f is not last]
        path = os.path.join(out_dir, f"junk_{row['key'].replace('@', '_')}.png")
        fires = (f"fires on {len(row['fires'])} day(s) of its window, the last {_day(last['day'])}" if row["fires"]
                 else "fires on no day of its window")
        _render(plt, _draw_bars, last, path, f"{row['key']} ({row['label']})  —  {fires}",
                _words(last["read"], last["door"]), marks=marks)
        junk_pages.append((row, path))
    return his_pages, junk_pages


def write_contact_sheet(his_pages: list, junk_pages: list, out_dir: str) -> str:
    def cell(klass, path, caption):
        return (f'<figure class="{klass}"><img src="{os.path.basename(path)}" loading="lazy">'
                f'<figcaption>{caption}</figcaption></figure>')

    his = [cell("hit" if row["strict"] and row["box"] == "HIS" else "chance" if row["strict"] else "miss", path,
                f"<b>{row['key']}</b> — box {_TO_HIM[row['box']]} · "
                + ("fires on your day at your trigger" if row["strict"] else f"no fire: {row['why']}"))
           for row, path in his_pages]
    junk = [cell("miss" if row["fires"] else "hit", path,
                 f"<b>{row['key']}</b> — {row['label']} · "
                 + (f"fires on {len(row['fires'])} day(s)" if row["fires"] else "silent"))
            for row, path in junk_pages]
    html = f"""<!doctype html><meta charset="utf-8">
<title>The core sitting</title>
<style>
 body{{font:14px/1.5 system-ui,sans-serif;margin:24px;background:#faf9f7;color:#222}}
 h1{{font-size:20px}} h2{{font-size:17px;margin-top:32px}}
 .grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(520px,1fr));gap:18px}}
 figure{{margin:0;padding:8px;border:2px solid #ddd;border-radius:6px;background:#fff}}
 figure.miss{{border-color:#d62728}} figure.chance{{border-color:#e8a33d}} figure.hit{{border-color:#2e8b57}}
 img{{width:100%;height:auto}} figcaption{{padding-top:6px;font-size:13px}}
</style>
<h1>The core sitting — the reader's own box, its LPS and its trigger</h1>
<p>OHLC bars. Blue dashed: the reader's box, each line from its own anchor day; pale blue: an earlier box, handed
 over, as this day's read tells it (the reader keeps no memory). Green band: the reader's LPS, from its top day to its last receding day, and the green line is
 its trigger, that day's high. Amber band: the LPS whose trigger the read day crossed, the buy day. Grey band: a
 pullback one of your four sentences refused (the words under the picture name the sentence). Red: your two lines, your LPS days (the bar along the bottom) and your buy (the
 triangle). Each chart is read on your last receding day. Misses first.</p>
<h2>Your {len(his_pages)} drawings</h2>
<div class="grid">{''.join(his)}</div>
<h2>The {len(junk_pages)} junk charts</h2>
<p>Each is shown on the last day it fires in its ten-day window (small green wedges mark its other fire days), or
 on the window's last day when it never fires.</p>
<div class="grid">{''.join(junk)}</div>
"""
    path = os.path.join(out_dir, "index.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pages", metavar="DIR", help="also write one OHLC page per chart and a contact sheet here")
    args = ap.parse_args()
    setups = load_corpus()
    frames, _ = load_sealed_fixture()
    started = time.perf_counter()
    rows = run_board(setups, frames)
    junk = junk_rows()
    print(format_board(rows))
    print(format_junk(junk))
    print(f"\n  {len(rows)} drawings and {len(junk)} junk charts read in {time.perf_counter() - started:.1f}s")
    if args.pages:
        his_pages, junk_pages = render_pages(rows, junk, args.pages)
        sheet = write_contact_sheet(his_pages, junk_pages, args.pages)
        print(f"  {len(his_pages) + len(junk_pages)} pages · contact sheet {sheet}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
