"""The resistance-contraction ruled form (program Task 6; named by operator
ruling 2026-08-18): its truth table with every refusing leg distinguishable
(EC-27), the posture-derived behavior NAME, the two episode-stats keys under
the as-of discipline, and the dark default.

The form's EC-17 acceptance through the REAL cascade (a MAN-shaped frame
electing under the species flags) lands with the species battery (program
Task 10) — this file constrains the form and its substrate, not the cascade."""
import numpy as np
import pytest

from config import settings
from engine_alpha.structure.event_map import (
    episode_sequence_stats,
    read_rail_episodes_arrays,
    resistance_contraction_admission,
    resistance_contraction_label,
    story_admission,
)


def _stats(**over):
    base = {"n_failed_s": 0, "terminal_s_drift": False,
            "terminal_r_engagement": True, "terminal_r_posture": False}
    base.update(over)
    return base


# ── the truth table, one refusing leg at a time (EC-27) ─────────────────────

def test_the_form_admits_the_contraction_at_resistance():
    assert resistance_contraction_admission(_stats()) is True


@pytest.mark.parametrize("leg, refusal", [
    ("n_failed_s", 1),                  # the floor failed once
    ("terminal_s_drift", True),         # bleeding on the floor
    ("terminal_r_engagement", False),   # the right edge is not at the ceiling
])
def test_the_form_refuses_each_leg(leg, refusal):
    assert resistance_contraction_admission(_stats(**{leg: refusal})) is False


# ── the behavior NAME derives from the measured posture (ruling 2026-08-18) ──

def test_the_record_names_the_behavior_it_saw():
    # Last bar closes ABOVE the rail -> the post-breakout stance.
    above = _stats(terminal_r_posture=True)
    assert resistance_contraction_label(above) == "contracting above resistance"
    # Engaged at the rail's zone, close still below it -> pressing from below.
    at = _stats(terminal_r_posture=False)
    assert resistance_contraction_label(at) == "contracting at resistance"


def test_the_two_forms_are_distinct_judgments():
    # A textbook S-test admission (S+ S+ R^) with a failed S in its history
    # still reads for the S-test form but NOT the contraction form — and a
    # bare contraction at the ceiling reads for the contraction form but not
    # the S-test form. Two named rulings, one vocabulary.
    s_test_stats = _stats(n_completed_s=2, terminal_r_posture=True,
                          n_failed_s=1)
    assert story_admission(s_test_stats) is True
    assert resistance_contraction_admission(s_test_stats) is False
    hang_stats = _stats(n_completed_s=0, terminal_r_posture=False)
    assert story_admission(hang_stats) is False
    assert resistance_contraction_admission(hang_stats) is True


# ── the substrate: the two episode-stats keys out of the real reader ────────

def _contraction_arrays():
    """A hand-reasoned 12-bar window on rails R=100, S=90, ATR=2 (touch zone
    ±1.0, buffer ±1.0): three quiet mid-box bars; an S visit at bars 3-4
    whose CLOSES breach S−buf=89 (min close 88.0) and whose last in-zone
    close 88.0 sits under S — the reader's "failed" outcome; recovery; then
    the frame ends INSIDE an R-zone engagement (highs >= 99, closes below
    100) — an open terminal R episode, contracting at resistance. The failed
    episode's merge horizon (EPISODE_MAX_GAP_BARS=2 -> knowable at bar 7)
    prints inside the frame, so the as-of count sees it."""
    highs = np.array([95, 95, 95, 91.0, 90, 93, 95, 96, 99.5, 99.5, 99.6, 99.4])
    lows = np.array([93, 93, 93, 88.5, 87.5, 92, 93, 94, 97, 97, 97, 97])
    closes = np.array([94, 94, 94, 89.5, 88.0, 91, 94, 95, 99, 99, 99, 98.8])
    return highs, lows, closes


def test_stats_carry_failed_s_and_terminal_engagement():
    highs, lows, closes = _contraction_arrays()
    read = read_rail_episodes_arrays(highs, lows, closes, 100.0, 90.0, 2.0)
    stats = episode_sequence_stats(read)
    assert stats["n_failed_s"] == 1                  # the breached floor visit
    assert stats["terminal_r_engagement"] is True    # the terminal engagement
    # The full-frame read sees the failure, so the form refuses — it cannot
    # be counterfeited by a window that broke its floor.
    assert resistance_contraction_admission(stats) is False
    # And the real reader's stats feed the label: closes end below the rail.
    assert resistance_contraction_label(stats) == "contracting at resistance"


def test_failed_s_respects_the_as_of_knowability_rule():
    highs, lows, closes = _contraction_arrays()
    read = read_rail_episodes_arrays(highs, lows, closes, 100.0, 90.0, 2.0)
    edge = read["n_bars"] - 1
    stats = episode_sequence_stats(read, as_of_bar=edge)
    # At the frame edge the failed-S episode's merge horizon has printed
    # (its knowable_bar <= edge), so the count matches the full-frame read.
    assert stats["n_failed_s"] == 1


def test_paying_read_never_consults_the_species_form():
    # The gate the whole design hangs on: the form flag is DARK, and the
    # story pool reads it lazily — the species lane toggles it via
    # window_override around its own election only.
    assert settings.POWER_PLAY_STORY_FORM_ENABLED is False
