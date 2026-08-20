"""Behaviour pins for the dark trend-terminal box gate.

``TREND_TERMINAL_BOX_GATE_ENABLED`` (operator ruling 2026-07-27, LIVN: *"we
can't start the anchor from the opposite direction of the trend if we are still
inside that trend"*) refuses a box that OPENS before the trend running into it
printed its climax — unless at least ``MIN_BASE_DAYS`` bars have printed since
that climax. It shipped with **no committed test** and a kill-by of 2026-08-31,
so the flip decision had no executable description of what the flag does.

These tests are BEHAVIOUR pins, not implementation mirrors, and they are built
in three layers:

1. **Flag OFF is provably inert.** The election is handed no floor at all, so the
   filtering block is unreachable; on a frame the gate demonstrably refuses, the
   flag-off read still elects the same box. This is the load-bearing assertion —
   the flag is dark and must stay dark until someone deliberately flips it.
2. **The gate's actual effect**, exercised at the seam the engine really uses
   (``validate_equilibrium(..., terminal_floor=...)``) with the real detectors on
   a synthetic frame, for a terminal that is already printed, one that is ahead
   but mature, and one that is ahead and still young (the LIVN case).
3. **The rule's own arithmetic** (``trend_terminal_legal_open``) and the floor it
   reads (``trend_terminal_floor``), including the edges: no covering segment, a
   still-running segment, an empty frame, a degenerate window, and a terminal the
   pivot set placed somewhere the eye would not.

Everything is built synthetically — no cache, no archive, no network.

Related record: docs/decisions.md 2026-07-27 (the ruling) and 2026-08-14 (the
DO-NOT-FLIP corroboration + the two-part box-blind defect); docs/flag_ledger.md
row ``TREND_TERMINAL_BOX_GATE_ENABLED``.
"""
from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pandas as pd

from config import settings
from engine_alpha.structure.box_primitives import (
    backext_shared_rail,
    collect_zigzag_candidates,
    trend_terminal_legal_open,
)
from engine_alpha.structure.bricks import RootSwing, validate_equilibrium
from engine_alpha.structure.market_structure import TrendFloor, trend_terminal_floor
from engine_alpha.structure.narrative import read_structure

_FLAG = "TREND_TERMINAL_BOX_GATE_ENABLED"


# ── Frame + floor builders ───────────────────────────────────────────────────
def _ohlc_from_closes(closes, *, band=1.0, volume=1000.0):
    return pd.DataFrame({
        "Open": list(closes),
        "High": [c + band for c in closes],
        "Low": [c - band for c in closes],
        "Close": list(closes),
        "Volume": [volume] * len(closes),
    })


def _worked_frame():
    """A one-way leg crashing into a genuinely worked 100/110 range.

    The same construction test_bricks uses for the pair cascade: the election
    returns a box at df bar 6, and a SECOND valid framing exists at df bar 10 —
    which is what lets the back-extension pin below say something real.
    """
    crash = [120, 118, 140, 120, 110, 104]
    worked = [101, 103, 105, 107, 109, 107, 105, 103] * 4
    return _ohlc_from_closes(crash + worked)


def _root():
    return RootSwing("BC", 0, 1, 141.0, 100.0, 0.29, 1)


_UNGATED_BOX = (6, 110.0, 100.0)          # (start_bar, R, S) with no gate at all


def _ident(box):
    if box is None:
        return None
    return (int(box.start_bar), float(box.R), float(box.S))


def _floor(n, *, terminal_bar, price=np.nan, direction=0):
    """A TrendFloor whose every bar is covered by one confirmed segment."""
    return TrendFloor(np.full(n, terminal_bar, dtype=int),
                      np.full(n, float(price), dtype=float),
                      np.full(n, direction, dtype=int))


def _seg(*, start_bar, end_bar, terminal_bar, terminal_price=100.0, direction=1):
    return {
        "start_bar": start_bar, "end_bar": end_bar,
        "terminal_bar": terminal_bar, "terminal_price": terminal_price,
        "direction": direction,
    }


# ── Layer 1: flag OFF is inert ───────────────────────────────────────────────
def test_flag_is_dark_in_the_committed_config():
    # The gate is UNRULED (docs/decisions.md 2026-08-14 corroborates the
    # 2026-07-28 DO-NOT-FLIP). Flipping it is a deliberate, evidenced act — this
    # pin exists so it can never happen as a side effect of another edit.
    assert getattr(settings, _FLAG) is False


def test_a_flip_rotates_the_frozen_engine_config_version():
    # The flag is engine identity: turning it on changes which boxes exist, so
    # the archive must partition on it rather than silently mix two populations.
    from engine_alpha.freeze.manifest import collect_manifest, manifest_hash

    manifest = collect_manifest()
    assert manifest[_FLAG] is False
    dark = manifest_hash()

    from tools.replay import flag_capture
    with flag_capture(**{_FLAG: True}):
        assert collect_manifest()[_FLAG] is True
        assert manifest_hash() != dark
    assert manifest_hash() == dark          # restored


class _RecordingBricks:
    """Scripted brick provider that records the kwargs the spine hands it.

    Mirrors test_narrative's ``_Bricks`` contract but accepts ``**kwargs`` on
    the election so it cannot pin an arity: the question here is only WHICH
    kwargs the spine chose to pass.
    """

    def __init__(self):
        self.equilibrium_kwargs = None

    def find_root_swing(self, df, search_from_bar, atr):
        return None if search_from_bar > 0 else SimpleNamespace(
            climax_bar=0, ar_bar=1, R=110.0, S=100.0, kind="BC")

    def validate_equilibrium(self, df, root, atr, **kwargs):
        self.equilibrium_kwargs = dict(kwargs)
        return SimpleNamespace(S=100.0, R=110.0, start_bar=1, box_width=0.10)

    def find_spring(self, df, box, atr):
        return None

    def find_inner_box(self, df, box, atr):
        return None

    def find_lps(self, df, box, atr, **kwargs):
        return SimpleNamespace(start_bar=20)

    def cause_maturity(self, df, box, atr, lps=None):
        return SimpleNamespace(matured=True, bridge_validated=True,
                               pre_box_trend="", box_trend="",
                               lps_tightness_ratio=0.0)

    def resolve_phase_a(self, df, root, box, atr, terminal_floor=None):
        return root.climax_bar, root.ar_bar


def test_flag_off_hands_the_election_no_terminal_floor(monkeypatch):
    # The gate lives entirely inside `if terminal_floor is not None` — flag off
    # means the kwarg is not passed AT ALL, so the candidate list cannot be
    # touched and injected fakes without the parameter keep working.
    monkeypatch.setattr(settings, _FLAG, False)
    bricks = _RecordingBricks()

    read_structure(_worked_frame(), 1.0, bricks=bricks)

    assert bricks.equilibrium_kwargs == {}


def test_flag_on_hands_the_election_the_frames_own_floor(monkeypatch):
    monkeypatch.setattr(settings, _FLAG, True)
    df = _worked_frame()
    bricks = _RecordingBricks()

    read_structure(df, 1.0, bricks=bricks)

    handed = bricks.equilibrium_kwargs["terminal_floor"]
    expected = trend_terminal_floor(df)
    assert len(handed.bar) == len(df)
    assert np.array_equal(handed.bar, expected.bar)


def test_flag_off_still_elects_the_box_the_gate_would_refuse():
    # THE assertion. The frame below is one the gate demonstrably kills; with no
    # floor the election is byte-identical to the ungated read, and passing an
    # explicit None is the same thing again (the live default).
    df, root = _worked_frame(), _root()
    refusing = _floor(len(df), terminal_bar=len(df) - 1)

    assert _ident(validate_equilibrium(df, root, 1.0)) == _UNGATED_BOX
    assert _ident(validate_equilibrium(df, root, 1.0, terminal_floor=None)) == _UNGATED_BOX
    assert validate_equilibrium(df, root, 1.0, terminal_floor=refusing) is None


def test_the_floor_is_pure_so_phase_as_lazy_read_cannot_diverge(monkeypatch):
    # Flag ON computes the floor once and hands it to BOTH the election and
    # Phase A; flag OFF lets Phase A's polarity resolver compute its own inside
    # the guard. That is only safe because the floor is a pure function of the
    # frame — pinned here so the eager/lazy split can never become a reading
    # difference.
    df = _worked_frame()
    first, second = trend_terminal_floor(df), trend_terminal_floor(df)

    assert np.array_equal(first.bar, second.bar)
    assert np.array_equal(first.direction, second.direction)


# ── Layer 2: the gate's actual effect on a real election ─────────────────────
def test_gate_keeps_a_box_whose_trend_already_printed_its_extreme():
    # The ordinary legal case: the climax is behind the box open, so the base is
    # describing a trend that already ended. Equality is legal too — that is the
    # handover bar the old trend still owns (the MATX case in the docstring).
    df, root = _worked_frame(), _root()
    open_bar = _UNGATED_BOX[0]

    for terminal in (0, open_bar - 1, open_bar):
        box = validate_equilibrium(df, root, 1.0,
                                   terminal_floor=_floor(len(df), terminal_bar=terminal))
        assert _ident(box) == _UNGATED_BOX, f"terminal_bar={terminal} should be legal"


def test_gate_refuses_a_box_that_opens_inside_a_still_young_correction():
    # The LIVN case the ruling was written for: the trend tops INSIDE the box and
    # too few bars have printed since for what followed to be a base at all.
    df, root = _worked_frame(), _root()
    young = len(df) - settings.MIN_BASE_DAYS + 1     # one bar short of maturity
    assert young > _UNGATED_BOX[0], "scenario requires the climax inside the box"

    assert validate_equilibrium(df, root, 1.0,
                                terminal_floor=_floor(len(df), terminal_bar=young)) is None


def test_gate_keeps_a_box_whose_post_climax_base_has_matured():
    # The PXS case: the climax also lands inside the box, but a real base has
    # printed since — MIN_BASE_DAYS bars exactly is enough, one fewer is not.
    df, root = _worked_frame(), _root()
    mature = len(df) - settings.MIN_BASE_DAYS
    assert mature > _UNGATED_BOX[0], "scenario requires the climax inside the box"

    kept = validate_equilibrium(df, root, 1.0,
                                terminal_floor=_floor(len(df), terminal_bar=mature))
    lost = validate_equilibrium(df, root, 1.0,
                                terminal_floor=_floor(len(df), terminal_bar=mature + 1))
    assert _ident(kept) == _UNGATED_BOX
    assert lost is None


def test_gate_ignores_the_terminals_price_maturity_is_the_whole_test():
    # Overshoot MAGNITUDE is Tested-DEAD (falsified 3x, decisions.md 2026-07-27):
    # the operator accepts boxes whose trend ran 101% of a box height past R and
    # rejects one at 20.6%. Only `bar` may move the verdict — the same terminal
    # bar at a wildly different terminal price must give the same answer.
    df, root = _worked_frame(), _root()
    mature = len(df) - settings.MIN_BASE_DAYS

    for price in (0.01, 100.0, 1_000_000.0, np.nan):
        box = validate_equilibrium(
            df, root, 1.0, terminal_floor=_floor(len(df), terminal_bar=mature, price=price))
        assert _ident(box) == _UNGATED_BOX, f"terminal_price={price} moved the verdict"


def test_gate_judges_the_back_extended_open_not_the_raw_candidate_start():
    # This frame carries two valid framings whose RAW starts differ (df 6 and
    # df 10) but which back-extend to the SAME shared-rail pivot (df 6). The gate
    # is defined on the bar that actually becomes box.start_bar, so a floor that
    # is legal at 10 and refusing at 6 must kill BOTH — judging the raw start
    # would have let the second framing through.
    df, root = _worked_frame(), _root()
    eval_df = df.iloc[:-settings.STRUCTURE_EDGE_SKIP_BARS]
    eq_df = eval_df.iloc[root.ar_bar:]
    raw_to_ext = {
        int(c[9]) + root.ar_bar:
            int(backext_shared_rail(eq_df, float(c[1]), float(c[2]), int(c[9]), 1.0))
            + root.ar_bar
        for c in collect_zigzag_candidates(eq_df, len(df) - root.ar_bar, 1.0,
                                           enforce_traversal=True)
    }
    assert raw_to_ext == {6: 6, 10: 6}, "frame no longer carries the back-extending pair"

    bars = np.full(len(df), -1, dtype=int)
    bars[:10] = len(df) - 1                  # refusing at 6, legal at 10
    partial = TrendFloor(bars, np.full(len(df), np.nan), np.zeros(len(df), dtype=int))

    assert validate_equilibrium(df, root, 1.0, terminal_floor=partial) is None


def test_gate_leaves_uncovered_bars_alone():
    # bar == -1 means no confirmed segment covers the open: there is no trend
    # there to still be inside of, so there is nothing to refuse.
    df, root = _worked_frame(), _root()

    box = validate_equilibrium(df, root, 1.0,
                               terminal_floor=_floor(len(df), terminal_bar=-1))
    assert _ident(box) == _UNGATED_BOX


# ── Layer 3a: the rule's arithmetic (trend_terminal_legal_open) ───────────────
def test_legality_is_offset_rebased_onto_the_roots_ar_bar():
    # Box bars are window-relative; the floor is df-positional. The offset IS
    # root.ar_bar, so window bar 0 asks about df bar == offset and never earlier
    # — the chronological invariant ar_bar <= box.start_bar in the gate's own
    # arithmetic (decisions.md 2026-08-14).
    n, offset = 60, 12
    bars = np.full(n, -1, dtype=int)
    bars[offset] = n - 1                     # refusing, exactly at the AR bar
    floor = TrendFloor(bars, np.full(n, np.nan), np.zeros(n, dtype=int))

    legal = trend_terminal_legal_open(floor, offset)
    assert legal(0) is False                 # window 0 -> df offset: the refusing bar
    assert legal(1) is True                  # window 1 -> df offset+1: uncovered


def test_a_box_opening_before_its_trend_end_is_judged_on_maturity_alone():
    # "The box opens BEFORE the marked trend end" is NOT an automatic refusal —
    # it is the branch where the maturity clock decides, and that clock runs from
    # the terminal to the FRAME'S RIGHT EDGE (len(bars) - terminal), not to the
    # box's own end.
    terminal, min_base = 20, int(settings.MIN_BASE_DAYS)
    just_short = trend_terminal_legal_open(
        _floor(terminal + min_base - 1, terminal_bar=terminal), 0)
    exactly_enough = trend_terminal_legal_open(
        _floor(terminal + min_base, terminal_bar=terminal), 0)

    assert just_short(5) is False            # box opens at 5, trend tops at 20
    assert exactly_enough(5) is True         # same box, one more bar of base


def test_already_printed_carries_a_box_that_maturity_could_never_save():
    # MUTATION-PINNED. The sibling test at Layer 2 asserts an already-printed
    # terminal keeps the box, but on that frame the terminal is early, so the
    # MATURITY clause is true as well and rescues the box on its own — deleting
    # the `bar >= term` clause outright left the suite green (verified
    # 2026-08-20 by three surviving mutants: `bar > term`, dropping the clause,
    # and `if False`).
    #
    # Here maturity CANNOT rescue anything: the trend tops late and too few bars
    # have printed since, so `(n - term) >= MIN_BASE_DAYS` is False everywhere.
    # The only thing that can make an open legal is that the trend had already
    # printed its extreme by then.
    n, min_base = 30, int(settings.MIN_BASE_DAYS)
    terminal = n - min_base + 5                     # maturity: 25 - 20 < 20
    legal = trend_terminal_legal_open(_floor(n, terminal_bar=terminal), 0)

    assert (n - terminal) < min_base, "the frame must make maturity impossible"

    # EQUALITY is the case that bites: the handover bar the old trend still owns
    # (the MATX case in the detector's docstring), which box_primitives calls
    # load-bearing — dropping it cost a pinned Guided-List hit.
    assert legal(terminal) is True
    assert legal(terminal + 5) is True              # strictly after: also legal
    assert legal(terminal - 1) is False             # one bar earlier: refused,
    #                                                 and maturity cannot save it


def test_bars_outside_the_floor_array_are_legal():
    # Nothing is known about them, so nothing may be refused on their account.
    floor = _floor(40, terminal_bar=39)
    legal = trend_terminal_legal_open(floor, 0)

    assert legal(-1) is True
    assert legal(40) is True
    assert legal(10_000) is True


def test_an_empty_floor_refuses_nothing():
    # The degenerate frame: zero-length arrays, every bar out of range.
    legal = trend_terminal_legal_open(_floor(0, terminal_bar=-1), 0)

    assert legal(0) is True
    assert legal(50) is True


# ── Layer 3b: the floor itself (trend_terminal_floor) ────────────────────────
def test_floor_of_an_empty_or_missing_frame_is_empty():
    for df in (None, pd.DataFrame({"High": [], "Low": [], "Close": []})):
        floor = trend_terminal_floor(df)
        assert len(floor.bar) == 0
        assert len(floor.price) == 0 and len(floor.direction) == 0


def test_no_confirmed_segment_leaves_every_bar_uncovered():
    df = _worked_frame()
    floor = trend_terminal_floor(df, segments=[])

    assert np.array_equal(floor.bar, np.full(len(df), -1))


def test_a_still_running_segment_never_vetoes():
    # A trend with no CHoCH has not proven it topped; its "terminal" is only the
    # highest high so far. Vetoing on it cost a pinned Guided-List hit (VIK).
    # The worked frame's OWN segmentation is exactly this case, so assert both
    # the injected form and the real read.
    df = _worked_frame()
    running = trend_terminal_floor(df, segments=[
        _seg(start_bar=0, end_bar=None, terminal_bar=len(df) - 1)])

    assert np.array_equal(running.bar, np.full(len(df), -1))
    assert np.array_equal(trend_terminal_floor(df).bar, np.full(len(df), -1))


def test_the_cause_trend_owns_the_shared_handover_bar():
    # Segments overlap by one leg: an uptrend runs to its CHoCH, which IS the
    # next downtrend's start. First write wins, so the EARLIER (cause) trend owns
    # bar 30 — letting the later one win vetoes a base at the very top where it
    # belongs (measured 2026-07-27: 6 pinned Guided-List hits broke).
    df = _ohlc_from_closes([100.0] * 60)
    floor = trend_terminal_floor(df, segments=[
        _seg(start_bar=0, end_bar=30, terminal_bar=25, direction=1),
        _seg(start_bar=30, end_bar=50, terminal_bar=45, direction=-1),
    ])

    assert floor.bar[29] == 25
    assert floor.bar[30] == 25               # handover bar: the CAUSE trend's
    assert floor.bar[31] == 45
    assert floor.direction[30] == 1
    assert floor.bar[51] == -1               # past both segments: uncovered


def test_degenerate_and_out_of_frame_windows_are_skipped():
    df = _ohlc_from_closes([100.0] * 40)
    floor = trend_terminal_floor(df, segments=[
        _seg(start_bar=20, end_bar=10, terminal_bar=15),        # inverted
        _seg(start_bar=100, end_bar=200, terminal_bar=150),     # past the frame
        _seg(start_bar=-5, end_bar=5, terminal_bar=3),          # clipped at 0
    ])

    assert np.array_equal(floor.bar[:6], np.full(6, 3))
    assert np.array_equal(floor.bar[6:], np.full(34, -1))


def test_the_floor_reports_the_segments_terminal_verbatim():
    # Half (a) of the box-blind defect (decisions.md 2026-08-14): where the
    # operator's trend end is not in the pivot set, `segment_trends` hands over a
    # terminal drawn from a later in-base upthrust instead. The floor does NOT
    # re-read price to sanity-check it — it copies the reported bar — so the
    # gate is only ever as good as the pivot set it is handed. Pinned so the
    # limitation is visible in the suite rather than only in the ledger.
    df = _ohlc_from_closes([100.0] * 60)
    df.loc[10, "High"] = 500.0               # the obvious extreme, NOT the terminal
    floor = trend_terminal_floor(df, segments=[
        _seg(start_bar=0, end_bar=40, terminal_bar=35, terminal_price=101.0)])

    assert floor.bar[0] == 35
    assert float(floor.price[0]) == 101.0


def test_the_real_election_never_opens_before_its_root():
    # The invariant the gate's offset arithmetic rests on, asserted on a real
    # election both with and without a floor: the elected box opens at or after
    # the root's AR bar, so the gate is never asked about a bar before it.
    df, root = _worked_frame(), _root()

    ungated = validate_equilibrium(df, root, 1.0)
    gated = validate_equilibrium(df, root, 1.0, terminal_floor=trend_terminal_floor(df))
    for box in (ungated, gated):
        assert box is not None
        assert box.start_bar >= root.ar_bar
