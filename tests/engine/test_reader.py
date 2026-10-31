"""The walking skeleton: a reader that answers "no lines", wired end to end.

Task 5 of the two-eyes-reader build. Everything here is about SHAPE and
REFUSAL, not about reading a chart — the new reader reads nothing yet, on
purpose. What these pin is that it travels every seam the old reader's answer
travels, that it is a leaf, and that it fails closed and loud on the four ways
a frame can be wrong without looking wrong.
"""
from __future__ import annotations

from _paths import REPO_ROOT
import ast
import datetime as dt
import os

import pandas as pd
import pytest

_ROOT = str(REPO_ROOT)
_PACKAGE = os.path.join(_ROOT, "engine_alpha")

#: The files in the engine that are NOT stages: the gate (every caller's way in), what the reader hands out
#: (the result row, the archive family), the engine config stamp and the stock's own facts. The stages may not
#: import them — nor config, the pipeline, the webapp or the tools: the reader is a leaf that reads a chart.
_NOT_A_STAGE = {"gate.py", "result.py", "archive.py", "stamp.py", "stock.py"}
_OUTSIDE_THE_STAGES = ("engine_alpha.gate", "engine_alpha.result", "engine_alpha.archive", "engine_alpha.stamp",
                       "engine_alpha.stock", "config", "core", "webapp", "tools")
_OLD_ENGINE = _OUTSIDE_THE_STAGES

#: The package a file in the leaf sits in, for resolving its relative imports.
_LEAF_PACKAGE = "engine_alpha"


def _frame(days=("2026-03-02", "2026-03-03", "2026-03-04", "2026-03-05",
                 "2026-03-06")) -> pd.DataFrame:
    n = len(days)
    return pd.DataFrame(
        {"Open": [1.0] * n, "High": [2.0] * n, "Low": [0.5] * n,
         "Close": [1.5] * n, "Volume": [1000] * n},
        index=pd.to_datetime(list(days)))


# --------------------------------------------------------------------------- #
# It is a leaf                                                                #
# --------------------------------------------------------------------------- #
def _modules_named(tree, package: str = _LEAF_PACKAGE) -> list:
    """Every module this source names — the ONE reading of an import.

    The guard and the guard's own proof both call this, so the proof cannot
    pass against a copy of the rule while the real walk uses another.
    """
    modules = []
    for node in ast.walk(tree):
        # EVERY name on the line, not just the first: `import os,
        # engine_alpha.structure` hides the offence behind a decoy.
        if isinstance(node, ast.ImportFrom):
            # A relative import is resolved against the file's package:
            # `from ..structure import pivots` inside the leaf IS
            # engine_alpha.structure, and reading only `structure` missed it.
            base = node.module or ""
            if node.level:
                parts = package.split(".")[: len(package.split(".")) - (node.level - 1)]
                base = ".".join(parts + ([node.module] if node.module else []))
            modules.append(base)
            # `from engine_alpha import evaluation` names a MODULE in the
            # import list: the module part alone is just `engine_alpha`.
            modules.extend(f"{base}.{a.name}" for a in node.names if a.name != "*")
        elif isinstance(node, ast.Import):
            modules.extend(a.name for a in node.names)
        # A DYNAMIC import makes no import node at all, so an AST walk that
        # looks only for `Import` sees nothing — the one way into this package
        # a blind check found still open. A name built at runtime cannot be
        # read here, but a written-down one can, and a written-down one is
        # what somebody reaching for the old engine would write.
        elif isinstance(node, ast.Call):
            called = node.func
            name = getattr(called, "attr", None) or getattr(called, "id", None)
            if name in ("import_module", "__import__") and node.args:
                first = node.args[0]
                if isinstance(first, ast.Constant) and isinstance(first.value, str):
                    modules.append(first.value)
    return modules


def _reaches_the_old_engine(tree, package: str = _LEAF_PACKAGE) -> list:
    return [m for m in _modules_named(tree, package)
            if any(m == old or m.startswith(old + ".") for old in _OLD_ENGINE)]


def test_the_new_package_imports_nothing_from_the_old_engine():
    """Growing the new reader inside the old is how the last three attempts
    ended up measuring the old engine wearing a new name."""
    offences = []
    # A WALK, not a listing: a future engine_alpha/sub/ package would
    # be invisible to os.listdir, and invisible is how a guard stops guarding.
    for folder, _dirs, files in os.walk(_PACKAGE):
        if "__pycache__" in folder:
            continue
        for name in sorted(f for f in files if f.endswith(".py")):
            if folder == _PACKAGE and name in _NOT_A_STAGE:
                continue
            path = os.path.join(folder, name)
            shown = os.path.relpath(path, _PACKAGE)
            package = ".".join([_LEAF_PACKAGE] + [
                p for p in os.path.relpath(folder, _PACKAGE).split(os.sep) if p != "."])
            with open(path, encoding="utf-8") as f:
                tree = ast.parse(f.read(), filename=path)
            offences += [f"{shown} imports {m}" for m in _reaches_the_old_engine(tree, package)]
    assert not offences, (
        "the reader's stages are a LEAF and import nothing from the gate, the result, the archive, the stamp, "
        f"the stock facts or anything outside the engine: {offences}")


@pytest.mark.parametrize("line,hidden", [
    ("from engine_alpha.gate import evaluate_ticker", True),
    ("import engine_alpha.result", True),
    # The decoy: a blind guard reads only the FIRST name on the line.
    ("import os, engine_alpha.stamp", True),
    # No import node exists for either of these.
    ("importlib.import_module('engine_alpha.archive')", True),
    ("__import__('engine_alpha.stock')", True),
    ("importlib.import_module('pandas')", False),
    # The shapes a blind survey once found a first version missing:
    ("from engine_alpha import gate", True),
    ("from engine_alpha import result", True),
    ("from . import gate", True),                     # relative, from inside the engine
    ("from config import settings", True),
    ("from core.pipeline import data", True),
    ("from . import record", False),                  # the leaf's own modules
    ("from engine_alpha import numbers as M", False),
    ("from engine_alpha import record", False),
    ("from engine_alpha.box import walk", False),
    ("import pandas as pd", False),
])
def test_the_leaf_guard_sees_every_way_the_old_engine_can_be_imported(line, hidden):
    """The guard's own proof, and the three shapes a blind check found it
    missing: a second name on one import line, a nested sub-package, and a
    dynamic import, which leaves no import node in the tree at all."""
    caught = bool(_reaches_the_old_engine(ast.parse(line)))
    assert caught is hidden, f"{line!r}: caught={caught}, expected {hidden}"


def test_the_guard_walks_sub_packages_not_just_the_top_folder():
    """os.listdir would not see engine_alpha/sub/, and a guard that
    cannot see a file is a guard that always passes for it."""
    import inspect

    source = inspect.getsource(test_the_new_package_imports_nothing_from_the_old_engine)
    # The CALL, not the word: the guard's own comment names os.listdir to say
    # why it is not used, and a plain substring check fails on that comment.
    assert "os.walk(" in source and "os.listdir(" not in source


# --------------------------------------------------------------------------- #
# The frame contract — fails closed, and says which day                       #
# --------------------------------------------------------------------------- #
def test_a_clean_frame_is_read_and_answers_no_lines():
    from engine_alpha import reader

    read = reader.read("TEST", _frame())
    assert read.state == reader.NO_LINES
    assert read.failed is False
    assert read.boxes == () and read.lps is None and read.trail == ()
    assert read.fired is False
    assert read.as_of == dt.date(2026, 3, 6)


def test_a_day_deleted_from_the_middle_is_refused():
    """The dangerous one: every remaining bar is valid, the index is still
    sorted, and the box is simply a day shorter than the market was."""
    from engine_alpha import reader

    whole = _frame()
    read = reader.read("TEST", whole.drop(whole.index[2]))
    assert read.failed is True
    assert read.state == reader.READ_FAILED
    assert "missing from the middle" in read.refusal
    assert "2026-03-03" in read.refusal and "2026-03-05" in read.refusal


def test_the_contract_passes_every_real_frame_in_the_fixtures():
    """The guard that catches the worst kind of contract: one that refuses
    everything.

    As first written this refused 35 of 35 of his drawings and 37 of 37 fleet
    charts — every one of them on a single missing 2025-01-09, the National
    Day of Mourning for President Carter, which no rule calendar predicts. A
    frame contract that never passes is not strict, it is broken, and nothing
    else in the suite would have said so.
    """
    from engine_alpha import reader
    from tools.regression import shadow_diff
    from core.calibration.replay import load_sealed_fixture, prepared_frame

    checked, refused = 0, []
    for loader in (load_sealed_fixture, shadow_diff._load_fixture):
        frames, _ = loader()
        assert frames, "the fixture went empty — this test would pass vacuously"
        for key, raw in frames.items():
            prep = prepared_frame(raw, raw.index[-1])
            read = reader.read(str(key), prep[0] if prep else raw)
            checked += 1
            if read.failed:
                refused.append(f"{key}: {read.refusal}")
    assert checked >= 70, f"only {checked} real frames checked"
    assert not refused, f"the contract refuses real charts: {refused[:5]}"


def test_the_unscheduled_closures_are_days_the_market_really_shut():
    """These cannot be generated by a rule, so they are listed — and a wrong
    entry silently turns a real trading day into a hole."""
    from engine_alpha.chart import UNSCHEDULED_CLOSURES, is_trading_session

    assert "2025-01-09" in UNSCHEDULED_CLOSURES, "President Carter's mourning day"
    assert "2012-10-29" in UNSCHEDULED_CLOSURES, "Hurricane Sandy"
    for day in UNSCHEDULED_CLOSURES:
        assert is_trading_session(day) is False, f"{day} is listed but still open"
    # A neighbour that WAS open, so the list is not swallowing ordinary days.
    assert is_trading_session("2025-01-08") is True
    assert is_trading_session("2025-01-10") is True


def test_a_market_holiday_is_not_a_deleted_day():
    """Christmas Day is not a hole. A weekday-counting contract would refuse
    every holiday in the corpus, which is why this uses the NYSE calendar."""
    from engine_alpha import reader

    read = reader.read("TEST", _frame(("2025-12-24", "2025-12-26", "2025-12-29")))
    assert read.failed is False, read.refusal


def test_the_same_day_at_two_clock_times_is_still_the_same_day_twice():
    """The rule is asked in DAYS, because its name says days.

    Asked in timestamps it let the pair through: 09:30 and 16:00 on one date
    are not equal, and the gap rule below it normalizes, so the two rows read
    as consecutive trading days. Two rows for one day is how a box silently
    gains a day the market never traded.
    """
    from engine_alpha import reader

    frame = _frame()
    doubled = pd.concat([frame, frame.iloc[[2]].rename(
        index={frame.index[2]: frame.index[2] + pd.Timedelta(hours=6, minutes=30)})]
    ).sort_index()
    read = reader.read("TEST", doubled)
    assert read.failed is True
    assert "the same day twice" in read.refusal, read.refusal


@pytest.mark.parametrize("rule,build", [
    ("the same day twice",
     lambda f: pd.concat([f, f.iloc[[1]]]).sort_index()),
    ("days out of order",
     lambda f: f.iloc[[0, 2, 1, 3, 4]]),
    ("a high under its low",
     lambda f: f.assign(High=[2.0, 2.0, 2.0, 0.1, 2.0])),
    ("missing column(s)",
     lambda f: f.drop(columns=["Low"])),
    ("empty frame",
     lambda f: f.iloc[0:0]),
])
def test_every_way_a_frame_can_be_wrong_is_refused_by_name(rule, build):
    """A refusal names the rule, so the reason reaches whoever reads the log."""
    from engine_alpha import reader

    read = reader.read("TEST", build(_frame()))
    assert read.failed is True
    assert rule in read.refusal, f"refused, but not as {rule!r}: {read.refusal}"


def test_a_crashed_read_is_never_the_words_no_lines():
    """"No lines" is what the screen says about a chart that has none. A read
    that fell over must not borrow that sentence — it is a counted failure."""
    from engine_alpha import reader

    whole = _frame()
    read = reader.read("TEST", whole.drop(whole.index[2]))
    assert read.state != reader.NO_LINES
    assert read.state == "no lines, the read failed"
    assert read.failed is True and read.refusal


# --------------------------------------------------------------------------- #
# The record's shape — every later stage fills it, none may reshape it        #
# --------------------------------------------------------------------------- #
def test_the_record_already_holds_what_his_method_needs():
    """Written while it is empty, because the adapter, the archive row and the
    screen are all built against it from the first commit."""
    from engine_alpha import record

    read = record.Read(ticker="TEST")
    assert read.boxes == () and read.trail == () and read.lps is None
    assert read.parent is None and read.mini is None

    line = record.Line(price=100.0, anchor_day=dt.date(2026, 1, 5))
    assert line.anchor_day == dt.date(2026, 1, 5), \
        "a line carries the DAY it was anchored, not only a price"

    # Two boxes live at once — his ruling: a mini and its parent are one setup.
    parent = record.Box(resistance=line, support=record.Line(90.0, line.anchor_day),
                        opened_day=line.anchor_day, role=record.ROLE_PARENT)
    mini = record.Box(resistance=record.Line(98.0, line.anchor_day),
                      support=record.Line(94.0, line.anchor_day),
                      opened_day=line.anchor_day, role=record.ROLE_MINI)
    both = record.Read(ticker="TEST", boxes=(parent, mini))
    assert both.parent is parent and both.mini is mini

    with pytest.raises(ValueError):
        record.Box(resistance=line, support=line, opened_day=line.anchor_day,
                   role="whatever")


def test_the_lps_must_say_which_box_it_was_read_against():
    """With two live boxes, "the last run of receding days" is ambiguous until
    you say receding INSIDE WHAT."""
    from engine_alpha import record

    with pytest.raises(TypeError):
        record.Lps(start_day=dt.date(2026, 3, 2), end_day=dt.date(2026, 3, 6))
    lps = record.Lps(start_day=dt.date(2026, 3, 2), end_day=dt.date(2026, 3, 6),
                     read_against=record.ROLE_PARENT)
    assert lps.read_against == record.ROLE_PARENT


def test_a_box_keeps_the_daily_range_it_was_born_with():
    """One unit per box, known at its birth — never the read day's, so a box
    does not change size because today happened to be wide."""
    from engine_alpha import record

    box = record.Box(resistance=record.Line(100.0, dt.date(2026, 1, 5)),
                     support=record.Line(90.0, dt.date(2026, 1, 5)),
                     opened_day=dt.date(2026, 1, 5), daily_range=2.5)
    assert box.daily_range == 2.5
    with pytest.raises(Exception):
        box.daily_range = 3.0       # frozen: a shown line never moves


def test_a_read_only_fires_with_both_a_box_and_a_buy():
    from engine_alpha import record

    line = record.Line(100.0, dt.date(2026, 1, 5))
    box = record.Box(resistance=line, support=record.Line(90.0, line.anchor_day),
                     opened_day=line.anchor_day)
    assert record.Read(ticker="T", boxes=(box,)).fired is False, \
        "a box with no buy is not a fire"
    lps = record.Lps(dt.date(2026, 3, 2), dt.date(2026, 3, 6),
                     record.ROLE_PARENT, trigger_price=None)
    assert record.Read(ticker="T", boxes=(box,), lps=lps).fired is False, \
        "a run of receding days with no trigger is not a fire"
    priced = record.Lps(dt.date(2026, 3, 2), dt.date(2026, 3, 6),
                        record.ROLE_PARENT, trigger_price=101.5)
    assert record.Read(ticker="T", boxes=(box,), lps=priced).fired is True
    assert record.crashed("T", None, "boom").fired is False, \
        "a crashed read never fires"


def test_a_read_carries_its_own_days_close():
    """The archive stores it as the setup's price and the forward-returns
    backfill scales every trigger by it, so it must be the read day's real
    close — never a stand-in from a line (build task 6)."""
    from engine_alpha import reader

    frame = _frame()
    frame.loc[frame.index[-1], "Close"] = 1.73
    assert reader.read("TEST", frame).close == 1.73


def test_a_day_the_caller_names_that_is_not_a_day_is_a_counted_failure():
    """read() promises never to raise. The record now cuts every day on the
    way in and refuses anything else, and that refusal must arrive inside the
    read's own guard as a counted failure, not escape it (build task 6)."""
    from engine_alpha import reader

    read = reader.read("TEST", _frame(), as_of="2026-03-06")
    assert read.failed is True and read.refusal


def test_the_crash_path_cannot_crash_on_an_odd_day():
    """The path a broken read takes may not break in turn: a day it cannot
    read is dropped so the refusal still arrives."""
    from engine_alpha import record

    crashed = record.crashed("TEST", "2026-03-06", "the frame was not a chart")
    assert crashed.failed is True and crashed.as_of is None
