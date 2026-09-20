"""The yardstick: one run, one board, one page per chart, on today's two engines.

Task 3 of the two-eyes-reader build. This is the bar the rewrite has to clear,
and the first honest number either engine has been given on his own 35 drawings.

**Why it exists.** Three sessions reported "35 of 37" for the twelve-step
method. That number was measured with HIS lines handed to the engine. Asked to
draw its own, the engine matched him on 12 of 35. The difference between those
two numbers is the whole rewrite, so the measurement has to be the strict one
from here on:

    the engine's OWN two lines carry a fire on HIS last receding day,
    at HIS trigger

and the looser reading — fired somewhere near his setup — rides beside it in a
"chance" column where it can be seen but never mistaken for the headline.

**Two arms, one tree.** "Today's engine" is the twelve-step method's 27
switches OFF; "the method" is all 27 ON. Both live in this checkout, so the
comparison needs no second branch: one run measures both.

**The picture and the number come from one run** (`--pages`), so a page can
never disagree with the count beside it.

Offline, read-only, sidecars only: it reads the frozen as-drawn frames and
writes to a directory you name. It never touches the archive (EC-46).

    python -m tools.yardstick                     # the board, both arms
    python -m tools.yardstick --pages OUT         # the board AND one page per chart
    python -m tools.yardstick --arm today         # one arm only
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import time
from typing import Optional

import pandas as pd

try:
    from tools._bootstrap import configure_path, refuse_sealed_output
except ImportError:  # invoked as a script from the repo root
    from _bootstrap import configure_path, refuse_sealed_output  # type: ignore
_ROOT = configure_path(backend=True)

from engine_alpha import reader  # noqa: E402
from engine_alpha.election_identity import projection  # noqa: E402
from tools.marks_corpus import load_corpus, setup_key  # noqa: E402
from tools.replay import (  # noqa: E402
    FROZEN_SPY_6M,
    drawn_box_window,
    fixture_frame,
    flag_capture,
    load_sealed_fixture,
    prepared_frame,
)

ARM_TODAY = "today"
ARM_METHOD = "method"

#: The twelve-step method, as the flag ledger's fate table records it. The arm
#: is only "the method" if it is ALL of them — a switch left out measures
#: something else under the method's name, which is why a test pins this list
#: against the ledger itself.
METHOD_SWITCHES = (
    "BASE_AGE_FROM_ANCHOR_ENABLED",
    "BOX_END_ENABLED",
    "BOX_HANDOVER_RANGES_ENABLED",
    "BOX_OPENS_ON_ANCHORS_ENABLED",
    "BOX_WIDTH_CAPS_GRADED_ENABLED",
    "CLIMAX_FIRST_WALK_ENABLED",
    "DEPTH_CAPS_GRADED_ENABLED",
    "DWELL_GRADED_ENABLED",
    "GRADE_LEDGER_ENABLED",
    "LINE_WORD_LAST_SUPPER_ENABLED",
    "LINE_WORD_MINI_ENABLED",
    "LINE_WORD_PHASE_C_ENABLED",
    "LINE_WORD_PHASE_D_ENABLED",
    "LINE_WORD_SOS_ENABLED",
    "LINE_WORD_UPTHRUST_ENABLED",
    "LPS_BUY_DAY_READS_HIGH_ENABLED",
    "LPS_GRADED_TRAITS_ENABLED",
    "LPS_LEAVES_ELECTION_ENABLED",
    "LPS_RANGES_YARDSTICK_ENABLED",
    "LPS_REFUSALS_TO_GRADES_ENABLED",
    "LPS_SELLERS_RISING_FATAL_ENABLED",
    "LPS_WINDOW_RECEDING_ENABLED",
    "RESPECT_GRADED_ENABLED",
    "RESPECT_WHOLE_BAR_ENABLED",
    "SPRING_BOUNDS_LIFTED_ENABLED",
    "TURN_LINE_ENABLED",
    "TURN_LINE_TREND_ENABLED",
)

#: How far his day may shift before a hit stops being a near miss. Three
#: trading days: his own redraws move a buy by a day or two, never a week.
DEFAULT_SHIFT_SESSIONS = 3

#: His rail area, as he taught it: about half a daily range either side.
RAIL_TOLERANCE_RANGES = 0.5


def arm_overrides(arm: str) -> dict:
    """Every method switch, set to what this arm means."""
    if arm == ARM_TODAY:
        return {name: False for name in METHOD_SWITCHES}
    if arm == ARM_METHOD:
        return {name: True for name in METHOD_SWITCHES}
    raise ValueError(f"unknown arm {arm!r}: expected {ARM_TODAY!r} or {ARM_METHOD!r}")


# --------------------------------------------------------------------------- #
# The measurements — pure, so the right answer can be reasoned, not observed   #
# --------------------------------------------------------------------------- #
def _date(value) -> Optional[dt.date]:
    if value is None or isinstance(value, dt.date):
        return value
    return dt.date.fromisoformat(str(value)[:10])


def his_last_lps_day(setup: dict) -> Optional[dt.date]:
    """The end of his LAST run of receding days — the day before his buy."""
    spans = [setup.get("lps"), setup.get("lps2")]
    ends = [_date(s[1]) for s in spans if s]
    return max(ends) if ends else None


def _trigger_matches(setup: dict, read: dict) -> bool:
    """The engine found HIS buy: the same last receding day, priced off it.

    Measured across all 35 of his drawings, without exception: his BUY day is
    the very next trading day after his last receding day, and his trigger
    price is exactly the HIGH of that last receding day. So his ``trigger``
    field is the day he would buy, while the engine's is the day its own run
    of receding days ended — they are one session apart by construction and
    must never be compared to each other.

    What makes a match, then, is that the engine ended its run on the day he
    ended his, and priced the buy off the same bar.
    """
    his_price = setup.get("trigger_price")
    if setup.get("trigger") is None or his_price is None:
        return False        # he marked no buy; nothing can match it
    if read.get("lps_end") != his_last_lps_day(setup):
        return False
    got = read.get("trigger_price")
    return got is not None and abs(float(got) - float(his_price)) < 0.005


def strict_hit(setup: dict, reads: list) -> bool:
    """Fired, on his last receding day, at his trigger. All three."""
    day = his_last_lps_day(setup)
    for read in reads:
        if read.get("day") == day:
            return bool(read.get("fired")) and _trigger_matches(setup, read)
    return False            # never read on his day at all


def chance_hit(setup: dict, reads: list, highs: dict,
               shift: int = DEFAULT_SHIFT_SESSIONS) -> bool:
    """The same read, with HIS day shifted — a near miss, never the headline.

    Shifting his day is not the same as reading on a different day. If his
    last receding day had been a session earlier or later, his trigger would
    have been THAT day's high — his own law, measured on all 35. So the
    shifted question is asked with a shifted trigger too: on day X near his,
    did the engine end its own run on X and price the buy at X's high?

    Keeping his real trigger while sliding only the reading day asks nothing
    new — it answers exactly what the headline already answered, which is how
    the first version of this column came to agree with it on all 70 reads.
    """
    day = his_last_lps_day(setup)
    if day is None or setup.get("trigger") is None:
        return False
    for read in reads:
        got = read.get("day")
        if got is None or abs((got - day).days) > shift:
            continue
        if not read.get("fired") or read.get("lps_end") != got:
            continue
        high = highs.get(got)
        price = read.get("trigger_price")
        if high is not None and price is not None and abs(float(price) - float(high)) < 0.005:
            return True
    return False


def rails_close(his_r: float, his_s: float, got_r, got_s, atr: float) -> bool:
    """Both of the engine's lines inside half a daily range of his."""
    if not atr or atr <= 0:
        raise ValueError("rails_close needs the drawn box's own daily range")
    if got_r is None or got_s is None:
        return False
    tolerance = RAIL_TOLERANCE_RANGES * float(atr)
    return (abs(float(got_r) - float(his_r)) <= tolerance
            and abs(float(got_s) - float(his_s)) <= tolerance)


def open_day_delta(his_open, got_open, sessions: list) -> Optional[int]:
    """Trading days between his opening day and the engine's, signed.

    Positive means the engine opened LATE (it started the box after he did),
    negative means early. The sign is kept because they are different faults:
    late is a box that missed its own beginning, early is one that swallowed
    the trend before it.
    """
    if got_open is None or his_open is None:
        return None
    try:
        return sessions.index(got_open) - sessions.index(his_open)
    except ValueError:
        return None         # a day outside the frame answers nothing


def opening_moved_on_reread(reads: list) -> bool:
    """The day the box opened moved while the chart was re-read.

    NOT his "openings running with the price", which is his anchor-polarity
    rule — an anchor may not start in the direction price is going — and is a
    test on the elected result that stage 10 must answer 0 of 35. These are two
    different measurements and they may not share a name.

    His rule is that a shown line never moves; the day it opened is a fact
    about the past and cannot move either. When it does, the engine is
    re-anchoring the opening to whatever price has just done — which is the
    defect that makes a box look right on the day and wrong a week later.
    Reads that found no box say nothing either way.
    """
    opens = {r.get("box_start") for r in reads if r.get("box_start") is not None}
    return len(opens) > 1


def first_difference(setup: dict, read: Optional[dict], atr: float) -> Optional[str]:
    """The FIRST stage where the engine's read leaves his drawing.

    In his order — the lines, the day the box opened, whether it fired at all,
    then the buy. A later difference is downstream of an earlier one and tells
    him nothing he can act on, so only the first is reported.

    "No frame" is its own answer and must never be folded into "lines". On four
    of his 35 the universe door refuses his own last receding day, so the
    engine never sees a chart at all; calling that "it drew the wrong lines"
    puts four charts in the board's largest bucket accused of something they
    were never given the chance to do.
    """
    if read is None:
        return "no read"
    if read.get("error"):
        return "no frame" if read["error"] == "no frame" else "the read crashed"
    rails = setup["rails_drawn"]
    if not rails_close(rails["R"], rails["S"], read.get("R"), read.get("S"), atr):
        return "lines"
    his_open = _date((setup.get("box") or [None])[0])
    if his_open is not None and read.get("box_start") != his_open:
        return "opening day"
    if not read.get("fired"):
        return "no fire"
    if not _trigger_matches(setup, read):
        return "trigger"
    return None


def rank_junk(fires: list) -> list:
    """The junk that fired, worst first — he reads the worst one first."""
    return sorted(fires, key=lambda f: (-float(f.get("score") or 0), str(f.get("key"))))


def slowest(seconds_by_chart: dict, n: int = 5) -> list:
    """The n slowest reads, each still carrying the name of its chart."""
    ranked = sorted(seconds_by_chart.items(), key=lambda kv: (-kv[1], kv[0]))
    return [(k, v) for k, v in ranked[:n]]


def misses_first(rows: list) -> list:
    """What it got wrong, then what it got right; stable within each half."""
    return [r for r in rows if not r.get("strict")] + \
           [r for r in rows if r.get("strict")]


# --------------------------------------------------------------------------- #
# Reading the charts                                                          #
# --------------------------------------------------------------------------- #
def _read_one_day(ticker: str, raw, day) -> dict:
    """One engine read of one chart, as of one day.

    Always reports the engine's OWN lines, whether or not it fired — a refusal
    with the right lines and a refusal with the wrong ones are different
    answers, and the board has to tell them apart.
    """
    started = time.perf_counter()
    out = {"day": day, "fired": False, "R": None, "S": None, "box_start": None,
           "lps_end": None, "trigger_price": None, "error": None}
    prepared = prepared_frame(raw, day)
    if prepared is None:
        out["seconds"] = time.perf_counter() - started
        out["error"] = "no frame"
        return out
    df, atr = prepared
    try:
        result = reader.evaluate_ticker(ticker, df, FROZEN_SPY_6M, None)
    except Exception as exc:                      # a crashed read is a fact
        out["seconds"] = time.perf_counter() - started
        out["error"] = f"{type(exc).__name__}: {exc}"
        return out
    if isinstance(result, dict):
        out.update(fired=True,
                   R=float(result["_R"]), S=float(result["_S"]),
                   box_start=_date(result.get("_phase_b_start_date")),
                   lps_end=_date(result.get("_lps_zone_end_date")),
                   trigger_price=float(result["_trigger_price"]))
    else:
        # It refused. Ask for the lines alone so "wrong lines" and "right
        # lines, no buy" stay separable.
        try:
            read = projection(reader.read_box(df, atr), df)
        except Exception as exc:
            out["error"] = f"{type(exc).__name__}: {exc}"
            read = None
        if read:
            out.update(R=read["R"], S=read["S"],
                       box_start=_date(read["box_start_date"]))
    out["seconds"] = time.perf_counter() - started
    return out


def _window(setup: dict, sessions: list, shift: int) -> list:
    """His last receding day, and the days either side the chance column uses."""
    day = his_last_lps_day(setup)
    if day is None or day not in sessions:
        return [d for d in sessions[-1:]]
    centre = sessions.index(day)
    lo, hi = max(0, centre - shift), min(len(sessions), centre + shift + 1)
    return sessions[lo:hi]


def score_setup(setup: dict, raw, shift: int = DEFAULT_SHIFT_SESSIONS) -> dict:
    """One drawn setup, read day by day, scored against what he drew."""
    key = setup_key(setup)
    sessions = [d.date() for d in raw.index]
    reads = [_read_one_day(setup["ticker"], raw, day)
             for day in _window(setup, sessions, shift)]
    box = setup.get("box") or [None, None]
    _, atr = drawn_box_window(raw, box[0], box[1])
    highs = {d.date(): float(h) for d, h in raw["High"].items()}
    on_his_day = next((r for r in reads if r["day"] == his_last_lps_day(setup)), None)
    rails = setup["rails_drawn"]
    return {
        "key": key,
        "ticker": setup["ticker"],
        "strict": strict_hit(setup, reads),
        "chance": chance_hit(setup, reads, highs, shift),
        "lines_close": bool(on_his_day and rails_close(
            rails["R"], rails["S"], on_his_day["R"], on_his_day["S"], atr)),
        "open_delta": open_day_delta(
            _date(box[0]), on_his_day["box_start"] if on_his_day else None, sessions),
        "opening_moved": opening_moved_on_reread(reads),
        "first_difference": first_difference(setup, on_his_day, atr),
        "seconds": sum(r["seconds"] for r in reads),
        "errors": [r["error"] for r in reads if r["error"]],
        "reads": reads,
        "atr": float(atr),
    }


def run_arm(arm: str, setups: list, frames: dict,
            shift: int = DEFAULT_SHIFT_SESSIONS) -> dict:
    """Every drawn setup, read under one arm's switches."""
    rows, clock = [], {}
    started = time.perf_counter()
    with flag_capture(**arm_overrides(arm)):
        for setup in setups:
            raw = fixture_frame(frames, setup_key(setup), setup["ticker"])
            row = score_setup(setup, raw, shift)
            rows.append(row)
            clock[row["key"]] = row["seconds"]
    return {
        "arm": arm,
        "rows": rows,
        "strict": sum(1 for r in rows if r["strict"]),
        "chance": sum(1 for r in rows if r["chance"]),
        "lines_close": sum(1 for r in rows if r["lines_close"]),
        "opened_on_his_day": sum(1 for r in rows if r["open_delta"] == 0),
        "opening_moved": sum(1 for r in rows if r["opening_moved"]),
        "total": len(rows),
        "wall_clock": time.perf_counter() - started,
        "slowest": slowest(clock),
    }


def junk_case_count() -> int:
    """How many labelled junk charts there are — from the fixture, never a
    literal. A lost frame would otherwise understate the numerator against a
    denominator that never moved."""
    from tools import negative_corpus

    _, meta = negative_corpus._load_fixture()
    return len(meta["cases"])


def junk_fires(arm: str) -> list:
    """The labelled junk that fired under this arm, worst first."""
    from tools import negative_corpus

    fires = []
    frames, meta = negative_corpus._load_fixture()
    with flag_capture(**arm_overrides(arm)):
        for case in meta["cases"]:
            key = case.get("key", case["ticker"])
            df = frames.get(key)
            if df is None or df.empty:
                fires.append({"key": key, "label": case["label"],
                              "day": None, "score": None, "tier": "FRAME MISSING"})
                continue
            walk = negative_corpus._case_walk(case, df, meta, False)
            for fire in walk.get("fires", []):
                result = fire.get("result") or {}
                fires.append({"key": key, "label": case["label"],
                              "day": fire.get("day"),
                              "score": result.get("Score"),
                              "tier": result.get("Tier")})
    return rank_junk(fires)


# --------------------------------------------------------------------------- #
# The board                                                                   #
# --------------------------------------------------------------------------- #
def _pct(hit: int, total: int) -> str:
    return f"{hit:>2} of {total}" if total else "  -   "


def format_board(arms: list, junk: dict, junk_total: int) -> str:
    """The board he reads: the strict headline first, everything else beside it."""
    out = ["", "THE YARDSTICK — his 35 drawings, both engines, "
           + dt.date.today().strftime("%A %d/%m/%Y"), ""]
    head = (f"{'':<34}" + "".join(f"{a['arm']:>14}" for a in arms))
    out += [head, "-" * len(head)]
    lines = [
        ("HIS DAY, HIS TRIGGER (the headline)",
         lambda a: _pct(a["strict"], a["total"])),
        ("  …with his day shifted (chance)",
         lambda a: _pct(a["chance"], a["total"])),
        ("his two lines, within half a range",
         lambda a: _pct(a["lines_close"], a["total"])),
        ("opened on his day",
         lambda a: _pct(a["opened_on_his_day"], a["total"])),
        ("openings that MOVED on re-reading",
         lambda a: _pct(a["opening_moved"], a["total"])),
        ("junk charts that fired",
         lambda a: _pct(len({f['key'] for f in junk[a['arm']]}), junk_total)),
        # The headline asks whether it fires at his buy using ITS OWN lines —
        # it does not ask that those lines are his. This row does, and it is
        # the one number that cannot be flattered.
        ("READ AS HE DREW IT (nothing differs)",
         lambda a: _pct(sum(1 for r in a["rows"]
                            if r["first_difference"] is None), a["total"])),
    ]
    for label, value in lines:
        out.append(f"{label:<34}" + "".join(f"{value(a):>14}" for a in arms))

    out += ["", "WHERE IT FIRST LEAVES HIS DRAWING"]
    for arm in arms:
        counts: dict = {}
        for row in arm["rows"]:
            counts[row["first_difference"] or "nowhere"] = \
                counts.get(row["first_difference"] or "nowhere", 0) + 1
        ordered = sorted(counts.items(), key=lambda kv: -kv[1])
        out.append(f"  {arm['arm']:<12}" +
                   "   ".join(f"{name} {n}" for name, n in ordered))

    out += ["", "THE CLOCK"]
    for arm in arms:
        slow = "  ".join(f"{k} {v:.2f}s" for k, v in arm["slowest"])
        out.append(f"  {arm['arm']:<12}{arm['wall_clock']:6.1f}s total    "
                   f"slowest: {slow}")

    for arm in arms:
        rows = junk[arm["arm"]]
        if not rows:
            continue
        out += ["", f"THE JUNK THAT FIRED — {arm['arm']}, worst chart first"]
        seen = set()
        for fire in rows:                       # already worst-first
            if fire["key"] in seen:
                continue                        # one line per CHART, not per day
            seen.add(fire["key"])
            days = sum(1 for f in rows if f["key"] == fire["key"])
            out.append(f"  {fire['key']:<18} {fire['label']:<34} "
                       f"worst {fire['day']} score {fire['score']} {fire['tier']}"
                       f"   ({days} day(s))")
    out.append("")
    return "\n".join(out)


# --------------------------------------------------------------------------- #
# The pages                                                                   #
# --------------------------------------------------------------------------- #
_HIS = "#d62728"        # his lines, red
_ENGINE = "#1f77b4"     # the engine's lines, blue


def render_pages(arm: dict, setups: dict, frames: dict, out_dir: str) -> list:
    """One page per chart, misses first, in his grammar: OHLC bars, his lines
    red, the engine's blue, and the words under them."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    from tools.full_package_render import _draw_bars

    refuse_sealed_output(out_dir)
    os.makedirs(out_dir, exist_ok=True)
    written = []
    for order, row in enumerate(misses_first(arm["rows"]), start=1):
        path = os.path.join(out_dir, f"{order:02d}_{row['key'].replace(':', '_')}.png")
        _render_one(plt, _draw_bars, row, setups[row["key"]],
                    fixture_frame(frames, row["key"], setups[row["key"]]["ticker"]),
                    arm["arm"], path)
        written.append(path)
    return written


#: Trading days of run-up shown before his box opens. Enough to see the trend
#: that ended, which is where his reading starts, without burying the box.
_LEAD_IN_SESSIONS = 45


def _window_bars(raw, setup: dict, row: dict):
    """The slice of the frame his setup actually lives in.

    The frozen frames carry five years. Drawn whole, his box is a sliver at
    the right edge and the page answers nothing — the first render did exactly
    that. The page shows the run-up into his box, his box, and everything
    after it to the day he drew.
    """
    sessions = [d.date() for d in raw.index]
    box = setup.get("box") or [None, None]
    starts = [_date(box[0])] + [r.get("box_start") for r in row["reads"]]
    first = min((s for s in starts if s is not None), default=sessions[0])
    lo = max(0, sessions.index(first) - _LEAD_IN_SESSIONS) if first in sessions else 0
    return raw.iloc[lo:], sessions[lo:]


def _swing_line(raw, offset: int, as_of) -> tuple:
    """The fine line of turns as of his day, as (x, price), plus any failure.

    Three corrections a blind check made to the first version of this, all of
    them the same mistake — drawing something other than what the engine had:

    * it read the WHOLE five-year frame, so turns near his day were confirmed
      by bars that came after it. The frame is now cut at ``as_of``, exactly
      as the reads are, so the line stops where his decision was made and the
      bars after it stand bare.
    * it ran outside the arm's switches, so the method arm's pages were drawn
      with today's skeleton. The caller now holds the arm open around it.
    * it swallowed every failure into an empty list, so "the reader crashed on
      all 35" and "no turns here" drew the same blank page. The reason comes
      back now and reaches the caption.
    """
    from engine_alpha.structure.market_structure import read_market_structure

    try:
        cut = raw.loc[:pd.Timestamp(as_of)] if as_of is not None else raw
        points = read_market_structure(cut).get("points", [])
    except Exception as exc:
        return [], f"{type(exc).__name__}: {exc}"
    return ([(int(p["bar"]) - offset, float(p["price"])) for p in points
             if int(p["bar"]) >= offset], None)


def _render_one(plt, draw_bars, row: dict, setup: dict, raw, arm: str, path: str):
    """One chart, in his grammar: bars, his lines red, the engine's blue."""
    view, sessions = _window_bars(raw, setup, row)
    fig, ax = plt.subplots(figsize=(16, 8))
    draw_bars(ax, view["Open"].values, view["High"].values,
              view["Low"].values, view["Close"].values)
    x = {d: i for i, d in enumerate(sessions)}

    rails, band = setup["rails_drawn"], RAIL_TOLERANCE_RANGES * row["atr"]
    for price in (rails["R"], rails["S"]):
        ax.axhspan(price - band, price + band, color=_HIS, alpha=.08, zorder=0)

    # The fine line of turns as of his day, and every turn sitting in one of
    # his rail areas. These are NOT "answering turns": his answering test has
    # a direction and a box window, and this has neither — it circles a swing
    # high resting at support as readily as a spring that recovered. It shows
    # where the turns fell against his lines, which is worth seeing under its
    # own name.
    last = his_last_lps_day(setup)
    turns, turn_error = _swing_line(raw, len(raw) - len(view), last)
    if turns:
        ax.plot([t[0] for t in turns], [t[1] for t in turns],
                color="#7a7a7a", lw=.9, alpha=.75, zorder=2)
        in_area = [t for t in turns
                   if min(abs(t[1] - rails["R"]), abs(t[1] - rails["S"])) <= band]
        if in_area:
            ax.plot([t[0] for t in in_area], [t[1] for t in in_area],
                    linestyle="none", marker="o", ms=9, mfc="none",
                    mec="#7a4b9c", mew=1.5, zorder=6)
    for price, name in ((rails["R"], "his R"), (rails["S"], "his S")):
        ax.axhline(price, color=_HIS, lw=1.7, zorder=4)
        ax.annotate(f"{name} {price:.2f}", (0.004, price),
                    xycoords=("axes fraction", "data"), color=_HIS,
                    fontsize=9, va="bottom", zorder=5)

    # His box: the span he drew, and the two days his lines answered on.
    box = setup.get("box") or [None, None]
    his_open, his_end = _date(box[0]), _date(box[1])
    if his_open in x and his_end in x:
        ax.axvspan(x[his_open], x[his_end], color=_HIS, alpha=.05, zorder=0)
        ax.axvline(x[his_open], color=_HIS, lw=1.2, ls=":", zorder=3)
    for rail, price in (("R", rails["R"]), ("S", rails["S"])):
        anchor = _date((setup.get("anchors") or {}).get(rail))
        if anchor in x:
            ax.plot([x[anchor]], [price], marker="o", ms=13, mfc="none",
                    mec=_HIS, mew=1.8, zorder=6)

    # His last run of receding days, and the buy it prices.
    lps = setup.get("lps2") or setup.get("lps")
    if lps and _date(lps[0]) in x and _date(lps[1]) in x:
        ax.axvspan(x[_date(lps[0])], x[_date(lps[1])], color="#8a6d3b",
                   alpha=.13, zorder=1)
    if _date(setup.get("trigger")) in x and setup.get("trigger_price"):
        ax.plot([x[_date(setup["trigger"])]], [setup["trigger_price"]],
                marker="^", ms=11, color=_HIS, zorder=6)

    read = next((r for r in row["reads"] if r["day"] == last), None)
    if read and read["R"] is not None:
        for price, name in ((read["R"], "engine R"), (read["S"], "engine S")):
            ax.axhline(price, color=_ENGINE, lw=1.5, ls="--", zorder=4)
            ax.annotate(f"{name} {price:.2f}", (0.80, price),
                        xycoords=("axes fraction", "data"), color=_ENGINE,
                        fontsize=9, va="bottom", zorder=5)
        if read["box_start"] in x:
            ax.axvline(x[read["box_start"]], color=_ENGINE, lw=1.3, ls=":", zorder=3)
            ax.annotate("engine opens here", (x[read["box_start"]], 0.985),
                        xycoords=("data", "axes fraction"), color=_ENGINE,
                        fontsize=8, ha="left", va="top")

    step = max(1, len(sessions) // 12)
    ax.set_xticks(range(0, len(sessions), step))
    ax.set_xticklabels([sessions[i].strftime("%d/%m/%y")
                        for i in range(0, len(sessions), step)], fontsize=8)
    ax.set_xlim(-2, len(sessions) + 1)

    verdict = ("HIS DAY, HIS TRIGGER" if row["strict"]
               else "chance only" if row["chance"] else "MISS")
    ax.set_title(f"{row['key']}  —  {verdict}   ·   arm: {arm}", fontsize=13,
                 loc="left", fontweight="bold")
    ax.set_xlabel(_words(row, setup, read, turn_error), fontsize=9.5, labelpad=8)
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)


def _words(row: dict, setup: dict, read, turn_error=None) -> str:
    """The sentence under the picture: what differs, in his words, first."""
    rails = setup["rails_drawn"]
    if read is None or read.get("R") is None:
        lines = "the engine drew no lines here"
    else:
        lines = (f"engine {read['R']:.2f}/{read['S']:.2f} against his "
                 f"{rails['R']:.2f}/{rails['S']:.2f}")
    if row["open_delta"] is None:
        opened = "it never opened a box on his day"
    elif row["open_delta"] == 0:
        opened = "it opened on his day"
    else:
        late = "late" if row["open_delta"] > 0 else "early"
        opened = f"it opened {abs(row['open_delta'])} trading days {late}"
    ran = " · its opening MOVED when the chart was re-read" if row["opening_moved"] else ""
    first = row["first_difference"] or "nothing"
    hurt = f"   THE TURN READER FAILED: {turn_error}." if turn_error else ""
    refused = ("   The universe door refused his day, so the engine never saw "
               "a chart." if "no frame" in (row.get("errors") or []) else "")
    return (f"First difference: {first}.   {lines} — half a daily range is "
            f"{RAIL_TOLERANCE_RANGES * row['atr']:.2f}.   {opened}.{ran}{refused}{hurt}")


def write_contact_sheet(arm: dict, pages: list, out_dir: str) -> str:
    """One page listing every chart, misses first, each picture under its verdict."""
    rows = misses_first(arm["rows"])
    cells = []
    for row, page in zip(rows, pages):
        verdict = "hit" if row["strict"] else ("chance" if row["chance"] else "miss")
        cells.append(
            f'<figure class="{verdict}"><img src="{os.path.basename(page)}" loading="lazy">'
            f'<figcaption><b>{row["key"]}</b> — {verdict}<br>'
            f'first difference: {row["first_difference"] or "none"}</figcaption></figure>')
    html = f"""<!doctype html><meta charset="utf-8">
<title>The yardstick — {arm['arm']}</title>
<style>
 body{{font:14px/1.5 system-ui,sans-serif;margin:24px;background:#faf9f7;color:#222}}
 h1{{font-size:20px}} .n{{color:#666}}
 .grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(520px,1fr));gap:18px}}
 figure{{margin:0;padding:8px;border:2px solid #ddd;border-radius:6px;background:#fff}}
 figure.miss{{border-color:#d62728}} figure.chance{{border-color:#e8a33d}}
 figure.hit{{border-color:#2e8b57}}
 img{{width:100%;height:auto}} figcaption{{padding-top:6px;font-size:13px}}
</style>
<h1>The yardstick — {arm['arm']}</h1>
<p class="n">His day, his trigger: <b>{arm['strict']} of {arm['total']}</b> ·
 with his day shifted: {arm['chance']} · his lines within half a daily range:
 {arm['lines_close']} · opened on his day: {arm['opened_on_his_day']}.
 Misses first.</p>
<div class="grid">{''.join(cells)}</div>
"""
    path = os.path.join(out_dir, "index.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return path


# --------------------------------------------------------------------------- #
# The run                                                                     #
# --------------------------------------------------------------------------- #
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--arm", choices=[ARM_TODAY, ARM_METHOD], action="append",
                    help="run one arm only (default: both)")
    ap.add_argument("--pages", metavar="DIR",
                    help="also write one page per chart and a contact sheet here")
    ap.add_argument("--json", metavar="PATH", help="also dump the board as JSON")
    ap.add_argument("--shift", type=int, default=DEFAULT_SHIFT_SESSIONS,
                    help="trading days the chance column may shift his day")
    args = ap.parse_args()

    arms_wanted = args.arm or [ARM_TODAY, ARM_METHOD]
    setups = load_corpus()
    frames, _ = load_sealed_fixture()
    by_key = {setup_key(s): s for s in setups}

    arms, junk = [], {}
    for name in arms_wanted:
        arms.append(run_arm(name, setups, frames, args.shift))
        junk[name] = junk_fires(name)
    print(format_board(arms, junk, junk_case_count()))

    if args.pages:
        for arm in arms:
            out_dir = os.path.join(args.pages, arm["arm"])
            # Under the arm's own switches: the page's turn line is read by the
            # engine, and drawing the method arm's pages with today's skeleton
            # puts a different reader's line beside the method's box.
            with flag_capture(**arm_overrides(arm["arm"])):
                pages = render_pages(arm, by_key, frames, out_dir)
            sheet = write_contact_sheet(arm, pages, out_dir)
            print(f"  {arm['arm']}: {len(pages)} pages · contact sheet {sheet}")
    if args.json:
        # Every sibling instrument guards its --json, and the reason is this
        # exact typo: `--json docs/marks/guided_list_2026-07.json` would
        # truncate his drawings in place, and a green run would say nothing.
        refuse_sealed_output(args.json)
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump({"arms": [{k: v for k, v in a.items() if k != "rows"}
                                | {"rows": [{k: v for k, v in r.items()
                                             if k != "reads"} for r in a["rows"]]}
                                for a in arms]}, f, indent=2, default=str)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
