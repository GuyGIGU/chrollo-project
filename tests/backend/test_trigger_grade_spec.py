"""Trigger-timing grader — the no-lookahead classifier contract (Task 6 spec).

Authored BEFORE its target (`domains.calibration.trigger_grade`, built in Task 11). It
auto-skips until that module exists, then holds the build to this contract:
three HONEST outcomes and a never-fired that is never silently collapsed into
"fired late". The engine reads only bars <= each session (the no-lookahead guard
lives in the replay seam, Task 11); this pure classifier must — given only the
fire date and the trigger date — never brand an absent read as late.
"""
import sys


from _paths import REPO_ROOT as ROOT
BACKEND_DIR = ROOT / "webapp" / "backend"
sys.path.insert(0, str(ROOT))
sys.path.insert(1, str(BACKEND_DIR))

# A plain import, not importorskip: the grader has landed, and a broken import
# path must fail this spec loudly instead of quietly skipping it.
from domains.calibration import trigger_grade  # noqa: E402
classify = trigger_grade.classify_fire_timing


def test_fired_before_the_trigger_is_at_or_before():
    assert classify("2026-04-14", "2026-04-16") == "at_or_before"


def test_fired_on_the_trigger_bar_is_at_or_before():
    # The breakout can land on the as-of bar itself — an on-trigger fire passes.
    assert classify("2026-04-16", "2026-04-16") == "at_or_before"


def test_fired_after_the_trigger_is_after():
    assert classify("2026-04-20", "2026-04-16") == "after"


def test_never_fired_is_its_own_outcome_not_late():
    # The load-bearing guard: no engine read is NOT "fired after" — that would
    # brand a setup the engine never elected as a late buy.
    assert classify(None, "2026-04-16") == "never"
