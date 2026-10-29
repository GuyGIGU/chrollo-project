"""The approval pack (task 15 of the two-eyes-reader build): the last yardstick run, made into ONE page he approves
from, summary first.

The plan's Done-when: *"the APPROVAL PACK is the last yardstick run: your 35 (misses first, sorted by the first step
that differs), the junk sheet (ABEV, ENIC, DGII, DBD for you to rule; SPCB, the June BBVA, KWR and COLM for your
eye), the grade sheet, and a real scan night replayed by BOTH readers on a COPIED panel, outside the scan slot, into
side files only, with fires, the tally of state words and the wall clock; you approve, or point at the charts that
are wrong"*. His 35 are 40 since Fri 02/10/2026.

One run makes the numbers and the pictures, so a page can never disagree with the count beside it:

* the yardstick's three arms on his drawings (today's engine, the twelve-step method, the new reader), the junk
  under each, and per drawing the FIRST step where the new reader leaves his drawing;
* the core board's OHLC pages: his drawings read on his last receding day, each junk chart on its window;
* the grade sheet: his drawings and the junk fires ranked together by the grade (`grade_probe`), and the reader's
  own letters tallied;
* the night replayed by both readers, read from ``OUT/night/night.json`` (`parallel_night`, run on its own: it reads
  the whole universe twice and must run outside the scan slot);
* three charts he never drew that fire only by the small box's "near" (`MINI_RESCUES`), read on their fire days from
  the night's copied panel, so the night runs first.

The run's numbers go to ``OUT/pack.json``; ``OUT/index.html`` is written from that record and the night's side file,
so the page is rewritten without reading a chart again (``--index-only``). Offline, read-only, sidecars only (EC-46).

    python -m tools.calibration.parallel_night OUT/night          # the night first, outside the scan slot
    python -m tools.calibration.approval_pack OUT
    python -m tools.calibration.approval_pack OUT --index-only    # the page again, after another night
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
import pathlib
import re
import subprocess
import sys
import time
from collections import Counter

try:
    from tools._bootstrap import configure_path, refuse_sealed_output
except ImportError:  # invoked as a script from the repo root
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from tools._bootstrap import configure_path, refuse_sealed_output  # type: ignore
_ROOT = configure_path(backend=True)

#: His four to rule, and his four to look at (the plan's words), in the plan's order.
JUNK_TO_RULE = ("ABEV", "ENIC", "DGII", "DBD")
JUNK_FOR_EYE = ("SPCB", "BBVA@2026-06-05", "KWR", "COLM")
#: The first step where a read leaves his drawing, in his order (the yardstick's `first_difference`); a drawing the
#: new reader matches comes after every miss.
STEP_ORDER = ("no read", "no frame", "the read crashed", "lines", "opening day", "no fire", "trigger")
STEP_WORDS = {
    "no read": "no read at all",
    "no frame": "the universe door refuses your day: not scanned",
    "the read crashed": "the read fell over",
    "lines": "other lines than yours",
    "opening day": "your lines, another opening day",
    "no fire": "your box, no fire on your day",
    "trigger": "a fire on your day at another trigger",
}
LETTERS = ("S", "A", "B", "C")
ARM_WORDS = {"today": "today's engine", "method": "the twelve-step method", "two-eyes": "the new reader"}
NIGHT_COMMAND = "python -m tools.calibration.parallel_night OUT/night"
#: Three charts he never drew that fire ONLY because the pullback rests near the small box's top where the big box
#: refuses it: his "near it / resting on it" (the mini, task 13), on no picture of his. The task-13 blind check named
#: them "for task 15's sheet before any go-live" (docs/decisions.md, 2026-10-03).
MINI_RESCUES = (("BWAY", "2026-08-13"), ("FRBA", "2026-07-30"), ("TEVA", "2026-09-25"))
#: The day the rewrite began: every builder's default of its record is on the page (EC-58).
REWRITE_BEGAN = "2026-09-20"
#: How a decisions row marks a default of the builder's, not a ruling of his.
#: In any case and any form the record uses ("OURS", "ours", "(mine)", "my defaults", "marked as ours",
#: "builder's default"): verify-6 of the fix run found three rows the upper-case form missed, a live rule among them.
OURS_MARK = re.compile(r"\bours\b|\bmine\b|\bmy defaults?\b|builder's defaults?", re.IGNORECASE)
#: What he approves that is not his own word, or that he ruled and the reader does not yet do: each with the
#: date of its decisions row, first on the page (council review 2026-10-09, findings 4 and 5; EC-58).
#: Each with its decisions date and, where one is committed, the picture he ruled on (a repo path).
OPEN_FOR_HIM = (
    ("2026-10-05", "The grade reads the PARENT box, whatever box the LPS was read against. That day's record "
                   "calls this your call, not ours, and the build took the parent: it is what makes SIMO an S "
                   "(SIMO's two letters are side by side below). It also moves VIK, VLO, WTS and SYRE.", None),
    ("2026-10-09", "Your FRPH ruling (a box that failed into its own lower level for two months is not tied to "
                   "the box any more; its late return is no test and no SOS) is NOT BUILT: the reader still "
                   "gives a box its place back on the first day the bars come back to both its lines, and the "
                   "boxes after it build on that box.", "docs/marks/rulings_2026-10-05/frph_dead_space.png"),
    ("2026-10-01", "A line the reader has shown never moves back to an earlier pair (ours, the core sitting): "
                   "it is what costs your ROIV box. Asked of you on the night of your ROIV picture.", None),
    ("2026-09-26", "A pair under one daily range tall is never a box (ours, placed at the listing gate). Your "
                   "word of Mon 05/10/2026: a box about as tall as its bars is completely fine. All 40 of yours "
                   "pass it today.", None),
    ("2026-09-08", "Your LPS trait, \"Lowering (and low) spread below average\": no stage reads it, no rule "
                   "grades it and nothing stores it. Keep it as a raw number on every fire, or drop it?", None),
    ("2026-10-03", "Your MTLS word, follow the counter swing to the support the bars rest on: ten readings "
                   "measured, none built, by your own bar.", None),
    ("2026-10-09", "The grade's straight line from 100 to 0 and its cuts (S from 75, A from 50, B from 25) are "
                   "the plan's, yours to approve.", None),
)
#: SIMO's letters on the two boxes, from the decisions row of Fri 09/10/2026 (the fifth reading measured): the
#: parent reading he is asked to approve, beside the box the LPS was read against.
SIMO_LETTERS = (("the parent box (as built)", "S on all six fire days"),
                ("the box the LPS was read against (the mini on two days)", "C on the two days read against the "
                                                                         "mini, S on the other four"))


def misses_first_by_step(rows: list) -> list:
    """His drawings, the misses first in the order of the first step that differs, then the ones that match."""
    def rank(row):
        step = row.get("first_difference")
        if step is None:
            return len(STEP_ORDER) + 1
        return STEP_ORDER.index(step) if step in STEP_ORDER else len(STEP_ORDER)
    return sorted(rows, key=lambda row: (rank(row), row["key"]))


# --------------------------------------------------------------------------- #
# The run                                                                      #
# --------------------------------------------------------------------------- #
def _tally(letters) -> dict:
    counts = Counter(letter for letter in letters if letter)
    return {letter: counts[letter] for letter in LETTERS if counts[letter]}


def _page(path: str, out_dir: str) -> str:
    return os.path.relpath(path, out_dir).replace(os.sep, "/")


def rescue_rows(out_dir: str) -> list | None:
    """The three charts of `MINI_RESCUES`, each read on its day from the night's copied panel (``OUT/night/panel``,
    the scan's own frame preparation) and drawn as the board draws; None when the night has not been copied yet."""
    import pandas as pd
    from core.pipeline.screening.screener import _prepare_ticker_frames
    from core.pipeline.universe.descriptor import resolve_universe
    from tools.calibration import core_board

    uni = resolve_universe(None)
    panel = os.path.join(out_dir, "night", "panel", os.path.basename(uni.cache_paths()[0]))
    if not os.path.exists(panel):
        return None
    data = pd.read_parquet(panel)
    if getattr(data.index, "tz", None) is not None:
        data.index = data.index.tz_localize(None)
    frames = _prepare_ticker_frames([ticker for ticker, _day in MINI_RESCUES], data, uni)
    rows = []
    for ticker, day in MINI_RESCUES:
        row = core_board.read_day(ticker, frames[ticker], dt.date.fromisoformat(day)) if ticker in frames else None
        read = None if row is None else row["read"]
        lps = None if read is None else read.lps
        page = None
        if row is not None and row["prepared"] is not None:
            page = _page(core_board.render_read(row, os.path.join(out_dir, "pages", f"rescue_{ticker}.png"),
                                                f"{ticker}  —  read on {_day(day)}"), out_dir)
        rows.append({"key": ticker, "day": day, "fired": bool(row and row["fired"]),
                     "state": None if read is None else read.state,
                     "against": None if lps is None else lps.read_against, "how": None if lps is None else lps.how,
                     "trigger": None if lps is None else round(float(lps.trigger_price), 2),
                     "grade": None if read is None or read.grade is None else read.grade.letter,
                     "score": None if read is None or read.grade is None else round(read.grade.score, 1),
                     "page": page})
    return rows


def rests_on_the_way_back(found) -> bool:
    """The box shown DESCENDS from a way back: since the read's last new trend (a first box, or a box taken over
    from one anchored inside a live trend), some box took its place back after the price had left it downward
    (``walk.came_back_to``), the rule his FRPH ruling of Fri 09/10/2026 calls a mistake for a box that failed
    long ago. Read off the walk's own reasons (``Life.why``), never its words: FRPH's January box comes back once
    and the boxes it fires on take over from it upward (verify-6 of the fix run)."""
    from engine_alpha.two_eyes import walk

    for life in reversed(getattr(found, "lives", None) or ()):
        if life.why == walk.CAME_BACK:
            return True
        if life.why in (walk.LIVE_TREND, walk.FIRST_BOX, walk.WRAPS):
            return False                        # a fresh box: nothing before it is a place to come back to
    return False


def ours_rows(path: str | None = None) -> list:
    """Every decisions row since the rewrite began that records a default of the builder's (OURS, MINE, a
    builder's default), as ``(date, title)``: the page lists them all, so \"approved\" never signs a rule he
    never saw stated (EC-58)."""
    path = path or os.path.join(_ROOT, "docs", "decisions.md")
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            row = re.match(r"\| (\d{4}-\d\d-\d\d) \| (.*)", line)
            if not row or row.group(1) < REWRITE_BEGAN or not OURS_MARK.search(line):
                continue
            title = re.search(r"\*\*(.+?)\*\*", row.group(2))
            out.append((row.group(1), title.group(1) if title else row.group(2)[:200]))
    return out


def _versions() -> dict:
    """The engine version each reader reads under, as the night replay stamps it (``parallel_night._version``)."""
    from tools.calibration.parallel_night import _version

    return {"old": _version(False), "new": _version(True)}


def _head() -> str | None:
    """The commit the pack is built at, "+dirty" when a tracked file has changed since it."""
    try:
        head = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=_ROOT, capture_output=True, text=True,
                              check=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"], cwd=_ROOT,
                               capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None
    return f"{head}+dirty" if dirty else head


def build(out_dir: str) -> dict:
    """Read every chart once, draw the pages and the grade sheet, write ``pack.json`` and the index."""
    from config import settings
    from tools.calibration import core_board, grade_probe, yardstick
    from tools.regression.marks_corpus import load_sealed_standard

    refuse_sealed_output(out_dir)
    os.makedirs(out_dir, exist_ok=True)
    started = time.perf_counter()
    setups, frames, stamp = load_sealed_standard()     # the drawings and their bars, proved one set (EC-13)

    # The last yardstick run: three arms on his drawings and the junk under each, the board kept as it prints.
    arms = [yardstick.run_arm(arm, setups, frames) for arm in yardstick.ARMS]
    junk_by_arm = {arm: yardstick.junk_fires(arm) for arm in yardstick.ARMS}
    with open(os.path.join(out_dir, "yardstick.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write(yardstick.format_board(arms, junk_by_arm, yardstick.junk_case_count()) + "\n")
    new_arm = {row["key"]: row for row in next(a for a in arms if a["arm"] == yardstick.ARM_NEW)["rows"]}

    # The core board's pages: the reader's box, its LPS and its trigger, his lines in red.
    rows = core_board.run_board(setups, frames)
    junk = core_board.junk_rows()
    his_pages, junk_pages = core_board.render_pages(rows, junk, os.path.join(out_dir, "pages"))
    page_of = {row["key"]: _page(path, out_dir) for row, path in his_pages + junk_pages}
    rescues = rescue_rows(out_dir)

    # The grade sheet, ranked by the grade that passed its bar (the probe's fifth reading, read to the whole point,
    # is the reader's own).
    his_m, junk_m, silent = grade_probe.collect()
    _, charts, summary = grade_probe.board(his_m, junk_m, silent, grade_probe.SHUFFLES)
    third = grade_probe.graded_by(*(summary[n]["passes"] for n in ("fifth", "fourth", "third")))
    sheet = grade_probe.render_sheet(charts, os.path.join(out_dir, "grade"), "D", bool(summary["kept"]), third)

    def grade_of(read):
        return read.grade.letter if read.grade is not None else None

    record = {
        "made": dt.date.today().strftime("%a %d/%m/%Y"),
        "head": _head(),
        "ruleset": settings.TWO_EYES_RULESET,
        "marks": {"drawings": len(setups)},
        "yardstick": {"arms": [{key: arm[key] for key in ("arm", "strict", "chance", "lines_close",
                                                           "opened_on_his_day", "total")}
                               | {"wall_clock": round(arm["wall_clock"], 1)} for arm in arms]},
        "his": [{"key": row["key"],
                 "first_difference": new_arm.get(row["key"], {}).get("first_difference"),
                 "strict": bool(new_arm.get(row["key"], {}).get("strict")),
                 "box": row["box"], "why": row["why"], "page": page_of.get(row["key"]),
                 "grade": grade_of(row["on_last"]["read"]),
                 "score": (round(row["on_last"]["read"].grade.score, 1)
                           if row["on_last"]["read"].grade is not None else None)} for row in rows],
        "junk": [{"key": row["key"], "label": row["label"], "fires": [f["day"].isoformat() for f in row["fires"]],
                  "grades": [grade_of(f["read"]) for f in row["fires"]], "page": page_of.get(row["key"])}
                 for row in junk],
        "grade": {"his": _tally(grade_of(row["on_last"]["read"]) for row in rows),
                  "junk": _tally(grade_of(f["read"]) for row in junk for f in row["fires"]),
                  "sheet": _page(sheet, out_dir)},
        "rescues": rescues,
        "stamp": {**stamp, "readers": _versions()},
        "way_back": {"his": [row["key"] for row in rows
                            if row["on_last"]["fired"] and rests_on_the_way_back(row["on_last"].get("found"))],
                    "junk": [f"{row['key']} {f['day'].isoformat()}" for row in junk for f in row["fires"]
                             if rests_on_the_way_back(f.get("found"))]},
        "grade_nights": core_board.grade_moves(setups, frames),
        "seconds": round(time.perf_counter() - started, 1),
    }
    with open(os.path.join(out_dir, "pack.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(record, f, indent=1)
    write_index(out_dir)
    return record


# --------------------------------------------------------------------------- #
# The page                                                                     #
# --------------------------------------------------------------------------- #
def _e(value) -> str:
    return html.escape(str(value))


def _day(iso: str) -> str:
    return dt.date.fromisoformat(iso).strftime("%a %d/%m/%Y")


def _letters(tally: dict) -> str:
    return " · ".join(f"{letter} {tally[letter]}" for letter in LETTERS if tally.get(letter)) or "none"


def _figure(klass: str, page, caption: str) -> str:
    img = f'<img src="{_e(page)}" loading="lazy">' if page else '<div class="nopage">no picture</div>'
    return f'<figure class="{klass}">{img}<figcaption>{caption}</figcaption></figure>'


def _his_figure(row: dict) -> str:
    """Green: read as he drew it. Amber: it fires on his day at his trigger, and something before differs (the
    lines, the opening day). Red: no fire on his day at his trigger (the core sitting's sheets, the same colours)."""
    step = row.get("first_difference")
    fires = ("fires on your day at your trigger" if row.get("strict")
             else "no fire on your day at your trigger" + (f" ({_e(row['why'])})" if row.get("why") else ""))
    said = "read as you drew it" if step is None else STEP_WORDS.get(step, step)
    grade = f" · grade {row['grade']} {row['score']:.0f}" if row.get("grade") and row.get("score") is not None else ""
    klass = "hit" if step is None else "chance" if row.get("strict") else "miss"
    return _figure(klass, row.get("page"),
                   f"<b>{_e(row['key'])}</b> — {said} · {fires} · box {_e(row['box'])}{grade}")


def _junk_figure(row: dict) -> str:
    fires = row.get("fires") or []
    said = (f"fires on {len(fires)} day(s) of its window, graded {' '.join(g or '-' for g in row.get('grades') or [])}"
            if fires else "silent on every day of its window")
    return _figure("miss" if fires else "hit", row.get("page"), f"<b>{_e(row['key'])}</b> — {_e(row['label'])} · {said}")


def _rescue_figure(row: dict) -> str:
    """What the reader says on that day now, never the record's word: a chart that no longer fires says so."""
    if row.get("fired"):
        box = "the small box" if row.get("against") == "mini" else "the big box"
        said = f"fires on {_day(row['day'])} at {row['trigger']:.2f}, read against {box}" + (
            f" ({_e(row['how'])} it)" if row.get("how") else "")
    else:
        said = f"no fire on {_day(row['day'])} ({_e(row.get('state') or 'no read')})"
    grade = f" · grade {row['grade']} {row['score']:.0f}" if row.get("grade") and row.get("score") is not None else ""
    return _figure("fleet", row.get("page"), f"<b>{_e(row['key'])}</b> — {said}{grade}")


def _rescue_section(rescues) -> str:
    head = "<h2 id=\"rescues\">Three charts you never drew, fired by the small box's \"near\"</h2>"
    if rescues is None:
        return head + ("<p>Read from the night's copied panel: run the night first, then the pack "
                       f"(<code>{_e(NIGHT_COMMAND)}</code>).</p>")
    return head + ("<p>Each fires only because its pullback rests just over the small box's top, where the big box "
                   "alone refuses it (your \"near it / resting on it\"). No drawing of yours shows this rule at work: "
                   "these are the charts that do.</p>"
                   f"<div class=\"grid\">{''.join(_rescue_figure(row) for row in rescues)}</div>")


def _grade_rule() -> str:
    """The grade's rule and weights, stated where he approves them, from the reader's own numbers (verify-15d: the
    sheet showed every chart's grade, never the rule that makes it)."""
    from engine_alpha import two_eyes_numbers as M

    def share(x: float) -> str:
        return "half" if x == 0.5 else f"{x:g} of"

    return (f"<p><b>How the grade reads</b>: a day of the base is empty when its bar misses the box by more than"
            f" {share(M.LINE_WORD_AREA_ATR)} its daily range, outside every named event's own swing. 100 when no day"
            f" of the base is empty, 0 when {share(M.GRADE_EMPTY_ZERO)} the base is empty, a straight line between; 0"
            f" when the base did not hold (after the SOS's top, a low beyond the support's area and under the base's"
            f" own lowest low). Read to the whole point: S from {M.GRADE_S:g}, A from {M.GRADE_A:g}, B from"
            f" {M.GRADE_B:g}, C under. These numbers are yours to approve.</p>")


def _choices_section(record: dict) -> str:
    """First on the page: what he approves that is not his own word, and the rulings the reader does not yet do
    (council review 2026-10-09, findings 4 and 5; EC-58)."""
    way = record.get("way_back")
    if way is None:
        way_said = "not counted on this run (an older pack)."
    else:
        named = list(way.get("his") or []) + list(way.get("junk") or [])
        way_said = ("fires that rest on that way back here: " + _e(", ".join(named))) if named else \
            "no fire of this pack rests on that way back."
    items = []
    for day, words, picture in OPEN_FOR_HIM:
        extra = f" <i>{way_said}</i>" if "FRPH" in words else ""
        if "SIMO" in words:
            extra += ("<table class=\"simo\"><tr><th>SIMO, read on</th><th>its letter</th></tr>"
                      + "".join(f"<tr><td>{_e(box)}</td><td>{_e(letter)}</td></tr>" for box, letter in SIMO_LETTERS)
                      + "</table>")
        if picture and os.path.exists(os.path.join(_ROOT, picture)):
            uri = pathlib.Path(_ROOT, picture).resolve().as_uri()
            extra += f' <a href="{_e(uri)}">the picture you ruled on</a>'
        items.append(f"<li><b>{_day(day)}</b> — {_e(words)}{extra}</li>")
    rows = "".join(f"<li>{_day(day)} — {_e(title)}</li>" for day, title in ours_rows())
    return ("<h2 id=\"choices\">What you approve that is ours, not yours</h2>"
            f"<ul class=\"short\">{''.join(items)}</ul>"
            "<details><summary>Every default of ours on the record since the rewrite began "
            f"({len(ours_rows())} rows of docs/decisions.md)</summary><ul>{rows}</ul></details>")


def _grade_nights_paragraph(record: dict) -> str:
    """The letter night after night on his drawings (council review 2026-10-09, finding 6)."""
    moves = record.get("grade_nights")
    if moves is None:
        return "<p><b>The letter, night after night</b>: not measured on this run (an older pack).</p>"
    charts = " · ".join(f"{_e(key)} {_e(letters)}" for key, letters in sorted(moves["charts"].items()))
    return (f"<p><b>The letter, night after night</b>, on your drawings, the ten trading days up to your last "
            f"receding day and on to your day ({moves['nights']} nights): with the same box shown, the letter "
            f"moved {moves['moves']} times in {moves['pairs']} pairs of nights, {moves['moves_with_the_sos']} of "
            f"them when THE SOS's day moved; THE SOS was still provisional on {moves['provisional_sos_nights']} "
            f"nights. Charts whose letter moved: {charts or 'none'}. The grade reads THE SOS whether it is settled "
            f"or provisional; grading only on a settled SOS is yours to choose.</p>")


def night_mismatch(record: dict, night) -> str | None:
    """A night read by another engine than the pack's: the two halves of the page would come from two builds
    (council review 2026-10-09, finding 7). None when they agree or either side carries no stamp."""
    ours = (record.get("stamp") or {}).get("readers")
    if night is None or not ours:
        return None
    theirs = {side: night["readers"][side].get("engine_config_version") for side in ("old", "new")}
    differ = [side for side in ("old", "new") if theirs[side] and theirs[side] != ours.get(side)]
    if not differ:
        return None
    return ("THE NIGHT WAS READ BY ANOTHER ENGINE than this pack: " + "; ".join(
        f"{'today' if side == 'old' else 'the new reader'}'s night {str(theirs[side])[:12]}, the pack "
        f"{str(ours.get(side))[:12]}" for side in differ) + ". Run the night again, then this page.")


def _scan_paragraph(night) -> str:
    """The night he saw, beside the replay: the replay's old reader is this branch's engine, and the scan that
    night may have run another, with a cut after the read."""
    scan = night.get("scan")
    if scan is None:
        return "<p>The scan's own payload of this night was not copied: the replay is not set beside the night you saw.</p>"
    if not scan.get("same_night"):
        return f"<p>The scan's payload is of {_day(scan['scan_date'])}, not this night: not compared.</p>"
    removed = scan.get("removed_after_the_read") or []
    took = f"; its market-cap floor took out after the read: {_e(', '.join(removed))}" if removed else ""
    here = night["readers"]["old"].get("read")
    why = (f" This replay reads every chart of the copied panel its ledgers admit ({here}); the scan read the names of"
           f" its ticker list it admitted that night ({scan['read']}), a set it does not keep on disk."
           if here != scan.get("read") else "")
    return (f"<p><b>The scan you saw that night</b> (engine {_e(str(scan.get('engine_config_version') or '?')[:8])}):"
            f" {scan['fires']} fires shown of {scan['read']} tickers read{took}. Today's engine here is this branch's"
            f" (engine {_e(str(night['readers']['old'].get('engine_config_version') or '?')[:8])}):"
            f" only in this replay: {_e(', '.join(scan['replay_only']) or 'none')};"
            f" only in the scan: {_e(', '.join(scan['scan_only']) or 'none')}. The new reader's fires are counted"
            f" before any cut after the read.{why}</p>")


def _night_section(night) -> str:
    if night is None:
        return (f'<h2 id="night">One real scan night, both readers</h2><p>Not run yet. Outside the scan slot: '
                f"<code>{_e(NIGHT_COMMAND)}</code>, then this page again with <code>--index-only</code>.</p>")
    old, new = night["readers"]["old"], night["readers"]["new"]

    def fires(side):
        return ", ".join(f"{_e(f['ticker'])} {_e(f.get('tier') or '')}" for f in side["fires"]) or "none"

    def tiers(side):
        return " · ".join(f"{_e(tier)} {n}" for tier, n in (side.get("tiers") or {}).items()) or "none"

    def failures(side):
        if not side.get("failures"):
            return "none"
        reasons = " · ".join(f"{_e(rule)} {n}" for rule, n in (side.get("failure_reasons") or {}).items())
        return f"{reasons} ({_e(', '.join(ticker for ticker, _why in side['failures']))})"

    words = "".join(f"<tr><td>{_e(word)}</td><td>{count}</td></tr>" for word, count in new.get("states", {}).items())
    panel = night.get("panel") or {}
    return f"""<h2 id="night">One real scan night, both readers — {_day(night['night'])}</h2>
<p>A copy of the scan's own panel ({_e(panel.get('source', '?'))}, sha256 {_e(str(panel.get('sha256', ''))[:12])}),
 read outside the scan slot into side files only, every ticker by both readers through the one door.</p>
<table class="night"><tr><th></th><th>today's engine</th><th>the new reader</th></tr>
<tr><td>tickers read</td><td>{old['read']}</td><td>{new['read']}</td></tr>
<tr><td>fires</td><td>{len(old['fires'])}</td><td>{len(new['fires'])}</td></tr>
<tr><td>fires by tier</td><td>{tiers(old)}</td><td>{tiers(new)}</td></tr>
<tr><td>failed reads</td><td>{old['failed']}</td><td>{new['failed']}</td></tr>
<tr><td>why they failed</td><td>{failures(old)}</td><td>{failures(new)}</td></tr>
<tr><td>wall clock</td><td>{old['wall_clock_s']:.0f} s</td><td>{new['wall_clock_s']:.0f} s</td></tr></table>
{_scan_paragraph(night)}
<p>Both fire on {len(night['both'])}: {_e(', '.join(night['both']) or 'none')}. Today's engine alone on
 {len(night['old_only'])}; the new reader alone on {len(night['new_only'])}.</p>
<p>Today's engine fires: {fires(old)}.</p><p>The new reader fires: {fires(new)}.</p>
<h3>The new reader's words, every chart of the night</h3><table class="words">{words}</table>"""


def _stamp_words(record: dict) -> str:
    """Which drawings and which engines made the page (EC-13): blank-safe for an older pack."""
    stamp = record.get("stamp") or {}
    readers = stamp.get("readers") or {}
    if not stamp:
        return "no stamp of the drawings or the engines (an older pack)"
    return (f"drawings: corpus {_e(str(stamp.get('corpus_sha256'))[:12])}, marks fingerprint "
            f"{_e(str(stamp.get('marks_fingerprint'))[:12])} · engines: today's {_e(str(readers.get('old'))[:12])}, "
            f"the new reader's {_e(str(readers.get('new'))[:12])}")


def write_index(out_dir: str) -> str:
    """``OUT/index.html`` from ``OUT/pack.json`` and, when it exists, ``OUT/night/night.json``."""
    with open(os.path.join(out_dir, "pack.json"), encoding="utf-8") as f:
        record = json.load(f)
    night_path = os.path.join(out_dir, "night", "night.json")
    night = None
    if os.path.exists(night_path):
        with open(night_path, encoding="utf-8") as f:
            night = json.load(f)

    arms = {arm["arm"]: arm for arm in record["yardstick"]["arms"]}
    new = arms.get("two-eyes", {})
    others = ", ".join(f"{ARM_WORDS[name]} {arm['strict']}" for name, arm in arms.items() if name != "two-eyes")
    his = misses_first_by_step(record["his"])
    junk = {row["key"]: row for row in record["junk"]}
    firing = [row for row in record["junk"] if row.get("fires")]
    summary = [
        f"Your {record['marks']['drawings']} drawings: the new reader fires on your last receding day at your trigger"
        f" on <b>{new.get('strict', '?')} of {new.get('total', '?')}</b> ({others}).",
        f"The grade: your drawings {_letters(record['grade']['his'])}; the junk's fire days"
        f" {_letters(record['grade']['junk'])}.",
        f"The junk: {len(firing)} of {len(record['junk'])} fire on some day of their window; four are yours to rule,"
        " four for your eye.",
    ]
    if night is not None:
        scan = night.get("scan") or {}
        seen = (f" (the scan you saw that night showed {scan['fires']}; why they differ is below)"
                if scan.get("same_night") else "")
        summary.append(f"One real night, {_day(night['night'])}, both readers: today's engine"
                       f" {len(night['readers']['old']['fires'])} fires{seen}, the new reader"
                       f" {len(night['readers']['new']['fires'])}, both on {len(night['both'])}.")
    else:
        summary.append("One real night, both readers: not run yet.")
    warning = night_mismatch(record, night)
    if warning:
        summary.insert(0, f'<span class="warn">{_e(warning)}</span>')
    summary.append("You approve, or point at the charts that are wrong — and the choices of ours listed first.")

    def group(keys):
        return "".join(_junk_figure(junk[key]) for key in keys if key in junk)

    rest = [key for key in sorted(junk) if key not in JUNK_TO_RULE + JUNK_FOR_EYE]
    page = f"""<!doctype html><meta charset="utf-8">
<title>The approval pack</title>
<style>
 body{{font:14px/1.5 system-ui,sans-serif;margin:24px;background:#faf9f7;color:#222}}
 h1{{font-size:21px}} h2{{font-size:17px;margin-top:34px}} h3{{font-size:15px;margin-top:22px}}
 .meta{{color:#666}} ul.short li{{margin:4px 0}}
 .grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(520px,1fr));gap:18px}}
 figure{{margin:0;padding:8px;border:2px solid #ddd;border-radius:6px;background:#fff}}
 figure.miss{{border-color:#d62728}} figure.chance{{border-color:#e8a33d}} figure.hit{{border-color:#2e8b57}}
 figure.fleet{{border-color:#4a6fa5}} .warn{{color:#b00020;font-weight:600}}
 img{{width:100%;height:auto}} figcaption{{padding-top:6px;font-size:13px}} .nopage{{color:#999;padding:30px}}
 table{{border-collapse:collapse}} td,th{{border:1px solid #ddd;padding:4px 10px;text-align:left}}
</style>
<h1>The two-eyes reader — the approval pack</h1>
<p class="meta">Made {_e(record['made'])} from commit {_e(record.get('head') or '?')} · reader {_e(record['ruleset'])}
 · {_stamp_words(record)}
 · OHLC bars; red: your lines and your days; blue: the reader's box, thin blue its mini; green: its LPS and trigger.
 Frames: green, read as you drew it; amber, it fires on your day at your trigger and something before differs; red,
 no fire on your day at your trigger; blue, a chart you never drew.</p>
<h2>In short</h2>
<ul class="short">{''.join(f'<li>{line}</li>' for line in summary)}</ul>
{_choices_section(record)}
<h2>Your {record['marks']['drawings']} drawings — misses first, by the first step where the reader leaves yours</h2>
<div class="grid">{''.join(_his_figure(row) for row in his)}</div>
<h2>The junk</h2>
<h3 id="junk-rule">For you to rule</h3><div class="grid">{group(JUNK_TO_RULE)}</div>
<h3 id="junk-eye">For your eye</h3><div class="grid">{group(JUNK_FOR_EYE)}</div>
<h3 id="junk-rest">The rest of the junk</h3><div class="grid">{group(rest)}</div>
{_rescue_section(record.get('rescues'))}
<h2 id="grade">The grade sheet</h2>
<p>Your drawings: {_letters(record['grade']['his'])}. The junk's fire days: {_letters(record['grade']['junk'])}.
 <a href="{_e(record['grade']['sheet'])}">The sheet</a>: your drawings and the junk fires ranked together by the
 grade.</p>
{_grade_rule()}
{_grade_nights_paragraph(record)}
{_night_section(night)}
"""
    path = os.path.join(out_dir, "index.html")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(page)
    return path


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("out", help="the folder the pack goes to")
    ap.add_argument("--index-only", action="store_true", help="rewrite the page from pack.json and the night only")
    args = ap.parse_args(argv)
    refuse_sealed_output(args.out)
    if args.index_only:
        print(f"the pack: {write_index(args.out)}")
        return 0
    record = build(args.out)
    print(f"the pack: {os.path.join(args.out, 'index.html')} ({record['seconds']:.0f} s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
