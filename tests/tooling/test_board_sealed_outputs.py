"""The three boards refuse a sealed folder before they read a chart (council review 2026-10-09, finding 9; EC-14).

grade_probe (`--json`, `--pages`), core_board (`--pages`) and walk_board (`--pages`) made their folder and wrote
their pages straight to the path typed, so one slip (`--pages docs/marks`) overwrote his drawings or the ratchet's
pinned results in place. Their four siblings on the branch guard it; now these do too, and first: the reading
functions below explode if they are reached, so a refusal that comes after the reading fails here.
"""
from __future__ import annotations

import sys

import pytest

from _paths import REPO_ROOT

SEALED = [str(REPO_ROOT / "docs" / "marks"), str(REPO_ROOT / "tests" / "baselines" / "pages"),
          str(REPO_ROOT / "docs" / "marks" / "guided_list_2026-07.json")]


def _never(*args, **kwargs):
    raise AssertionError("the board read a chart before it checked where it writes")


@pytest.mark.parametrize("flag", ["--pages", "--json"])
@pytest.mark.parametrize("target", SEALED)
def test_grade_probe_refuses_a_sealed_target_before_reading(monkeypatch, flag, target):
    from tools.calibration import grade_probe

    monkeypatch.setattr(grade_probe, "collect", _never)
    monkeypatch.setattr(sys, "argv", ["grade_probe", flag, target])
    with pytest.raises(ValueError, match="sealed"):
        grade_probe.main()


@pytest.mark.parametrize("module", ["core_board", "walk_board"])
@pytest.mark.parametrize("target", SEALED)
def test_the_boards_refuse_a_sealed_pages_folder_before_reading(monkeypatch, module, target):
    import importlib

    board = importlib.import_module(f"tools.calibration.{module}")
    monkeypatch.setattr(board, "load_corpus", _never)
    monkeypatch.setattr(board, "run_board", _never)
    monkeypatch.setattr(sys, "argv", [module, "--pages", target])
    with pytest.raises(ValueError, match="sealed"):
        board.main()
