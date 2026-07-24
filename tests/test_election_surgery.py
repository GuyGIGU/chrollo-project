"""Election surgery guards (solve-the-engine task 13, dark).

Stale-frame dethronement (ELECTION_DETHRONE_ENABLED): a rescue-propped
framing the tape has fully left behind for the trailing N sessions loses
the election to a later valid framing. (The sibling rescued-pool
arbitration lever was built and REJECTED by this very guard — it killed
VIK's pinned corpus hit; the counterexample is recorded at the seam in
box_primitives.)

The blast-radius pin: election surgery exists to fix MATX-class stale
elections at the operator's marks — it must move NOTHING else. Flag-on over
the sealed marks-corpus fixture's pinned hits at their first-fire sessions,
every election must be identical to flag-off (the reverted shelf-R lesson,
enforced hermetically).
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config import settings
from engine_alpha.election_identity import projection, same_election
from engine_alpha.structure.narrative import read_structure
from tools.replay import fixture_frame, flag_capture, load_sealed_fixture, prepared_frame


def test_flag_state_and_rejected_lever():
    # Dethronement flipped LIVE 2026-07-16 (operator grant, flip checklist #4);
    # the sweep below is the blast-radius contract either way. The REJECTED
    # arbitration lever must never quietly return (it killed VIK's pinned hit).
    assert settings.ELECTION_DETHRONE_ENABLED is True
    assert not hasattr(settings, "ELECTION_RESCUED_COMPETE_ENABLED"), \
        "the rejected arbitration lever must not quietly return"


@pytest.mark.regression
def test_election_surgery_moves_no_corpus_election():
    # Every pinned corpus HIT read at its frozen first-fire session (where a
    # structure provably exists), flag-off vs flag-on: the election must not
    # change hands anywhere the operator did not mark a stale-election
    # defect. Non-vacuity: the sweep must actually read boxes.
    import pandas as pd
    frames, baseline = load_sealed_fixture()
    hits = [s for s in baseline["setups"] if s["status"] == "hit"]
    assert len(hits) >= 5, "sealed fixture went vacuous"
    n_elected = 0
    moved = []
    for setup in hits:
        raw = fixture_frame(frames, setup["key"], setup["ticker"])
        prep = prepared_frame(raw, pd.Timestamp(setup["first_fire"]))
        if prep is None:
            continue
        df, atr = prep
        base = read_structure(df, atr)
        with flag_capture(ELECTION_DETHRONE_ENABLED=True):
            on = read_structure(df, atr)
        if base is None and on is None:
            continue
        n_elected += 1
        if (base is None) != (on is None) or not same_election(
                projection(base, df), projection(on, df)):
            moved.append(setup["ticker"])
    assert n_elected >= 3, "sweep read no structures — vacuous guard"
    assert not moved, f"election surgery re-elected non-target boxes: {moved}"
