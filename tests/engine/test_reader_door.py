"""Every caller of the chart reader goes through ONE door.

Task 4 of the two-eyes-reader build. Two readers are about to exist side by
side, so the question "which reader answered?" must have one answer per read and
one place that decides it. The failure this prevents is specific and was found
by a blind check of the plan: a switch placed behind the nightly scan's entry
point would have left the calibration workbench's miss explainer, the archive
row re-read, the chart-state page and every gate still calling the old engine
directly — a split brain that no test would have noticed.

These assertions are about WIRING, not behaviour. The door forwards to the same
functions with the same arguments, so the engine's output is byte-identical;
that is proved by the fleet shadow, the reader pin, the junk corpus and the
marks ratchet, not here.
"""
from __future__ import annotations

from _paths import REPO_ROOT
import ast
import os

import pytest

_ROOT = str(REPO_ROOT)

# The reader's entry points, as they are named inside the engine. The guarded
# wrapper is here too: it is a full way in, not an internal step.
_ENTRIES = {"_evaluate_ticker", "evaluate_ticker_with_near_miss",
            "evaluate_ticker_with_watch", "_run_eval_chain",
            "_run_guarded_chain", "read_structure"}

# Everything OUTSIDE the engine that reads a chart and must go through the door:
# production paths and the committed gates. Instruments (censuses, A/Bs, one-off
# probes) may keep calling the old engine by name while both readers exist —
# what matters is that nothing which SHIPS or GATES can read a chart without
# saying which reader answered.
_MUST_USE_THE_DOOR = (
    "core/pipeline/screening/screener.py",                        # the nightly scan
    "core/archive/seed.py",                             # the archive seed, and the single-row re-read
    "webapp/backend/domains/screener/chart_state.py",   # the chart-state page
    "webapp/backend/domains/calibration/fired.py",     # "why did this mark miss"
    "core/calibration/replay.py",                                  # the seam three gates share
    "tools/regression/marks_corpus.py",                            # the marks ratchet
    "tools/regression/negative_corpus.py",                         # the junk corpus
    "tools/regression/shadow_diff.py",                             # the fleet shadow
    "tools/calibration/calibration_harness.py",                     # the agreement harness
    "webapp/backend/domains/calibration/grading.py",   # the workbench grading the harness shares (main moved fired_one and the veto read here)
    "tools/regression/cause_veto_corpus.py",                       # the cause-before-effect bite gate
    "tools/regression/fold_parity.py",                             # the fold-parity gate the reader pin builds on
    # Reaches the reader through the seed's one re-read (`_evaluate_at_date`),
    # which goes through the door. Listed so it stays that way: this route
    # re-reads a single archived row on demand, and a direct call here would be
    # the easiest one to add and the hardest to notice.
    "webapp/backend/domains/archive/actions.py",
)


# Where a reader entry point comes from when it is NOT the door.
# `engine_alpha.structure` is here because the package re-exports `read_structure`
# in its own __all__, so `from engine_alpha.structure import read_structure` is
# the natural way to write it and must not be the way around the door.
# Both spellings of the narrative package: on main's layout it re-exports
# `read_structure` from `.reader`, and the door itself imports it the short way.
# The package name is DERIVED from the module's, never spelled out: the porter's
# text pass reads a bare "engine_alpha.structure.<package>" as the pre-refactor
# flat module and rewrites it, and its own no-churn guard then fails (port
# verifier, second pass, Sat 26/09/2026).
_NARRATIVE_READER = "engine_alpha.structure.narrative.reader"
_OLD_SOURCES = ("engine_alpha.evaluation", _NARRATIVE_READER,
                _NARRATIVE_READER.rsplit(".", 1)[0],
                "engine_alpha.structure", "core.pipeline.screening.screener")


def _dotted(node) -> str:
    """`engine_alpha.evaluation` for the node behind `....._evaluate_ticker`."""
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if not isinstance(node, ast.Name):
        return ""
    parts.append(node.id)
    return ".".join(reversed(parts))


def _reaches_the_old_reader(path: str) -> set[str]:
    """Reader entry points this module can REACH having bound them from the old engine.

    The rule is reference, not call. An earlier version of this guard asked
    "does the file CALL it", and was blind to the one offence actually in the
    tree: the nightly scan picked the old engine's lane twin by name, handed
    the function object to a process pool, and never wrote a call at all —

        worker = evaluate_ticker_with_near_miss     # no Call node
        executor.submit(worker, ticker, df, ...)    # the read happens here

    Handing the old engine's function to something that will run it is exactly
    what a switch cannot re-point, so a mere reference is the offence.

    Binding is still fine: `core/pipeline/screening/screener.py` re-exports the two lane
    twins under their old names so instruments and tests keep working. An
    `import` binds a name; it does not load it. Two binding forms are followed:
    `from engine_alpha.evaluation import X` (a bare name) and
    `from engine_alpha import evaluation` (a module alias, then
    `evaluation.X`). Deferred imports inside a function count — they are how
    three of these callers reach the engine today.
    """
    with open(os.path.join(_ROOT, path), "r", encoding="utf-8") as f:
        tree = ast.parse(f.read(), filename=path)

    old_names: set[str] = set()     # bare names bound from the old engine
    old_modules: set[str] = set()   # whatever an old engine MODULE is bound as
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            if node.module in _OLD_SOURCES:
                old_names |= {(a.asname or a.name) for a in node.names
                              if a.name in _ENTRIES}
            for a in node.names:
                if f"{node.module}.{a.name}" in _OLD_SOURCES:
                    old_modules.add(a.asname or a.name)
        elif isinstance(node, ast.Import):
            for a in node.names:
                if a.name in _OLD_SOURCES:
                    # No `as`: the dotted path itself is how it is written.
                    old_modules.add(a.asname or a.name)

    reached: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            if node.id in old_names:
                reached.add(node.id)
        elif isinstance(node, ast.Attribute) and node.attr in _ENTRIES:
            owner = _dotted(node.value)
            # Either the module is bound under this name, or it is spelled out
            # in full — `engine_alpha.evaluation._evaluate_ticker(...)` after a
            # bare `import engine_alpha` reaches the reader just as surely.
            if owner and (owner in old_modules or owner in _OLD_SOURCES):
                reached.add(f"{owner}.{node.attr}")
    return reached


def test_the_door_exists_and_offers_the_readers_three_entry_points():
    """One module, three ways in: the whole chain, the chain without its guard,
    and the box read alone."""
    from engine_alpha import reader

    for name in ("evaluate_ticker", "run_eval_chain", "read_box", "which_reader"):
        assert callable(getattr(reader, name, None)), f"the door has no {name}()"


@pytest.mark.parametrize("path", _MUST_USE_THE_DOOR)
def test_every_shipping_and_gating_caller_goes_through_the_door(path):
    """No production path and no gate can reach a reader entry point directly."""
    direct = _reaches_the_old_reader(path)
    assert not direct, (
        f"{path} reaches the reader directly ({sorted(direct)}) — calling it, or "
        "handing it to something that will. Two readers are about to exist: "
        "import engine_alpha.reader and go through the door, or this file keeps "
        "reading the old engine after the switch is flipped and nothing says so."
    )


#: Instruments that read the old engine past the door through a brick rather than an entry point (the guard
#: above cannot see them): named, so they say which reader they read too.
_READS_OLD_BRICKS = ("tools/research/correspondence_census.py",)


def _binds_the_old_election(path: str) -> bool:
    """The file imports one of the old election's private doors from the old engine (they are not reader entry
    points, so `_reaches_the_old_reader` does not follow them)."""
    with open(os.path.join(_ROOT, path), "r", encoding="utf-8") as f:
        tree = ast.parse(f.read(), filename=path)
    return any(isinstance(node, ast.ImportFrom) and node.module == "engine_alpha.evaluation"
               and any(a.name in _OLD_ELECTION_DOORS for a in node.names) for node in ast.walk(tree))


#: The old election's private doors (verify-2 of the go-live build: an audit that reached the election through
#: `_resolve_structure_context` slipped past the first version of the guard below).
_OLD_ELECTION_DOORS = ("_resolve_structure_context", "_prepare_eval_frame")


def test_every_instrument_that_reads_the_old_box_past_the_door_says_so():
    """Go-live plan, task 4. An instrument (not a gate: those go through the door) may keep reading the old
    engine's box straight after the flip, but on a new-reader night it must say FIRST that it reads the OLD
    reader (``tools._bootstrap.say_old_reader``), or its reading passes for a judgement of tonight's screen.
    Found from the tree, not listed: a new instrument that reads the old box joins on its first commit."""
    import glob

    tools = sorted(os.path.relpath(p, _ROOT).replace(os.sep, "/")
                   for p in glob.glob(os.path.join(_ROOT, "tools", "**", "*.py"), recursive=True))
    # The box read itself, and the two private doors to the old election (verify-2 of the go-live build: an
    # audit that reached the election through `_resolve_structure_context` slipped past the first version).
    old_box = [p for p in tools if "read_structure" in _reaches_the_old_reader(p) or _binds_the_old_election(p)]
    assert "tools/audits/doctrine_audit.py" in old_box, "the inventory lost its own anchor case"
    silent = []
    for path in old_box + list(_READS_OLD_BRICKS):
        with open(os.path.join(_ROOT, path), encoding="utf-8") as f:
            if "say_old_reader(" not in f.read():
                silent.append(path)
    assert not silent, f"these read the OLD reader past the door and never say so: {silent}"


def test_the_guard_sees_a_reference_that_is_never_written_as_a_call(tmp_path):
    """The guard's own proof, kept beside it.

    This is the shape that got past the first version: the old engine's twin is
    picked by name and handed to a pool. It is also the shape the scan really
    used, so the guard is worthless if it cannot see it.
    """
    handed_over = tmp_path / "handed_over.py"
    handed_over.write_text(
        "from engine_alpha.evaluation import evaluate_ticker_with_near_miss\n"
        "from functools import partial\n"
        "def run(executor, rows):\n"
        "    worker = evaluate_ticker_with_near_miss\n"
        "    return executor.submit(worker, *rows)\n",
        encoding="utf-8")
    wrapped = tmp_path / "wrapped.py"
    wrapped.write_text(
        "from engine_alpha.evaluation import evaluate_ticker_with_watch\n"
        "from functools import partial\n"
        "def run(inner):\n"
        "    return partial(evaluate_ticker_with_watch, inner=inner)\n",
        encoding="utf-8")
    # Four more ways in, all found by a blind check of the first rule. Each was
    # a false GREEN; none needed anything cleverer than the obvious import.
    package_reexport = tmp_path / "package_reexport.py"
    package_reexport.write_text(
        "from engine_alpha.structure import read_structure\n"
        "def run(df, atr):\n"
        "    return read_structure(df, atr)\n",
        encoding="utf-8")
    package_alias = tmp_path / "package_alias.py"
    package_alias.write_text(
        "from engine_alpha import structure\n"
        "def run(df, atr):\n"
        "    return structure.read_structure(df, atr)\n",
        encoding="utf-8")
    spelled_out = tmp_path / "spelled_out.py"
    spelled_out.write_text(
        "import engine_alpha.evaluation\n"
        "def run(t, df):\n"
        "    return engine_alpha.evaluation._evaluate_ticker(t, df)\n",
        encoding="utf-8")
    guarded_wrapper = tmp_path / "guarded_wrapper.py"
    guarded_wrapper.write_text(
        "from engine_alpha.evaluation import _run_guarded_chain\n"
        "def run(t, df):\n"
        "    return _run_guarded_chain(t, df)\n",
        encoding="utf-8")

    # The form the door itself uses (engine_alpha/reader.py): on main's layout the
    # narrative package re-exports read_structure, so this is the natural spelling
    # and the porter's rewrite of the source list to `.reader` alone let it through
    # (port verifier, Sat 26/09/2026).
    package_narrative = tmp_path / "package_narrative.py"
    package_narrative.write_text(
        "from engine_alpha.structure.narrative import read_structure\n"
        "def run(df, atr):\n"
        "    return read_structure(df, atr)\n",
        encoding="utf-8")

    re_export_only = tmp_path / "re_export_only.py"
    re_export_only.write_text(
        "from engine_alpha.evaluation import evaluate_ticker_with_near_miss  # noqa: F401\n"
        "__all__ = ['evaluate_ticker_with_near_miss']\n",
        encoding="utf-8")

    # os.path.join keeps an absolute second argument, so these resolve outside
    # the repo without the helper needing a second way in.
    assert _reaches_the_old_reader(str(handed_over)) == {"evaluate_ticker_with_near_miss"}
    assert _reaches_the_old_reader(str(wrapped)) == {"evaluate_ticker_with_watch"}
    assert _reaches_the_old_reader(str(package_reexport)) == {"read_structure"}
    assert _reaches_the_old_reader(str(package_alias)) == {"structure.read_structure"}
    assert _reaches_the_old_reader(str(package_narrative)) == {"read_structure"}
    assert _reaches_the_old_reader(str(spelled_out)) == {
        "engine_alpha.evaluation._evaluate_ticker"}
    assert _reaches_the_old_reader(str(guarded_wrapper)) == {"_run_guarded_chain"}
    assert _reaches_the_old_reader(str(re_export_only)) == set(), (
        "a re-export is a binding, not a read; flagging it would force the "
        "screener to drop names its own tests and the instruments import")


def test_the_switch_is_read_in_exactly_one_place():
    """One function decides which reader answers; everything else asks it."""
    import subprocess

    # --untracked: a new door module is not committed on its first run, and a
    # guard that cannot see the file it guards is a guard that always passes.
    out = subprocess.run(
        ["git", "grep", "-l", "--untracked", "TWO_EYES_READER_ENABLED", "--",
         "*.py"], cwd=_ROOT, capture_output=True, text=True)
    files = {line.strip() for line in out.stdout.splitlines() if line.strip()}
    # The rule is about the ENGINE: one function decides which reader answers.
    # `config/settings.py` declares the switch, the manifest hashes its name so
    # the version stamp moves when it flips, and a test that flips it to see
    # what happens is not a second place that decides.
    #
    # NAMED, never a `tests/` wildcard. Task 2's guard listed three files; the
    # skeleton's tests widened it to any test file, which is how a guard stops
    # biting: a future test reading the setting for some non-test reason would
    # have passed in silence. A new name here is one line and a moment's
    # thought, which is exactly the cost it should carry.
    # config/engine.py holds the switch's default since the port onto main's layout
    # (settings.py re-exports it); the inert contract enrols the switch by NAME
    # as a dark engine flag and decides nothing. The LPS tests flip it to send a
    # real fire through the door (task 12a), and the yardstick flips it to read
    # the new reader as its third arm: both measure, neither decides. The core
    # board's test flips it to check the board against the door on his 35. The
    # night replay (task 15) reads one scan night with it off and then on, the
    # old reader and the new through the door: it measures, it decides nothing.
    # The failed-read test (council review 2026-10-09, finding 3) flips it to make
    # the new reader refuse a chart through the seed and the manual add. The
    # scan's walking skeleton (go-live plan task 2) flips it to send his ALB
    # through the whole scan and into a throwaway archive, and back off. The go-live
    # plan's tasks 4 and 5 flip it to make the tools, the audits and the workbench
    # meet a new-reader night (refused charts, the notice, the miss's reason).
    # The morning check (task 9) flips it to read the night twice, new and old: it measures.
    files -= {"tests/tooling/test_old_reader_tools.py", "tests/backend/test_workbench_new_reader.py",
              "config/settings.py", "config/engine.py", "engine_alpha/freeze/manifest.py",
              "tests/contracts/test_inert_contract.py", "tests/archive/test_read_failed_is_said.py",
              "tests/pipeline/test_scan_under_the_new_reader.py",
              "tests/engine/test_reader_door.py", "tests/engine/test_two_eyes_adapter.py",
              "tests/engine/test_two_eyes_skeleton.py", "tests/engine/test_two_eyes_lps.py",
              "tests/engine/test_two_eyes_mini.py",
              "tests/tooling/test_core_board.py",
              "tests/tooling/test_yardstick.py", "tools/calibration/yardstick.py",
              "tools/calibration/parallel_night.py",
                  "tools/ops/morning_check.py"}
    assert files == {"engine_alpha/reader.py"}, (
        f"the reader switch is read in {sorted(files)}; it belongs in "
        "engine_alpha.reader.which_reader() alone")


def test_the_door_names_the_reader_that_answered_out_of_band():
    """The reader's name rides a sink, never the result.

    A name inside the result dict would reach the archive row and the wire, and
    flag-off output must stay byte-identical.
    """
    from engine_alpha import reader

    stamp: dict = {}
    reader._stamp(stamp, reader.READER_OLD)
    assert stamp == {"reader": "old"}
    reader._stamp(None, reader.READER_OLD)  # no sink, no work, no crash


def test_which_reader_answers_old_until_the_switch_exists(monkeypatch):
    """Today there is one reader, and the door says so."""
    from config import settings
    from engine_alpha import reader

    monkeypatch.delattr(settings, "TWO_EYES_READER_ENABLED", raising=False)
    assert reader.which_reader() == reader.READER_OLD
    monkeypatch.setattr(settings, "TWO_EYES_READER_ENABLED", False, raising=False)
    assert reader.which_reader() == reader.READER_OLD
    monkeypatch.setattr(settings, "TWO_EYES_READER_ENABLED", True, raising=False)
    assert reader.which_reader() == reader.READER_NEW


def test_the_scan_names_the_reader_it_ran():
    """The night says which reader read it, once.

    Every other caller can take a ``stamp`` sink, but the scan reads inside a
    process pool and its answers cross that boundary in a fixed shape, so a
    per-ticker name would move the worker contract the lane twins pin. One
    reading covers the night instead — which is only true if something
    actually writes it down.
    """
    import inspect

    from core.pipeline.screening import screener

    source = inspect.getsource(screener._evaluate_frames)
    assert "which_reader()" in source, (
        "nothing names the reader the scan ran; 'one reading names the whole "
        "night' is then a claim with no line behind it")


def test_the_door_makes_the_same_call_the_caller_used_to_make(monkeypatch):
    """No uninvited keywords.

    The old call sites passed four positional arguments and nothing else. The
    first version of this door always forwarded ``watch=`` and ``near_miss=``;
    the real chain accepts both, so production was unmoved, but three tests
    that exist to pin the production call shape died of TypeError. A door that
    rewrites the call is not a door.
    """
    from engine_alpha import evaluation, reader

    seen: list = []

    def four_arguments_only(ticker, df, spy_6m_return=0.0, breadth_pct=None):
        seen.append(ticker)
        return None

    monkeypatch.setattr(evaluation, "_evaluate_ticker", four_arguments_only)
    monkeypatch.setattr(evaluation, "_run_eval_chain", four_arguments_only)
    assert reader.evaluate_ticker("A", None, 0.0, None) is None
    assert reader.run_eval_chain("B", None, 0.0, None) is None
    assert seen == ["A", "B"]


def test_the_door_forwards_without_touching_the_answer(monkeypatch):
    """Whatever the engine returns is what the caller gets — no wrapping."""
    from engine_alpha import evaluation, reader

    sentinel = {"Ticker": "PROBE"}
    seen: dict = {}

    def fake(ticker, df, spy, breadth, watch=None):
        seen.update(ticker=ticker, spy=spy, breadth=breadth, watch=watch)
        return sentinel

    monkeypatch.setattr(evaluation, "_evaluate_ticker", fake)
    stamp: dict = {}
    got = reader.evaluate_ticker("PROBE", None, 1.5, 0.25, watch={}, stamp=stamp)
    assert got is sentinel
    assert seen == {"ticker": "PROBE", "spy": 1.5, "breadth": 0.25, "watch": {}}
    assert stamp == {"reader": "old"}
