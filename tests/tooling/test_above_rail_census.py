"""The above-rail census's basis check, pinned.

Only the DRAWN leg runs here: it is pure frame arithmetic (no cascade read), so
it is fast enough for the default suite, and it is the leg that licenses the
whole instrument. The census reports new numbers about rests ABOVE the rail; its
standing to do so rests entirely on re-deriving the BELOW-side figures the 0.30
razor was placed on. If the basis drifts, the new numbers are worthless — so
that reproduction is the thing worth guarding, not the headline.
"""
import pytest

from tools.above_rail_census import drawn_leg
from tools.marks_corpus import load_corpus
from tools.replay import load_sealed_fixture

# The ruling record's own figures (docs/consolidation_method_2026-09.md §Task 6):
# DSGN 0.010 / MATX 0.087 / MSGS 0.148 ATR UNDER his drawn R.
_RULING_RECORD_BELOW_R = {
    "DSGN:2026-03-31": -0.010,
    "MATX:2026-07-01": -0.087,
    "MSGS:2026-05-22": -0.148,
}


@pytest.fixture(scope="module")
def rows():
    setups = load_corpus()
    frames, _ = load_sealed_fixture()
    return {r["key"]: r for r in drawn_leg(setups, frames)}


def test_the_census_reproduces_the_figures_the_razor_was_placed_on(rows):
    """The basis check: re-derive the ruling record's own below-R depths."""
    for key, expected in _RULING_RECORD_BELOW_R.items():
        assert key in rows, f"{key} vanished from the sealed marks corpus"
        got = rows[key]["low_minus_R_atr"]
        assert got == pytest.approx(expected, abs=0.0005), (
            f"{key}: the census measures {got:+.3f} ATR against the ruling "
            f"record's {expected:+.3f}. The basis moved (ATR offset, wick vs "
            "close, or the drawn span), so every ABOVE-rail number this "
            "instrument reports is now unlicensed - fix the basis, never the "
            "expectation.")


def test_the_drawn_corpus_still_holds_shelves_on_both_sides_of_the_rail(rows):
    """A one-sided corpus would make the above-rail leg vacuous.

    The census's headline is that 3 of 33 drawn shelves sit ABOVE R. If a future
    corpus edit left none there, the instrument would keep printing "0 of N"
    and read as evidence of absence rather than a corpus that stopped covering
    the case."""
    measured = [r for r in rows.values() if "low_minus_R_atr" in r]
    assert len(measured) == 33, f"expected 33 measurable drawn shelves, got {len(measured)}"
    above = [r for r in measured if r["low_minus_R_atr"] > 0]
    below = [r for r in measured if r["low_minus_R_atr"] < 0]
    assert above and below, (
        f"the drawn corpus no longer straddles the rail ({len(above)} above, "
        f"{len(below)} below) - the above-rail census cannot measure what the "
        "corpus does not contain")
