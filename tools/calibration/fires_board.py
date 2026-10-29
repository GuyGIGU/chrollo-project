"""His yardstick on his LIVE drawings, with the walk's switches (Wed 28/10/2026).

His ruling of Sat 24/10/2026: the setup fires on his buy day at his trigger — "fires on his day at his trigger" —
measured on every drawing in his journal that has a trigger drawn (a drawing without one is named and skipped).
The core board's own reading per drawing (`core_board.score_setup`: the reader's box against his two lines, HIS /
CLOSE / OTHER, and the fire on his last receding day at his trigger to the cent), on the bars the drawing was
frozen on: the sealed fixture's frame for a sealed drawing, the frozen frame by the mark's digest for the rest.
Never a re-fetch, never a rule of its own.

A reading of his is measured as ONE switch plus ONE run: `--switch NAME=0` turns one of the walk's named switches
off (`two_eyes_numbers`: every upper-case name bound to a bool) for this process only; nothing is written anywhere.
That is what his word asked for: *"we've got to write the engine in a certain way that will allow us to easily
tune it in the right direction"* — the readings tried as monkeypatches before are now one flag each.

THE JOURNAL IS NEVER OPENED IN PLACE: the tool takes a fresh copy with sqlite3's backup API from a read-only
connection (so the -wal's newest drawings are in it — a file copy drops them) into a temporary directory, reads
the copy and removes it. The journal, the frozen frames and the sealed fixture are the MAIN checkout's (found
through git's common dir, so a worktree reads his real drawings and not its own empty folders). `--db` reads an
existing copy instead (an earlier night's board, the same numbers again). The export tool (`guided_list_export`)
is never run: its --help runs the export.

    python -m tools.calibration.fires_board                             # as built, on a fresh copy
    python -m tools.calibration.fires_board --switch ONE_BAR_PAIR=0     # one reading, one run
    python -m tools.calibration.fires_board --db COPY.db                # an earlier copy of the journal
"""
from __future__ import annotations

import argparse
import contextlib
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
from collections import Counter
from urllib.request import pathname2url

try:
    from tools._bootstrap import configure_path
except ImportError:  # invoked as a script from the repo root
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from tools._bootstrap import configure_path  # type: ignore
_ROOT = configure_path(backend=True)

from engine_alpha import two_eyes_numbers as M  # noqa: E402
from tools.regression.marks_corpus import DRAWN_EVENT_KEYS, setup_key, validate_setup  # noqa: E402

NO_TRIGGER = "no trigger drawn"
NO_LPS = "no LPS drawn"
NO_FRAME = "no frozen frame"


# --------------------------------------------------------------------------- #
# The switches                                                                #
# --------------------------------------------------------------------------- #
def switch_names() -> tuple:
    """The walk's switches: every upper-case name of ``two_eyes_numbers`` bound to a bool."""
    return tuple(sorted(name for name, value in vars(M).items() if name.isupper() and isinstance(value, bool)))


def parse_switch(text: str) -> tuple:
    """``NAME=0`` / ``NAME=1`` (``off`` / ``on``, ``false`` / ``true`` too) -> ``(name, value)``; a name that is
    not a switch, or a value that is not one of those, is refused out loud."""
    name, sep, value = text.partition("=")
    name = name.strip().upper()
    if not sep or name not in switch_names():
        raise ValueError(f"not a switch: {text!r} (the switches: {', '.join(switch_names())}; write NAME=0 or NAME=1)")
    words = {"0": False, "1": True, "off": False, "on": True, "false": False, "true": True}
    if value.strip().lower() not in words:
        raise ValueError(f"a switch is 0 or 1: {text!r}")
    return name, words[value.strip().lower()]


@contextlib.contextmanager
def switched(overrides: dict):
    """The switches set for the block, and put back after it, whatever happens inside."""
    before = {name: getattr(M, name) for name in overrides}
    try:
        for name, value in overrides.items():
            setattr(M, name, bool(value))
        yield
    finally:
        for name, value in before.items():
            setattr(M, name, value)


def switch_words(overrides: dict) -> str:
    if not overrides:
        return "as built (every switch on)"
    return ", ".join(f"{name}={'1' if value else '0'}" for name, value in sorted(overrides.items()))


# --------------------------------------------------------------------------- #
# His journal: a fresh copy, read-only, the WAL included                      #
# --------------------------------------------------------------------------- #
def main_checkout() -> str:
    """The checkout that holds his live journal, the frozen frames and the cache: the one git's common dir sits
    in (a linked worktree's own folders are empty). This checkout when git does not answer."""
    try:
        run = subprocess.run(["git", "rev-parse", "--git-common-dir"], cwd=_ROOT, capture_output=True, text=True,
                             check=True)
    except (OSError, subprocess.CalledProcessError):
        return _ROOT
    common = run.stdout.strip()
    return os.path.normpath(os.path.join(_ROOT, common, "..")) if common else _ROOT


def live_journal(checkout: str) -> str:
    return os.path.join(checkout, "webapp", "backend", "trading_journal.db")


def copy_journal(src: str, dst: str) -> str:
    """A copy of the journal through sqlite3's backup API from a read-only connection: the -wal's newest writes
    are in it (a file copy of the .db alone drops them: his four drawings of Fri 17/10/2026 were in the -wal), and
    the live file is never opened for writing."""
    if not os.path.exists(src):
        raise FileNotFoundError(f"no journal at {src}")
    source = sqlite3.connect("file:" + pathname2url(os.path.abspath(src)) + "?mode=ro", uri=True)
    try:
        target = sqlite3.connect(dst)
        try:
            source.backup(target)
        finally:
            target.close()
    finally:
        source.close()
    return dst


def live_setups(db_path: str) -> tuple:
    """His marks in the export's shape, read from a copy: ``(setups, skipped)``, ``skipped`` the keys with no LPS
    drawn (nothing to read on). The export tool is never run."""
    con = sqlite3.connect("file:" + pathname2url(os.path.abspath(db_path)) + "?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        marks = [dict(m) for m in con.execute("SELECT * FROM calibration_marks ORDER BY ticker, as_of_date")]
        events = [dict(e) for e in con.execute("SELECT * FROM calibration_mark_events ORDER BY mark_id, start_date")]
    finally:
        con.close()
    by_mark = {}
    for e in events:
        by_mark.setdefault(e["mark_id"], []).append(e)
    setups, skipped = [], []
    for m in marks:
        setup = {
            "ticker": m["ticker"], "setup": str(m["as_of_date"]), "source": "operator", "as_of": str(m["as_of_date"]),
            "frame_digest": m["frame_digest"],
            "box": [str(m["box_start_date"]), str(m["box_end_date"])],
            "anchors": {"R": str(m["r_anchor_date"]), "S": str(m["s_anchor_date"])},
            "first_rail": m["first_rail"],
            "trigger": str(m["trigger_date"]) if m["trigger_date"] else None,
            "trigger_price": float(m["trigger_price"]) if m["trigger_price"] is not None else None,
            "rails_drawn": {"R": float(m["resistance"]), "S": float(m["support"])},
        }
        evs = by_mark.get(m["id"], [])
        lps = [e for e in evs if e["event_type"] == "lps"]
        if lps:
            setup["lps"] = [str(lps[0]["start_date"]), str(lps[0]["end_date"])]
        if len(lps) > 1:
            setup["lps2"] = [str(lps[1]["start_date"]), str(lps[1]["end_date"])]
        mini = [e for e in evs if e["event_type"] == "mini"]
        if mini:
            setup["mini"] = {"band": {"R": float(mini[0]["band_high"]), "S": float(mini[0]["band_low"])},
                             "span": [str(mini[0]["start_date"]), str(mini[0]["end_date"])]}
        for kind in DRAWN_EVENT_KEYS:
            spans = [[str(e["start_date"]), str(e["end_date"])] for e in evs if e["event_type"] == kind]
            if spans:
                setup[kind] = spans
        if "lps" not in setup:
            skipped.append((setup_key(setup), NO_LPS))
            continue
        validate_setup(setup, setup_key(setup))
        setups.append(setup)
    return setups, skipped


def frame_for(setup: dict, sealed_frames: dict, frames_dir: str):
    """The bars the drawing was frozen on: the sealed fixture's frame, else the frozen frame by the mark's digest
    (``frames_dir``, the main checkout's ``calibration_frames``). None when neither carries it."""
    import pandas as pd
    from core.calibration.replay import fixture_frame
    from domains.calibration import frame_store

    key = setup_key(setup)
    raw = fixture_frame(sealed_frames, key, setup["ticker"]) if key in sealed_frames else None
    if raw is None:
        frame_store.FRAMES_DIR = frames_dir
        raw = frame_store.load_frame(setup["ticker"], setup["as_of"], setup["frame_digest"])
    if raw is None:
        return None
    raw = raw.copy()
    if not isinstance(raw.index, pd.DatetimeIndex):
        raw.index = pd.to_datetime(raw.index)
    return raw


# --------------------------------------------------------------------------- #
# The board                                                                   #
# --------------------------------------------------------------------------- #
def score(setups: list, sealed_frames: dict, frames_dir: str) -> tuple:
    """Every drawing with a trigger through the core board's reading: ``(rows, skipped)``."""
    from tools.calibration import core_board

    rows, skipped = [], []
    for setup in setups:
        key = setup_key(setup)
        if setup.get("trigger_price") is None:
            skipped.append((key, NO_TRIGGER))
            continue
        raw = frame_for(setup, sealed_frames, frames_dir)
        if raw is None:
            skipped.append((key, NO_FRAME))
            continue
        scored = core_board.score_setup(setup, raw)
        read = scored["on_last"]["read"]
        trigger = None if read.lps is None else float(read.lps.trigger_price)
        his = float(setup["trigger_price"])
        off = None if trigger is None or not scored["unit"] else (trigger - his) / float(scored["unit"])
        rows.append({"key": key, "box": scored["box"], "fired": bool(scored["on_last"]["fired"]),
                     "strict": bool(scored["strict"]), "trigger": trigger, "his_trigger": his, "off": off,
                     "why": scored["why"]})
    return rows, skipped


def format_board(rows: list, skipped: list, overrides: dict) -> str:
    n = len(rows)
    crossed = Counter((r["box"], r["fired"]) for r in rows)
    near = [r for r in rows if r["fired"] and r["off"] is not None and abs(r["off"]) <= 0.5]
    out = [f"THE FIRES ON HIS {n} — the reader fires on his last receding day at his trigger; the box beside it",
           f"  switches: {switch_words(overrides)}",
           "  the box x fired on his day: " + " · ".join(
               f"{box} {crossed[(box, True)]} fired / {crossed[(box, False)]} not"
               for box in ("HIS", "CLOSE", "OTHER", "NONE") if crossed[(box, True)] or crossed[(box, False)]),
           f"  FIRES ON HIS DAY AT HIS TRIGGER (to the cent): {sum(1 for r in rows if r['strict'])} of {n}",
           f"  fires on his day, the trigger within half a daily range of his: {len(near)} of {n}",
           "  the misses:"]
    for r in sorted((r for r in rows if not r["strict"]), key=lambda r: (r["fired"], r["box"], r["key"])):
        trigger = "none" if r["trigger"] is None else f"{r['trigger']:.2f}"
        off = "" if r["off"] is None else f" ({r['off']:+.2f} ranges)"
        out.append(f"    {r['key']:<18} box {r['box']:<6} fired {'yes' if r['fired'] else 'no ':<4} trigger {trigger}"
                   f" vs his {r['his_trigger']:.2f}{off}  {r['why'] or 'fired, not on his day at his trigger'}")
    if not any(not r["strict"] for r in rows):
        out.append("    none")
    out.append("  skipped: " + (", ".join(f"{key} ({why})" for key, why in skipped) or "none"))
    return "\n".join(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--switch", metavar="NAME=0|1", action="append", default=[],
                    help=f"one of the walk's switches, off or on, for this run only ({', '.join(switch_names())})")
    ap.add_argument("--db", metavar="COPY", help="an existing COPY of the journal to read instead of taking a fresh one "
                    "(never the live file)")
    args = ap.parse_args(argv)
    overrides = dict(parse_switch(text) for text in args.switch)
    from core.calibration.replay import load_sealed_fixture
    from engine_alpha.freeze.manifest import manifest_hash

    checkout = main_checkout()
    frames_dir = os.path.join(checkout, "calibration_frames")
    sealed_frames, _ = load_sealed_fixture()
    scratch = None
    try:
        if args.db:
            db_path = args.db
            print(f"  his drawings: the copy {db_path}")
        else:
            scratch = tempfile.mkdtemp(prefix="chrollo-fires-board-")
            db_path = copy_journal(live_journal(checkout), os.path.join(scratch, "journal_copy.db"))
            print(f"  his drawings: a fresh copy of {live_journal(checkout)} (backup API, read-only, the WAL included)")
        setups, skipped = live_setups(db_path)
        started = time.perf_counter()
        with switched(overrides):
            print(f"  engine {manifest_hash()[:12]} · switches: {switch_words(overrides)} · {len(setups)} drawings "
                  f"with an LPS, {len(skipped)} without")
            rows, more = score(setups, sealed_frames, frames_dir)
        print(format_board(rows, skipped + more, overrides))
        print(f"  {len(rows)} drawings read in {time.perf_counter() - started:.1f}s")
    finally:
        if scratch:
            shutil.rmtree(scratch, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
