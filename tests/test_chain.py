"""The chain coordinator's battery (story-chain program Task 6).

Two halves, on the narrative suite's own pattern: the displacement-root
ARITHMETIC on small real frames (as-of reserve, the house AR law, honest
refusals), and the coordinator's ORCHESTRATION with fake bricks (one root
served once, delegation, the inheritance law recording the raw cause
verdict, the frozen parent's immutability). The real-bricks end-to-end
acceptance runs against the operator's ruled specimens in the wall fixture
(program Task 3) — not against synthetic tape.
"""
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from config import settings
from engine_alpha.structure.chain import (
    CHAIN_STATES,
    ChainRead,
    FrozenParent,
    displacement_root,
    freeze_parent,
    read_chain,
)


def _frame(closes, *, band=1.0, start="2025-01-02"):
    idx = pd.bdate_range(start, periods=len(closes))
    c = np.asarray(closes, dtype=float)
    return pd.DataFrame({"Open": c, "High": c + band, "Low": c - band,
                         "Close": c, "Volume": np.full(len(c), 1e6)}, index=idx)


def _chain_a_frame():
    """Resolution at bar 10, run to a peak of ~131 high at bar 18, a
    confirmed reaction into ~121 low at bar 24, then a flat child shelf,
    then the 5-bar edge reserve."""
    closes = ([100.0] * 10                       # parent era
              + list(np.linspace(112, 130, 9))   # bar 10 = resolution, run to 130
              + [128, 126, 124, 123, 122, 123]   # reaction: close 122 <= 131*0.95
              + [124.0] * 10                     # the child shelf
              + [124.0] * 5)                     # the edge reserve
    return _frame(closes)


def _parent(**over):
    values = dict(R=110.0, S=100.0, base_len=60, start_date="2024-10-01",
                  resolution_date="2025-01-16", kind="breakout_up")
    values.update(over)
    return FrozenParent(**values)


# --- freeze_parent ----------------------------------------------------------

def test_freeze_parent_records_dates_and_prices_verbatim():
    df = _frame([100.0] * 30)
    s = SimpleNamespace(R=110.0, S=100.0, phase_b_start_bar=3,
                        box=SimpleNamespace(base_len=27))
    fp = freeze_parent(df, s, resolution_bar=20, kind="breakout_up")
    assert (fp.R, fp.S, fp.base_len) == (110.0, 100.0, 27)
    assert fp.start_date == str(df.index[3].date())
    assert fp.resolution_date == str(df.index[20].date())
    with pytest.raises(Exception):
        fp.R = 111.0                             # frozen: recorded constants


def test_freeze_parent_refuses_an_unknown_kind():
    df = _frame([100.0] * 10)
    s = SimpleNamespace(R=1.0, S=0.0, phase_b_start_bar=0, box=SimpleNamespace())
    with pytest.raises(ValueError):
        freeze_parent(df, s, 5, "sideways_drift")


# --- displacement_root ------------------------------------------------------

def test_displacement_root_reads_the_run_peak_and_confirmed_reaction():
    df = _chain_a_frame()
    parent = _parent(resolution_date=str(df.index[10].date()))
    root = displacement_root(df, parent)
    assert root is not None
    assert root.kind == "BC"
    # the peak is the highest visible high after the resolution (bar 18)
    assert root.climax_bar == 18
    assert root.R == pytest.approx(131.0)        # close 130 + band 1
    # the reaction low is the argmin within the AR window (close 122 bar)
    assert root.ar_bar == 23
    assert root.S == pytest.approx(121.0)
    assert 0 < root.reaction_pct < 0.10


def test_displacement_root_honors_the_edge_reserve():
    # Push a HIGHER peak into the newest `skip` bars: the walk must not see
    # it — the visible peak stays bar 18 (prefix truth, never hindsight).
    df = _chain_a_frame()
    df.iloc[-2, df.columns.get_loc("High")] = 200.0
    parent = _parent(resolution_date=str(df.index[10].date()))
    root = displacement_root(df, parent)
    assert root is not None and root.climax_bar == 18


def test_displacement_root_refuses_honestly():
    parent_missing = _parent(resolution_date="1999-01-04")
    assert displacement_root(_chain_a_frame(), parent_missing) is None
    # a run still rising (no confirmed reaction) is not yet a child
    rising = _frame([100.0] * 10 + list(np.linspace(112, 140, 25)))
    parent = _parent(resolution_date=str(rising.index[10].date()))
    assert displacement_root(rising, parent) is None
    # a "run" that never left the parent's ceiling
    flat = _frame([100.0] * 10 + [105.0] * 25)
    parent2 = _parent(resolution_date=str(flat.index[10].date()))
    assert displacement_root(flat, parent2) is None


# --- read_chain orchestration (fake bricks) ---------------------------------

class _FakeBricks:
    """Scripted 'real' provider handed to the chain's delegating wrapper."""

    def __init__(self, box=None, lps=None, cause_matured=False):
        self.box = box
        self.lps = lps
        self.cause_matured = cause_matured
        self.seen_min_base_days = None

    def validate_equilibrium(self, df, root, atr, **kw):
        self.seen_min_base_days = settings.MIN_BASE_DAYS
        return self.box

    def find_spring(self, df, box, atr):
        return None

    def find_inner_box(self, df, box, atr):
        return None

    def find_lps(self, df, box, atr, **kw):
        return self.lps

    def resolve_phase_a(self, df, root, box, atr, terminal_floor=None):
        return root.climax_bar, root.ar_bar

    def cause_maturity(self, df, box, atr, lps=None):
        return SimpleNamespace(matured=self.cause_matured,
                               bridge_validated=False, pre_box_trend="up",
                               box_trend="up", lps_tightness_ratio=1.2)


def _elected_fakes():
    box = SimpleNamespace(S=121.0, R=131.0, start_bar=23, box_width=0.08,
                          base_len=15, r_touches=2, s_touches=2,
                          r_anchor_bar=23, s_anchor_bar=24, breach_days=0)
    lps = SimpleNamespace(start_bar=30, low_bar=31, length=4, offset=0)
    return _FakeBricks(box=box, lps=lps)


def test_read_chain_composes_and_records_the_raw_cause():
    df = _chain_a_frame()
    parent = _parent(resolution_date=str(df.index[10].date()))
    out = read_chain(df, 1.0, parent, bricks=_elected_fakes())
    assert out.state == "child_elected" and out.state in CHAIN_STATES
    assert out.child is not None
    assert out.parent is parent                   # the frozen object, untouched
    assert out.displacement["run_peak_bar"] == 18
    assert out.displacement["separation"] == pytest.approx(121.0 - 110.0)
    # the veto was satisfied by INHERITANCE, and the raw verdict is recorded
    assert out.child_cause_raw is not None
    assert out.child_cause_raw["matured"] is False


def test_read_chain_refusal_states_are_honest():
    df = _chain_a_frame()
    parent = _parent(resolution_date=str(df.index[10].date()))
    refused = read_chain(df, 1.0, parent, bricks=_FakeBricks(box=None))
    assert refused.state == "child_refused" and refused.child is None
    missing = read_chain(df, 1.0, _parent(resolution_date="1999-01-04"),
                         bricks=_FakeBricks())
    assert missing.state == "no_displacement_root"
    assert missing.displacement is None and missing.child_cause_raw is None


def _chain_b_frame():
    """Undercut at bar 10, shakeout low 94 at bar 12, staircase recovery to a
    peak of 107 at bar 22, then a CONFIRMED contracting pullback (low 100 at
    bar 25 — below the old floor is legal: the tactical long), a shelf, and
    the reserve."""
    return _frame([105.0] * 10 + [97.0, 96.0, 95.0]
                  + [98.0, 100.0, 101.0, 102.0] + [100.0, 98.5, 100.0]
                  + [102.0, 104.0, 106.0, 106.0]          # peak 107 @ bar 22
                  + [103.0, 101.0, 102.0, 103.0]          # the pullback
                  + [103.0] * 3 + [103.0] * 5)


def test_shakeout_chain_reads_through_the_recovery():
    df = _chain_b_frame()
    parent = _parent(kind="shakeout_down", S=100.0,
                     resolution_date=str(df.index[10].date()))
    out = read_chain(df, 2.0, parent, bricks=_elected_fakes())
    assert out.state == "child_elected"
    assert out.recovery is not None
    assert out.recovery["character"] == "staircase"
    assert out.displacement["run_peak_bar"] == 22          # roots on the recovery high
    assert out.displacement["reaction_low_bar"] == 25
    assert out.displacement["reaction_low"] == pytest.approx(100.0)
    # below the old ceiling — the tactical geometry is legal by decree
    assert out.displacement["separation"] < 0


def test_shakeout_with_no_recovery_states_it():
    df = _frame([105.0] * 10 + [95.0, 93.0, 92.0] + [92.5] * 8 + [92.5] * 5)
    parent = _parent(kind="shakeout_down", S=100.0,
                     resolution_date=str(df.index[10].date()))
    out = read_chain(df, 2.0, parent, bricks=_FakeBricks())
    assert out.state == "no_recovery"
    assert out.recovery["character"] == "none"
    assert out.child is None and out.displacement is None


def test_read_chain_refuses_an_unknown_kind_loudly():
    df = _chain_a_frame()
    with pytest.raises(ValueError):
        read_chain(df, 1.0, _parent(kind="sideways_drift"))


def test_window_preset_enters_through_the_one_override_and_restores():
    df = _chain_a_frame()
    parent = _parent(resolution_date=str(df.index[10].date()))
    fakes = _elected_fakes()
    before = settings.MIN_BASE_DAYS
    read_chain(df, 1.0, parent, bricks=fakes,
               window_preset={"MIN_BASE_DAYS": 7})
    assert fakes.seen_min_base_days == 7          # the read saw the preset
    assert settings.MIN_BASE_DAYS == before       # and it was restored
