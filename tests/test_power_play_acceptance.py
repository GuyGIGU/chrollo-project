"""The species acceptance battery + dark ratchet (program Task 10).

The committed fixture pair (tests/baselines/power_play_fixture.parquet +
power_play_baseline.json, built by tools/power_play_fixture.py) freezes MAN at
2026-08-12 (the session BEFORE his breakout) and FTNT at its 2026-08-13 fire.
The baseline is a CHANGE DETECTOR: the species read and the default read on
those exact frames must reproduce it byte-for-byte — any deviation fails, and
a recapture is legal only in a declared flip/seam commit (EC-29). The sealed
28/33 marks corpus is untouched by this battery.

The frozen facts the pair carries (captured 2026-08-17, worth reading):
  * MAN @ 08-12 = species PENDING — at the provisional clock 10 the first
    legal look lands ON breakout day (08-13), one session too late; clock 8
    is the first value that watches MAN pre-breakout. The census + the
    operator's sheets rule the clock with exactly this on the table.
  * FTNT @ 08-13 = default read ELECTS (the live tier-S fire) while its July
    shelf does NOT pole-qualify (+40.9%/40 bars — the broad tier-2 species);
    the watch latches the older May episode, long broken out: refused_clock.
"""
import numpy as np
import pandas as pd
import pytest

from config import settings
from engine_alpha.structure.box_primitives import collect_root_anchors
from engine_alpha.evaluation import species_watch
from engine_alpha.structure.power_play import PP_STATES
from tools.power_play_fixture import frame_digest, load_fixture


@pytest.fixture(scope="module")
def fixture():
    return load_fixture()


# ── EC-12: the committed basis is content-verified at check time ────────────

def test_fixture_frames_match_their_sealed_digests(fixture):
    frames, baseline = fixture
    assert set(frames) == set(baseline["tickers"]) == {"MAN", "FTNT"}
    for ticker, entry in baseline["tickers"].items():
        assert len(frames[ticker]) == entry["bars"]
        assert frame_digest(frames[ticker]) == entry["frame_digest"]


# ── the dark ratchet: any deviation from the frozen reads fails ─────────────

@pytest.mark.parametrize("ticker", ["MAN", "FTNT"])
def test_species_read_reproduces_the_ratchet_baseline(fixture, ticker):
    frames, baseline = fixture
    entry = baseline["tickers"][ticker]["species"]
    watch, stats = species_watch(frames[ticker])
    assert (None if watch is None else watch["state"]) == entry["state"]
    assert (None if watch is None else watch["clock"]) == entry["clock"]
    assert (None if watch is None else watch["fields"]) == entry["fields"]
    assert {k: v for k, v in sorted(stats.items())
            if k != "pp_eval_ms"} == entry["stats"]


@pytest.mark.parametrize("ticker", ["MAN", "FTNT"])
def test_default_read_reproduces_the_ratchet_baseline(fixture, ticker):
    from engine_alpha.evaluation import _prepare_eval_frame_with_reason
    from engine_alpha.structure.narrative import read_structure

    frames, baseline = fixture
    entry = baseline["tickers"][ticker]["default_read"]
    prep, _ = _prepare_eval_frame_with_reason(frames[ticker])
    assert prep is not None
    pdf = prep["df"]
    atr = float(pdf.iloc[-int(settings.STRUCTURE_ATR_SAMPLE_OFFSET)]["ATR_10"])
    s = read_structure(pdf, atr)
    elects = bool(s is not None and s.box is not None)
    assert elects == entry["elects"]
    if elects:
        assert str(pdf.index[int(s.box.start_bar)].date()) == entry["box_open"]


def test_the_frozen_behavioral_facts_hold(fixture):
    _frames, baseline = fixture
    # FTNT fires at the default clock (the live control) …
    assert baseline["tickers"]["FTNT"]["default_read"]["elects"] is True
    # … MAN does not (the wall the whole program exists for) …
    assert baseline["tickers"]["MAN"]["default_read"]["elects"] is False
    # … and every frozen species state is in the closed set or honest-None.
    for entry in baseline["tickers"].values():
        state = entry["species"]["state"]
        assert state is None or state in PP_STATES


# ── EC-32: the input-tied assertion, mutation-checked once ──────────────────

def test_species_facts_derive_from_the_frame_itself(fixture):
    # MAN's frozen ADMITTED facts must be recomputable from the fixture
    # frame's OWN bars (input-tied — a watch that ignored its input could
    # never produce them): the pole gain from the recorded climax over the
    # trailing pole window's min low, and the shelf denominator from the
    # recorded span's own trading days.
    frames, baseline = fixture
    fields = baseline["tickers"]["MAN"]["species"]["fields"]
    df = frames["MAN"]
    peak_pos = df.index.get_indexer([pd.Timestamp(fields["climax_date"])])[0]
    assert peak_pos > 0
    window = int(getattr(settings, "POWER_PLAY_POLE_WINDOW_BARS", 40))
    low = float(df["Low"].iloc[max(0, peak_pos - window + 1):peak_pos + 1].min())
    recomputed = float(df["High"].iloc[peak_pos]) / low - 1.0
    assert fields["pole_gain"] == pytest.approx(recomputed, abs=1e-3)
    start = df.index.get_indexer([pd.Timestamp(fields["shelf_start_date"])])[0]
    end = df.index.get_indexer([pd.Timestamp(fields["shelf_end_date"])])[0]
    assert start >= 0 and end >= 0
    # The lane counts the span INCLUSIVE of both ends (len of the slice).
    assert fields["shelf_bars"] == end - start + 1


def test_mutation_probe_a_flattened_pole_is_not_watched(fixture):
    # Feed the seam a wrong input ONCE and prove the suite would go red: the
    # same MAN frame with its advance flattened must produce NO watch.
    frames, _ = fixture
    df = frames["MAN"].copy()
    flat = float(df["Close"].iloc[0])
    for col in ("Open", "High", "Low", "Close"):
        df[col] = flat
    df["High"] += 0.5
    df["Low"] -= 0.5
    assert species_watch(df) == (None, {})


# ── the composed twin on the frozen frames (2026-08-17 review, finding 3) ───

def test_the_composed_twin_carries_the_frozen_states_end_to_end(fixture):
    # The one committed real-world fired-plus-watched composition, at the
    # RULED read (clock 8 + the departure wall, operator 2026-08-18): FTNT
    # fires at the default read (the live control) while its watched June
    # episode goes honestly UNFRAMED (no root frames that shelf — counted,
    # no record fabricated); MAN — the specimen the program exists for — is
    # WATCHED AND ADMITTED the day before the operator's breakout
    # (`admitted_dark`, his exact climax/AR dates), with no fire at the
    # default read: the dark lane now reads MAN end-to-end.
    from engine_alpha.evaluation import evaluate_ticker_with_power_play
    from tools.replay import flag_capture

    frames, baseline = fixture
    assert baseline["tickers"]["FTNT"]["species"]["state"] is None
    assert baseline["tickers"]["MAN"]["species"]["state"] == "admitted_dark"
    with flag_capture(POWER_PLAY_PRESET_ENABLED=True,
                      NEAR_MISS_LANE_ENABLED=False):
        base, row, stats = evaluate_ticker_with_power_play("FTNT", frames["FTNT"])
        man_base, man_row, man_stats = evaluate_ticker_with_power_play(
            "MAN", frames["MAN"])
    assert isinstance(base, dict)                  # the fire is intact
    assert "_pp_state" not in base                 # no watch record: NULL family
    assert row is None                             # nothing to publish beyond the fire
    assert stats["pp_shelf_unframed"] == 1 and "pp_eval_ms" in stats
    assert man_base is None                        # no fire at the default read
    assert man_row["ticker"] == "MAN"              # the admitted watch publishes
    assert man_row["status"] == "watched_ungraded"
    assert man_stats["pp_admitted_dark"] == 1 and "pp_eval_ms" in man_stats


# ── the clock moves ONLY under the preset (synthetic, hand-reasoned) ────────

def test_a_13_bar_ar_seeds_under_the_species_clock_only():
    # LIVN's "way too young" 13-bar case: age-walled at the default clock,
    # seedable at the species clock — the constant moved, nothing else.
    n = 476
    closes = np.empty(n)
    closes[:400] = 40 + 10 * np.arange(400) / 399
    closes[400:440] = 50 + 50 * np.arange(40) / 39
    closes[440:447] = np.linspace(98, 88.5, 7)
    shelf = np.arange(447, n)
    closes[447:] = np.where(shelf % 2 == 0, 90.0, 92.0)
    idx = pd.bdate_range("2024-06-03", periods=n)
    df = pd.DataFrame({"Open": closes, "High": closes + 0.5,
                       "Low": closes - 0.5, "Close": closes,
                       "Volume": 200_000.0}, index=idx)
    young = df.iloc[:460]                     # AR at 446 is 13 bars old
    assert not any(a[2] == 446 for a in
                   collect_root_anchors(young, settings.MIN_BASE_DAYS))
    species_clock = settings.POWER_PLAY_WINDOWS["MIN_BASE_DAYS"]
    assert any(a[2] == 446 for a in
               collect_root_anchors(young, species_clock))
