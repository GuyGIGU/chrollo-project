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
  the whole universe twice and must run outside the scan slot).

The run's numbers go to ``OUT/pack.json``; ``OUT/index.html`` is written from that record and the night's side file,
so the page is rewritten without reading a chart again (``--index-only``). Offline, read-only, sidecars only (EC-46).

    python -m tools.calibration.approval_pack OUT
    python -m tools.calibration.parallel_night OUT/night          # the night, outside the scan slot
    python -m tools.calibration.approval_pack OUT --index-only    # the page again, with the night in it
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
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


def _head() -> str | None:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=_ROOT, capture_output=True, text=True,
                              check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def build(out_dir: str) -> dict:
    """Read every chart once, draw the pages and the grade sheet, write ``pack.json`` and the index."""
    from config import settings
    from core.calibration.replay import load_sealed_fixture
    from tools.calibration import core_board, grade_probe, yardstick
    from tools.regression.marks_corpus import load_corpus

    refuse_sealed_output(out_dir)
    os.makedirs(out_dir, exist_ok=True)
    started = time.perf_counter()
    setups = load_corpus()
    frames, _ = load_sealed_fixture()

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

    # The grade sheet, ranked by the grade that passed its bar (the probe's fifth reading is the reader's own).
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
    step = row.get("first_difference")
    verdict = ("fires on your day at your trigger" if step is None
               else STEP_WORDS.get(step, step) + (f" ({_e(row['why'])})" if row.get("why") else ""))
    grade = f" · grade {row['grade']} {row['score']:.0f}" if row.get("grade") and row.get("score") is not None else ""
    return _figure("hit" if step is None else "miss", row.get("page"),
                   f"<b>{_e(row['key'])}</b> — {verdict} · box {_e(row['box'])}{grade}")


def _junk_figure(row: dict) -> str:
    fires = row.get("fires") or []
    said = (f"fires on {len(fires)} day(s) of its window, graded {' '.join(g or '-' for g in row.get('grades') or [])}"
            if fires else "silent on every day of its window")
    return _figure("miss" if fires else "hit", row.get("page"), f"<b>{_e(row['key'])}</b> — {_e(row['label'])} · {said}")


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
<p>Both fire on {len(night['both'])}: {_e(', '.join(night['both']) or 'none')}. Today's engine alone on
 {len(night['old_only'])}; the new reader alone on {len(night['new_only'])}.</p>
<p>Today's engine fires: {fires(old)}.</p><p>The new reader fires: {fires(new)}.</p>
<h3>The new reader's words, every chart of the night</h3><table class="words">{words}</table>"""


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
        summary.append(f"One real night, {_day(night['night'])}, both readers: today's engine"
                       f" {len(night['readers']['old']['fires'])} fires, the new reader"
                       f" {len(night['readers']['new']['fires'])}, both on {len(night['both'])}.")
    else:
        summary.append("One real night, both readers: not run yet.")
    summary.append("You approve, or point at the charts that are wrong.")

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
 figure.miss{{border-color:#d62728}} figure.hit{{border-color:#2e8b57}}
 img{{width:100%;height:auto}} figcaption{{padding-top:6px;font-size:13px}} .nopage{{color:#999;padding:30px}}
 table{{border-collapse:collapse}} td,th{{border:1px solid #ddd;padding:4px 10px;text-align:left}}
</style>
<h1>The two-eyes reader — the approval pack</h1>
<p class="meta">Made {_e(record['made'])} from commit {_e(record.get('head') or '?')} · reader {_e(record['ruleset'])}
 · OHLC bars; red: your lines and your days; blue: the reader's box, thin blue its mini; green: its LPS and trigger.</p>
<h2>In short</h2>
<ul class="short">{''.join(f'<li>{line}</li>' for line in summary)}</ul>
<h2>Your {record['marks']['drawings']} drawings — misses first, by the first step where the reader leaves yours</h2>
<div class="grid">{''.join(_his_figure(row) for row in his)}</div>
<h2>The junk</h2>
<h3 id="junk-rule">For you to rule</h3><div class="grid">{group(JUNK_TO_RULE)}</div>
<h3 id="junk-eye">For your eye</h3><div class="grid">{group(JUNK_FOR_EYE)}</div>
<h3 id="junk-rest">The rest of the junk</h3><div class="grid">{group(rest)}</div>
<h2 id="grade">The grade sheet</h2>
<p>Your drawings: {_letters(record['grade']['his'])}. The junk's fire days: {_letters(record['grade']['junk'])}.
 <a href="{_e(record['grade']['sheet'])}">The sheet</a>: your drawings and the junk fires ranked together by the
 grade.</p>
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
