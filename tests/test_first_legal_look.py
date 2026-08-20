"""The first-legal-look battery: the walk never reads its own edge reserve.

``first_legal_look`` answers ONE question — on which session could this
Power-Play episode's anchor first have been seeded? The collector anchors on
the edge-TRIMMED frame, so a walk standing on session ``p`` reads the reaction
only through bar ``p - STRUCTURE_EDGE_SKIP_BARS``; the newest five sessions are
reserve. Every case below is hand-reasoned from that one invariant, and the
frames are SYNTHETIC (Beck P1) — expected positions come from the construction
arithmetic, never from running the function.

The two bias directions this battery exists for (2026-08-20 council review,
finding 3) are named cases: a confirming close printing INSIDE the reserve
(the walk cannot see it yet — the old read watched up to five sessions early)
and a reaction low deepening INSIDE the reserve (the walk has not met it yet —
the old read watched late, all the way to the final-AR wall). The oracle case
settles the arithmetic against ``collect_root_anchors`` itself rather than
against a restatement of it.
"""
import numpy as np
import pandas as pd
import pytest

from config import settings
from engine_alpha.structure.box_primitives import collect_root_anchors
from engine_alpha.structure.power_play import first_legal_look, ticker_episodes

# ── the shared hand-reasoned pole ───────────────────────────────────────────
# pre   [0, 400)   : linear 40 -> 50
# pole  [400, 440) : linear 50 -> 100        peak at 439, High 100.5
# react [440, 455) : per-case (AR_MAX_BARS = 15 -> the window is 440..454)
# tail  [455, 476) : 96.5
# AR confirmation threshold = 100.5 * (1 - 0.05) = 95.475.
_PEAK, _J0, _J1, _N = 439, 440, 455, 476
_PEAK_HIGH = 100.5
_THR = _PEAK_HIGH * (1.0 - 0.05)


def _frame(reaction):
    """The pole frame with ``reaction`` = {bar: (Close, Low)} over 440..454;
    unspecified reaction bars rest at Close 96.5 / Low 96.0 (above the
    threshold, above any case's lows — inert)."""
    closes = np.empty(_N)
    closes[:400] = 40 + 10 * np.arange(400) / 399
    closes[400:440] = 50 + 50 * np.arange(40) / 39
    closes[440:] = 96.5
    lows = closes - 0.5
    lows[440:] = 96.0
    for bar, (close, low) in reaction.items():
        closes[bar], lows[bar] = close, low
    idx = pd.bdate_range("2024-06-03", periods=_N)
    return pd.DataFrame({"Open": closes, "High": closes + 0.5, "Low": lows,
                         "Close": closes, "Volume": 200_000.0}, index=idx)


def _episode(frame):
    eps = ticker_episodes("PP", frame, 0.90, 40)
    return next(e for e in eps if e["peak"] == _PEAK)


@pytest.fixture(autouse=True)
def _pin_the_arithmetics_basis():
    """Every hand-reasoned number below is derived from these three."""
    assert settings.STRUCTURE_EDGE_SKIP_BARS == 5
    assert settings.AR_MAX_BARS == 15
    assert settings.AR_MIN_DROP_PCT == 0.05


def test_a_confirming_close_inside_the_reserve_is_not_yet_visible():
    # The reaction low prints at bar 440 and the CONFIRMING close only at bar
    # 452. At clock 8 both age walls clear on session 452 — but on 452 the
    # walk reads through bar 447, where nothing has confirmed yet. The
    # confirmation is walk-visible on 457 (452 + skip), and that is the first
    # legal look. Indexing the prefix at p instead of p - skip answered 452:
    # five sessions EARLY, on a close the walk had not been shown.
    frame = _frame({440: (96.0, 90.0),      # deepest low, does NOT confirm
                    452: (95.0, 94.5)})     # confirms; low stays above 90.0
    ep = _episode(frame)
    assert ep["ar"] == 440 and ep["peak_high"] == pytest.approx(_PEAK_HIGH)
    assert frame["Close"].iloc[452] <= _THR < frame["Close"].iloc[440]
    assert first_legal_look(ep, 8, frame) == 457


def test_a_low_deepening_inside_the_reserve_is_not_yet_met():
    # Mirror image. Bar 440 confirms with a shallow low; the deeper FINAL low
    # prints at bar 451. At clock 8 the walk on session 452 reads through bar
    # 447, where the reaction low is still bar 440's — eight sessions old, the
    # wall clears, the anchor seeds. The deeper low at 451 is still inside the
    # reserve and resets nothing yet. Indexing at p met that low early and
    # answered 463 (the final-AR wall): eleven sessions LATE.
    frame = _frame({440: (95.0, 94.0),      # confirms, shallow running low
                    451: (96.5, 90.0)})     # the late, deeper FINAL AR
    ep = _episode(frame)
    assert ep["ar"] == 451
    assert first_legal_look(ep, 8, frame) == 452


def test_the_terminal_bound_waits_for_its_own_confirmation():
    # The confirming close prints on the LAST bar of the reaction window
    # (454), so the walk cannot see it before 459. The AR-age and climax-age
    # walls both clear on 452, and the old closed-form bound stopped there —
    # returning a session on which the reaction had not confirmed at all.
    frame = _frame({440: (97.0, 90.0),      # deepest low, does NOT confirm
                    454: (95.0, 94.5)})     # confirms on the window's last bar
    ep = _episode(frame)
    assert ep["ar"] == 440
    assert first_legal_look(ep, 8, frame) == 459   # 454 + skip


def test_the_default_clock_is_immune():
    # The divergence lives at the SHORT species clocks. At clock 20 the age
    # walls (464) already sit past the whole reaction window's reserve exit
    # (459), so reserve-visibility can never bind — the answer is the wall.
    frame = _frame({440: (96.0, 90.0), 452: (95.0, 94.5)})
    ep = _episode(frame)
    assert first_legal_look(ep, 20, frame) == 464   # max(440+24, 439+25)


def test_a_look_past_the_frame_is_pending():
    # Not-yet-watchable is a real answer, not an error: the caller compares
    # against len(df) and files the episode `pending`.
    frame = _frame({440: (95.0, 90.0)})
    ep = _episode(frame)
    assert first_legal_look(ep, 40, frame) >= len(frame)


@pytest.mark.parametrize("clock,reaction", [
    (8, {440: (96.0, 90.0), 452: (95.0, 94.5)}),    # confirms in the reserve
    (8, {440: (95.0, 94.0), 451: (96.5, 90.0)}),    # low deepens in the reserve
    (8, {440: (97.0, 90.0), 454: (95.0, 94.5)}),    # confirms on the last bar
    (20, {440: (96.0, 90.0), 452: (95.0, 94.5)}),   # the default clock
])
def test_the_answer_is_the_session_the_collector_actually_seeds(clock, reaction):
    # The oracle: instead of restating the walls, walk the REAL seeder over
    # the frame the pipeline would have handed it on each session (truncate to
    # the as-of, then drop the edge reserve) and find the first session on
    # which the episode's own climax is returned as an anchor. This is the
    # test that would have failed on the old arithmetic in every direction.
    frame = _frame(reaction)
    ep = _episode(frame)
    skip = settings.STRUCTURE_EDGE_SKIP_BARS

    def seeds(p):
        eval_df = frame.iloc[:p + 1].iloc[:-skip]
        return any(a[1] == _PEAK for a in collect_root_anchors(eval_df, clock))

    answer = first_legal_look(ep, clock, frame)
    assert seeds(answer)
    assert not any(seeds(p) for p in range(_J0, answer))
