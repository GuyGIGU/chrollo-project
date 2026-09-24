"""Build step 6 of the final method (docs/final_method_2026-09.md point 9): the 15-day floor from the first anchor.

His answers: "Lets go with 15 days" and "15 for a base minimum yes". The box's AGE counts from its first rail anchor
as day 1, not from the root's reaction bar where MIN_BASE_DAYS counts today; a younger box is forming, never elected.
One default-off switch, BASE_AGE_FROM_ANCHOR_ENABLED; flag-off byte-identical.
"""
import inspect
from collections import Counter
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from config import settings
from engine_alpha.freeze.manifest import ENGINE_SETTINGS_KEYS
from engine_alpha.structure.narrative import bricks
from engine_alpha.structure.narrative import Structure, read_structure

N = 60


def _frame(n=N):
    idx = pd.bdate_range("2026-01-05", periods=n)
    close = 100.0 + np.sin(np.arange(n) / 3.0)
    return pd.DataFrame({"Open": close, "High": close + 0.5, "Low": close - 0.5, "Close": close,
                         "Volume": 1e6}, index=idx)


def _box(r_age, s_age, start_age=None):
    """A box whose anchors sit r_age and s_age trading days back on an N-day frame (the anchor bar is day 1)."""
    return SimpleNamespace(S=100.0, R=110.0, start_bar=N - (start_age or max(r_age, s_age)), box_width=0.10,
                           r_anchor_bar=N - r_age, s_anchor_bar=N - s_age)


class _Bricks:
    """One scripted root, its box, no spring, an LPS: the spine's happy path (the fake of tests/engine/test_narrative.py)."""

    def __init__(self, box, inner=None):
        self.box, self.inner = box, inner

    def find_root_swing(self, df, search_from_bar, atr):
        return SimpleNamespace(climax_bar=10, ar_bar=20, R=110.0, S=100.0) if search_from_bar <= 10 else None

    def validate_equilibrium(self, df, root, atr, trace=None):
        return self.box

    def find_spring(self, df, box, atr):
        return None

    def find_lps(self, df, box, atr, *, diagnose=False, start_floor_bar=None):
        lps = SimpleNamespace(start_bar=55)
        return (lps, Counter()) if diagnose else lps

    def cause_maturity(self, df, box, atr, lps=None):
        return SimpleNamespace(matured=True, bridge_validated=True, pre_box_trend="", box_trend="",
                               lps_tightness_ratio=0.0)

    def resolve_phase_a(self, df, root, box, atr, terminal_floor=None):
        return root.climax_bar, root.ar_bar

    def find_inner_box(self, df, box, atr):
        return self.inner


@pytest.fixture
def floor_on(monkeypatch):
    monkeypatch.setattr(settings, "BASE_AGE_FROM_ANCHOR_ENABLED", True)


def test_the_floor_is_dark_and_on_the_manifest():
    assert settings.BASE_AGE_FROM_ANCHOR_ENABLED is False
    assert settings.BASE_AGE_MIN_DAYS == 15, "his number"
    assert {"BASE_AGE_FROM_ANCHOR_ENABLED", "BASE_AGE_MIN_DAYS"} <= set(ENGINE_SETTINGS_KEYS)


# ── the seed clock yields (bricks) ───────────────────────────────────────────

def test_the_seed_clock_yields_to_the_floor_less_the_edge_reserve(monkeypatch):
    from engine_alpha.structure.context.htf import window_override

    assert bricks._seed_clock() == settings.MIN_BASE_DAYS == 20, "flag-off: today's clock"
    monkeypatch.setattr(settings, "BASE_AGE_FROM_ANCHOR_ENABLED", True)
    assert bricks._seed_clock() == 10, "15 from the anchor, less the 5-day edge reserve"
    monkeypatch.setattr(settings, "STRUCTURE_EDGE_SKIP_BARS", 3)
    assert bricks._seed_clock() == 12, "the reserve is read, never assumed"
    monkeypatch.setattr(settings, "STRUCTURE_EDGE_SKIP_BARS", 5)
    with window_override({"MIN_BASE_DAYS": 8}):
        assert bricks._seed_clock() == 8, "never above a preset's own clock"


def test_the_root_walk_seeds_on_the_yielded_clock(monkeypatch):
    seen = []
    monkeypatch.setattr(bricks, "collect_root_anchors", lambda df, clock, *a, **k: seen.append(clock) or [])
    bricks.find_root_swing(_frame())
    monkeypatch.setattr(settings, "BASE_AGE_FROM_ANCHOR_ENABLED", True)
    bricks.find_root_swing(_frame())
    assert seen == [20, 10]


class _Reached(Exception):
    pass


def test_a_twelve_day_window_reaches_the_pair_election_only_under_the_floor(monkeypatch):
    def _spy(*_a, **_k):
        raise _Reached

    monkeypatch.setattr(bricks, "collect_zigzag_candidates", _spy)
    root = SimpleNamespace(climax_bar=5, ar_bar=13, R=110.0, S=100.0, kind="BC")
    df = _frame(30)          # df[:-5] holds 25 days; the reaction on day 13 leaves a 12-day window
    assert bricks.validate_equilibrium(df, root, 1.0) is None, "flag-off the 20-day clock refuses first"
    monkeypatch.setattr(settings, "BASE_AGE_FROM_ANCHOR_ENABLED", True)
    with pytest.raises(_Reached):
        bricks.validate_equilibrium(df, root, 1.0)


# ── the floor itself (the root walk) ─────────────────────────────────────────

def test_a_box_whose_first_anchor_is_14_days_old_is_forming_not_elected(monkeypatch):
    young = _Bricks(_box(14, 14, start_age=30))
    assert isinstance(read_structure(_frame(), 1.0, bricks=young), Structure), "flag-off: today's walk elects it"
    monkeypatch.setattr(settings, "BASE_AGE_FROM_ANCHOR_ENABLED", True)
    assert read_structure(_frame(), 1.0, bricks=young) is None, \
        "the box opens 30 days back, but its anchors are 14 days old: the age is the anchors'"


def test_the_anchor_bar_is_day_one_so_15_days_is_old_enough(floor_on):
    assert isinstance(read_structure(_frame(), 1.0, bricks=_Bricks(_box(15, 14))), Structure), \
        "the first anchor (R) is exactly 15 days old"


def test_the_age_counts_from_the_first_anchor_on_either_rail(floor_on):
    assert isinstance(read_structure(_frame(), 1.0, bricks=_Bricks(_box(20, 12))), Structure), "R first"
    assert isinstance(read_structure(_frame(), 1.0, bricks=_Bricks(_box(12, 20))), Structure), "S first"
    assert read_structure(_frame(), 1.0, bricks=_Bricks(_box(13, 14))) is None


def test_the_forming_box_is_narrated_in_the_walk_trace(floor_on):
    trace = []
    assert read_structure(_frame(), 1.0, bricks=_Bricks(_box(14, 14)), trace=trace) is None
    assert trace[0]["outcome"] == "forming" and trace[0]["forming"] == {"age": 14, "of": 15}


def test_a_young_mini_inside_an_old_parent_is_not_the_age(floor_on):
    inner = SimpleNamespace(S=104.0, R=108.0, start_bar=50, search_start_bar=48, box_width=0.04,
                            r_anchor_bar=52, s_anchor_bar=53)
    assert isinstance(read_structure(_frame(), 1.0, bricks=_Bricks(_box(30, 25), inner=inner)), Structure)


def test_the_floor_leaves_every_other_20_day_use_alone(floor_on):
    assert settings.MIN_BASE_DAYS == 20 and settings.PIP_MACRO_MIN_BASE_BARS == 20


# ── the evaluation ───────────────────────────────────────────────────────────

def test_the_fire_carries_its_age_only_under_the_floor(monkeypatch):
    """The real cascade (EC-17) on the committed shadow fixture: flag-off no key; flag-on the age of every fire that
    survives the floor, and that age is at least the floor."""
    from core.pipeline.screening.screener import _evaluate_ticker
    from engine_alpha.evaluation import EVAL_ERROR
    from tools.regression.shadow_diff import _load_fixture

    frames, scalars = _load_fixture()
    breadth = scalars.get("breadth_pct")
    spy, breadth = float(scalars.get("spy_6m_return", 0.0)), (float(breadth) if breadth is not None else None)
    checked = 0
    for ticker in scalars["tickers"]:
        df = frames.get(ticker)
        if df is None:
            continue
        off = _evaluate_ticker(ticker, df, spy, breadth)
        if off is None or off is EVAL_ERROR:
            continue
        assert "_base_age_from_anchor" not in off, ticker
        monkeypatch.setattr(settings, "BASE_AGE_FROM_ANCHOR_ENABLED", True)
        on = _evaluate_ticker(ticker, df, spy, breadth)
        monkeypatch.setattr(settings, "BASE_AGE_FROM_ANCHOR_ENABLED", False)
        if on is None or on is EVAL_ERROR:
            continue
        assert isinstance(on["_base_age_from_anchor"], int), ticker
        assert on["_base_age_from_anchor"] >= settings.BASE_AGE_MIN_DAYS, ticker
        checked += 1
        if checked == 3:
            break
    assert checked, "no fixture fire survives the floor"
