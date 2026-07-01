"""End-to-end regression-guard test wired into pytest/CI.

The headline shadow-output guard (``tools.shadow_diff.check_baseline``) was
previously MANUAL-ONLY: CI ran compileall + pytest but never the drift guard,
so a change that silently altered a canonical screener output could pass CI.

This module runs the REAL guard end-to-end against the COMMITTED baseline and
frozen fixture, so any canonical-field drift fails the default pytest run (and
therefore CI). It is fully OFFLINE and deterministic: ``check_baseline`` reads
the committed ``tests/baselines/shadow_baseline.json`` and replays the frozen
``shadow_fixture.parquet`` through the per-ticker pipeline. No network, no live
archive DB, no parquet cache.

The sibling seed-recall guard (``core.archive.seed_recall``) is intentionally
NOT run here: its ``--check`` needs the archive SQLite DB and ``--fresh`` needs
the network, so it lives as a separate (network-annotated) CI step instead.
"""
from __future__ import annotations

import os

import pytest

# Import path (`from tools.shadow_diff import ...`) is already exercised by the
# existing suite (tests/test_guards.py, tests/test_scoring.py, etc.), so pytest's
# rootdir is on sys.path and this import resolves without extra bootstrapping.
from tools import shadow_diff

pytestmark = pytest.mark.regression


def test_shadow_baseline_and_fixture_are_committed():
    """The guard is meaningless if its inputs are missing.

    Fail LOUDLY (never skip) if the committed baseline or frozen fixture has
    gone missing -- a silent skip would let real drift sail through CI.
    """
    assert os.path.exists(shadow_diff._BASELINE_PATH), (
        f"Missing committed shadow baseline at {shadow_diff._BASELINE_PATH}; "
        "run `python -m tools.shadow_diff --capture` and commit it."
    )
    assert os.path.exists(shadow_diff._FIXTURE_PARQUET), (
        f"Missing frozen shadow fixture at {shadow_diff._FIXTURE_PARQUET}; "
        "run `python -m tools.shadow_diff --build-fixture` and commit it."
    )
    assert os.path.exists(shadow_diff._FIXTURE_SCALARS), (
        f"Missing frozen fixture scalars at {shadow_diff._FIXTURE_SCALARS}; "
        "run `python -m tools.shadow_diff --build-fixture` and commit it."
    )


def test_shadow_output_guard_no_drift():
    """Replay the frozen fixture through the live pipeline; assert NO drift.

    ``check_baseline()`` returns True iff every canonical output field for every
    frozen ticker (and the displayed ranking) matches the committed baseline.
    Offline + deterministic: it reads only committed files and runs the
    per-ticker pipeline in-memory.
    """
    assert shadow_diff.check_baseline() is True, (
        "Shadow-output guard drifted: a canonical screener output changed "
        "against the committed baseline. Re-run `python -m tools.shadow_diff "
        "--check` locally to see the exact ticker/field, then either fix the "
        "regression or, if the change is intended, re-capture the baseline."
    )
