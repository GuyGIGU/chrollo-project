"""The armed-form roster's contract at the seams the story pool exposes
(council review 2026-09-01, finding 12).

Three laws, all about seams that used to trust their callers:

1. **The roster is a closed vocabulary, asserted where it enters the WALK**
   (EC-55). ``ADMISSION_FORMS`` is only ever membership-tested, so a
   hand-built, misspelled, empty or one-shot roster would arm nothing (or the
   wrong thing) and the walk would look like an honest refusal. The walk's
   entry raises instead, naming the offender, ONCE per read and before the
   first frame is touched — not the story pool, and not the box election.
   Both of those are DATA-dependent: the pool is skipped whenever an ordinary
   pool elects, and the box election never runs at all on a chart that seeds
   no root swing, so asserting at either validated a typo on some tickers and
   passed it in silence on others (round-two and round-three completeness
   critics, 2026-09-01).
2. **Narration silence belongs to the POOL, not to the judgment.** The story
   pool's respect refusals stay silent because the strict pass already
   narrated the identical windows — so a future pool reusing the ONE ladder
   with its own ruled judgment must NOT inherit that silence.
3. **The judgment seam has ONE visible output channel** — the ``Admission``
   record it returns.

Synthetic frames throughout, save for the one real chart the placement proof
needs: a read that genuinely ELECTS, which no synthetic frame here produces.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from config import settings
from engine_alpha.structure import box_primitives as bp
from engine_alpha.structure import bricks as real_bricks
from engine_alpha.structure import event_map as em
from engine_alpha.structure import narrative
from engine_alpha.structure.box_primitives import (
    ELECTED_POOLS,
    PRE_NARRATED_POOLS,
    Admission,
    _build_candidate,
    _story_pool_candidates,
)
from engine_alpha.structure.bricks import RootSwing, validate_equilibrium
from engine_alpha.structure.event_map import (
    ADMISSION_FORM_RESISTANCE_CONTRACTION,
    ADMISSION_FORM_S_TEST,
    ADMISSION_FORM_S_TEST_BAR_POSTURE,
    ADMISSION_FORMS,
    assert_admission_roster,
    baseline_admission_roster,
)

R, S, ATR = 14.0, 12.0, 1.0
ZZ = [(0, "peak", 14.0), (5, "valley", 12.0)]
BOX_WIDTH = (R - S) / S


def _frame(bars):
    return pd.DataFrame({"High": [b[0] for b in bars],
                         "Low": [b[1] for b in bars],
                         "Close": [b[2] for b in bars],
                         "Volume": [1_000_000.0] * len(bars)})


def _respected_bars():
    """R=14 / S=12, atr=1: a quiet in-band window — no bar leaves the
    buffered rails, so the shared ladder reaches its admission slot."""
    bars = [
        (13.3, 12.7, 13.0),
        (13.4, 12.9, 13.1),
        (13.3, 12.8, 13.0),
        (13.0, 12.4, 12.7),
        (12.9, 12.2, 12.6),
        (12.8, 12.0, 12.5),
        (13.2, 12.6, 13.0),
        (13.3, 12.7, 13.1),
        (13.3, 12.7, 13.0),
        (13.4, 12.8, 13.1),
        (13.0, 12.4, 12.7),
        (12.9, 12.3, 12.6),
        (13.0, 12.2, 12.8),
        (13.3, 12.7, 13.1),
    ]
    bars += [(13.3, 12.7, 13.0)] * 11
    bars += [
        (13.6, 12.9, 13.3),
        (13.8, 13.1, 13.6),
        (14.0, 13.3, 13.8),
        (14.2, 13.5, 14.05),
        (14.4, 13.7, 14.2),
    ]
    return bars


def _crashed_bars():
    """The same rails with every bar far BELOW the buffered floor: the
    respect gate refuses on share before any admission slot is reached."""
    return [(11.0, 9.0, 9.5)] * 20


def _electing_read():
    """A frame that ELECTS on the strict pool (``test_bricks``'s worked range,
    R=110 / S=100, atr 1) — so the last-resort story pool, which only runs
    once every ordinary pool has come back empty, is never consulted. THIS is
    the read the round-one placement left unvalidated."""
    closes = [101.0, 103.0, 105.0, 107.0, 109.0, 107.0, 105.0, 103.0] * 4
    df = pd.DataFrame({"Open": closes,
                       "High": [c + 1.0 for c in closes],
                       "Low": [c - 1.0 for c in closes],
                       "Close": closes,
                       "Volume": [1000.0] * len(closes)})
    return df, RootSwing("BC", 0, 0, 110.0, 100.0, 0.1, 0)


def _riser_frame(n=300):
    """A steady riser: no 5% reaction ever prints, so the walk asks for a root
    swing ONCE, is told there is none, and returns — the box election is never
    reached. THIS is the read the round-two placement left unvalidated: the
    assertion sat at the box election, which this chart never calls."""
    closes = 15.0 * (1.005 ** np.arange(n))
    return pd.DataFrame({"Open": closes, "High": closes * 1.004,
                         "Low": closes * 0.996, "Close": closes,
                         "Volume": np.full(n, 2_000_000.0)},
                        index=pd.bdate_range("2025-01-02", periods=n))


@pytest.fixture(scope="module")
def electing_read():
    """A REAL marked chart whose paying read elects a complete story (VLO, the
    sealed corpus's own name — read-only). Needed because the placement proof
    must cover a read that never falls through to the story pool, and the
    synthetic frames in this file all refuse."""
    from engine_alpha import evaluation
    from tools.marks_corpus import _load_fixture
    from tools.replay import fixture_frame
    frames, baseline = _load_fixture()
    mark = next(x for x in baseline["setups"]
                if x["status"] == "hit" and x["key"].startswith("VLO"))
    sliced = fixture_frame(frames, mark["key"], mark["ticker"]).loc[
        :pd.Timestamp(mark["first_fire"])]
    prep, _reason = evaluation._prepare_eval_frame_with_reason(sliced)
    df = prep["df"]
    return df, float(evaluation.structure_atr_row(df)["ATR_10"])


class _BricksProxy:
    """The real validators, with a tally on the two calls that touch the
    frame. Delegation is total (``__getattr__``), so the walk reads exactly
    the chart it always reads — the tally is the only difference, and it is
    read from the test body where nothing can swallow it."""

    def __init__(self):
        self.roots = 0
        self.boxes = 0

    def __getattr__(self, name):
        return getattr(real_bricks, name)

    def find_root_swing(self, *args, **kwargs):
        self.roots += 1
        return real_bricks.find_root_swing(*args, **kwargs)

    def validate_equilibrium(self, *args, **kwargs):
        self.boxes += 1
        return real_bricks.validate_equilibrium(*args, **kwargs)


class _PoolSpy:
    """A consultation tally for the story pool. It RECORDS and returns; it
    never asserts inside the engine — an assertion raised in a monkeypatched
    callback can be swallowed by a guard upstream, which is exactly how the
    round-one test passed while pinning nothing. The test body reads the
    tally afterwards, where nothing can catch it."""

    def __init__(self):
        self.calls = 0

    def __call__(self, *args, **kwargs):
        self.calls += 1
        return []


class _SpyRecorder:
    """The near-miss recorder's booking seam, numbers ignored."""

    def __init__(self):
        self.booked = []

    def refusal(self, leg, pool, *args):
        self.booked.append((leg, pool))


def _ladder(bars, *, pool, judgment, trace=None, recorder=None):
    df = _frame(bars)
    return _build_candidate(
        df["High"].values, df["Low"].values, df, R, S, BOX_WIDTH,
        0, 5, 0, ATR, trace=trace, rescued=True, pool=pool,
        recorder=recorder, occupancy_judgment=judgment)


# ── 1. the roster is a closed vocabulary, asserted where the walk hands it in ──

def test_every_declared_token_names_one_ruled_form():
    """The declared vocabulary IS the three ruled forms — no more, no less
    (EC-33: one tuple, never re-typed)."""
    assert ADMISSION_FORMS == (ADMISSION_FORM_S_TEST,
                               ADMISSION_FORM_RESISTANCE_CONTRACTION,
                               ADMISSION_FORM_S_TEST_BAR_POSTURE)
    assert len(set(ADMISSION_FORMS)) == 3


@pytest.mark.parametrize("roster", [
    (ADMISSION_FORM_S_TEST,),
    ADMISSION_FORMS,
    frozenset(ADMISSION_FORMS),
    {ADMISSION_FORM_S_TEST, ADMISSION_FORM_S_TEST_BAR_POSTURE},
])
def test_a_declared_roster_passes_the_assertion(roster):
    assert assert_admission_roster(roster) is None


@pytest.mark.parametrize("empty", [(), [], set(), frozenset()])
def test_an_empty_roster_is_refused_not_quietly_allowed(empty):
    """The ORIGINAL defect, and it used to pass the subset test: an empty
    roster arms nothing, so the pool refuses every pair and the read is
    indistinguishable from an honest refusal. It is illegal rather than a
    no-op — no legal caller can build one (the baseline always carries the
    S-test form, the escalation only ever ADDS), and declining to consult the
    pool at all is what the story-pool flag is for."""
    with pytest.raises(ValueError) as err:
        assert_admission_roster(empty)
    assert "empty" in str(err.value)


def test_a_one_shot_iterator_is_refused_before_anything_consumes_it():
    """The roster is membership-tested three times downstream, so a generator
    would answer the first question and nothing after — and taking ``set()``
    of it to validate is precisely what would drain it."""
    roster = (form for form in ADMISSION_FORMS)
    with pytest.raises(TypeError) as err:
        assert_admission_roster(roster)
    assert "iterator" in str(err.value)
    assert list(roster) == list(ADMISSION_FORMS)     # untouched — nothing drained


def test_a_bare_string_is_not_a_roster():
    """``"s_test" in "s_test_bar_posture"`` is True by SUBSTRING: a string
    roster would silently arm forms nobody named."""
    assert ADMISSION_FORM_S_TEST in ADMISSION_FORM_S_TEST_BAR_POSTURE
    with pytest.raises(TypeError):
        assert_admission_roster(ADMISSION_FORM_S_TEST_BAR_POSTURE)


@pytest.mark.parametrize("token", [
    "s_test_bar_postures",              # a plausible misspelling
    "bar_posture",                      # the lane's name, not the form's
    "resistance-contraction",           # the right words, the wrong token
    "S_TEST",                           # case is not a nickname
])
def test_an_unknown_token_fails_loudly_and_names_itself(token):
    """The failure mode this closes: an unknown token arms nothing, so the
    walk refuses and reads exactly like an honest refusal."""
    with pytest.raises(ValueError) as err:
        assert_admission_roster({ADMISSION_FORM_S_TEST, token})
    assert token in str(err.value)
    assert ADMISSION_FORM_S_TEST in str(err.value)      # the declared roster


def test_the_baseline_roster_is_always_declared(monkeypatch):
    """Both flag states of the ONE derivation stay inside the vocabulary."""
    for armed in (False, True):
        monkeypatch.setattr(settings, "POWER_PLAY_STORY_FORM_ENABLED", armed)
        roster = baseline_admission_roster()
        assert roster <= set(ADMISSION_FORMS)
        assert assert_admission_roster(roster) is None


def test_the_escalated_roster_the_walk_builds_is_declared():
    """The full-refusal escalation's widest roster (both rescue lanes armed)
    is legal — the assertion guards typos, never the lanes."""
    widest = set(baseline_admission_roster()) | {
        ADMISSION_FORM_RESISTANCE_CONTRACTION,
        ADMISSION_FORM_S_TEST_BAR_POSTURE}
    assert assert_admission_roster(widest) is None


def test_the_electing_read_never_consults_the_story_pool(monkeypatch):
    """The premise of the placement proof below, pinned separately so it can
    never silently stop being true: this frame elects on an ordinary pool, so
    the last-resort story pool — the round-one assertion's site — does not
    run at all."""
    spy = _PoolSpy()
    monkeypatch.setattr(bp, "_story_pool_candidates", spy)
    df, root = _electing_read()
    box = validate_equilibrium(df, root, 1.0,
                               forms=frozenset(ADMISSION_FORMS))
    assert box is not None
    assert box.elected_pool == "strict"
    assert spy.calls == 0


def test_a_typod_roster_raises_on_a_read_that_never_consults_the_story_pool(
        monkeypatch):
    """THE placement proof: validation may not depend on the DATA. Asserted
    inside the story pool, this typo passed in silence on every electing
    ticker and raised only on the ones whose ordinary pools came back empty —
    a flaky engine where a programmer error belongs. Asserted at the
    parameter's entry, it raises here, with the pool never consulted."""
    spy = _PoolSpy()
    monkeypatch.setattr(bp, "_story_pool_candidates", spy)
    df, root = _electing_read()
    with pytest.raises(ValueError) as err:
        validate_equilibrium(df, root, 1.0,
                             forms={ADMISSION_FORM_S_TEST,
                                    "s_test_bar_postures"})
    assert "s_test_bar_postures" in str(err.value)
    assert spy.calls == 0


def test_the_entry_assertion_runs_before_every_frame_gate():
    """Unconditional means unconditional: a roster typo raises even on a frame
    the walk refuses outright, so the programmer's mistake is never hidden
    behind a data refusal."""
    with pytest.raises(ValueError) as err:
        validate_equilibrium(None, None, float("nan"),
                             forms={"s_test_bar_postures"})
    assert "s_test_bar_postures" in str(err.value)


def test_a_declared_roster_at_the_entry_elects_exactly_as_no_roster_does():
    """The assertion adds no refusal of its own: the baseline roster handed in
    explicitly and the ordinary roster-less read elect the same box."""
    df, root = _electing_read()
    asserted = validate_equilibrium(df, root, 1.0,
                                    forms=baseline_admission_roster())
    ordinary = validate_equilibrium(df, root, 1.0)
    assert ordinary is not None
    assert (asserted.S, asserted.R, asserted.start_bar, asserted.base_len,
            asserted.elected_pool) == (
        ordinary.S, ordinary.R, ordinary.start_bar, ordinary.base_len,
        ordinary.elected_pool)


def test_the_story_pool_accepts_the_baseline_and_the_declared_roster():
    """Downstream of the entry assertion: forms=None (the ordinary walk, which
    resolves the baseline by the ONE derivation) and an already-asserted
    explicit roster both run."""
    df = _frame(_respected_bars())
    args = (df, df["High"].values, df["Low"].values, ZZ, ATR, 0)
    assert isinstance(_story_pool_candidates(*args), list)
    assert isinstance(
        _story_pool_candidates(*args, forms=frozenset(ADMISSION_FORMS)), list)


# ── 1b. the roster is asserted at the WALK's entry, once, before the data ────
# The four tests above enter at ``validate_equilibrium`` — the public API's own
# guard, kept. These enter at the WALK, which is where the engine's only roster
# hand-off actually happens (``narrative.read_structure``'s escalation, the one
# ``forms=`` call site outside the tests), and pin the two properties the box
# election cannot have: it runs on EVERY read, and it runs before any of them
# has looked at a chart.

def test_the_riser_read_never_reaches_the_box_election():
    """The anti-vacuity premise for the proof below, pinned so it can never
    silently stop being true: on this chart the walk asks for a root swing
    once, gets nothing, and returns — so the box election, where round two put
    the assertion, is never called. A roster error here had nowhere to raise."""
    probe = _BricksProxy()
    walked = narrative._walk_structure(
        _riser_frame(), 0.06, bricks=probe,
        forms=frozenset((ADMISSION_FORM_S_TEST,)))
    assert walked is None                      # an honest structural refusal
    assert probe.roots == 1                    # the walk did run
    assert probe.boxes == 0                    # ...and never elected a box


@pytest.mark.parametrize("roster, exc, needle", [
    ({ADMISSION_FORM_S_TEST, "s_test_bar_postures"}, ValueError,
     "s_test_bar_postures"),
    (set(), ValueError, "empty"),
    (ADMISSION_FORM_S_TEST, TypeError, "string"),
    (iter([ADMISSION_FORM_S_TEST]), TypeError, "iterator"),
])
def test_a_roster_error_raises_on_a_read_that_elects_no_box(roster, exc, needle):
    """THE round-three proof. All four of these passed in SILENCE on this
    chart while the assertion lived at the box election: no root swing, no box
    election, no assertion, and the read came back looking like the honest
    refusal it also happens to be — a programmer error hidden behind a data
    refusal. Asserted at the walk's entry, each raises here."""
    with pytest.raises(exc) as err:
        narrative._walk_structure(_riser_frame(), 0.06, forms=roster)
    assert needle in str(err.value)


def test_a_typod_roster_raises_before_the_electing_walk_touches_the_chart(
        electing_read):
    """The other half: a chart that ELECTS. Here the box election does run, so
    round two's placement did eventually raise — but only after the walk had
    read the chart, and only because this chart happened to seed a root. The
    entry assertion raises with the tally still at zero, so the verdict no
    longer depends on the data at all."""
    df, atr = electing_read
    probe = _BricksProxy()
    with pytest.raises(ValueError) as err:
        narrative._walk_structure(df, atr, bricks=probe,
                                  forms={ADMISSION_FORM_S_TEST,
                                         "s_test_bar_postures"})
    assert "s_test_bar_postures" in str(err.value)
    assert (probe.roots, probe.boxes) == (0, 0)


def test_the_same_electing_chart_does_read_when_the_roster_is_declared(
        electing_read):
    """The anti-vacuity twin of the test above: the tally is zero because the
    assertion fired first, NOT because this chart is inert. Handed a declared
    roster, the identical call walks the chart and elects a complete story."""
    df, atr = electing_read
    probe = _BricksProxy()
    story = narrative._walk_structure(df, atr, bricks=probe,
                                      forms=frozenset(ADMISSION_FORMS))
    assert story is not None
    assert probe.roots >= 1 and probe.boxes >= 1


def test_the_escalated_walk_asserts_the_roster_exactly_once(monkeypatch):
    """One validation per read, at the top — not one per root swing, and not
    one per candidate window. On the riser the walk is the ONLY caller, so the
    count is exact."""
    calls = []
    real = em.assert_admission_roster

    def _counted(forms):
        calls.append(forms)
        return real(forms)

    monkeypatch.setattr(em, "assert_admission_roster", _counted)
    roster = frozenset((ADMISSION_FORM_S_TEST,))
    assert narrative._walk_structure(_riser_frame(), 0.06,
                                     forms=roster) is None
    assert calls == [roster]


def test_the_ordinary_rosterless_read_never_calls_the_assertion(electing_read):
    """The ordinary walk hands no roster down, so it has nothing to assert and
    pays nothing: the story pool still resolves the baseline by the ONE
    derivation, at call time, which is what lets a scoped flag override keep
    working (AP-3 / AP-10). The live read must stay byte-identical."""
    df, atr = electing_read
    calls = []
    real = em.assert_admission_roster

    def _counted(forms):
        calls.append(forms)
        return real(forms)

    ordinary = narrative._walk_structure(df, atr)
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(em, "assert_admission_roster", _counted)
        watched = narrative._walk_structure(df, atr)
    assert calls == []
    assert ordinary is not None
    assert (watched.box.S, watched.box.R, watched.box.start_bar) == (
        ordinary.box.S, ordinary.box.R, ordinary.box.start_bar)


def test_the_live_escalation_hands_its_roster_through_the_entry(monkeypatch):
    """End to end on the ONE path that actually hands a roster down: a full
    refusal with a rescue lane armed re-walks with an explicit roster. The
    entry must SEE that roster (the round-two placement saw it zero times on
    this chart — no root swing, no box election) and must accept it rather
    than trip on it."""
    monkeypatch.setattr(settings, "BAR_POSTURE_RESCUE_ENABLED", True)
    seen = []
    real = em.assert_admission_roster

    def _counted(forms):
        seen.append(set(forms))
        return real(forms)

    monkeypatch.setattr(em, "assert_admission_roster", _counted)
    assert narrative.read_structure(_riser_frame(), 0.06) is None
    # The baseline walk hands no roster (nothing to assert); the escalated
    # re-walk hands exactly one, and it carries the armed lane's form.
    assert seen == [{ADMISSION_FORM_S_TEST, ADMISSION_FORM_S_TEST_BAR_POSTURE}]


# ── 2. narration silence is a property of the POOL ───────────────────────────

def test_the_silent_pools_are_declared_elected_pools():
    assert PRE_NARRATED_POOLS == frozenset({"story"})
    assert PRE_NARRATED_POOLS <= set(ELECTED_POOLS)


def test_the_story_pools_respect_refusal_stays_silent():
    """The strict pass narrated the identical windows — the story pool's own
    respect refusal is silent and unbooked, exactly as it always was."""
    trace, recorder = [], _SpyRecorder()

    def _never():
        pytest.fail("the judgment ran after respect refused")

    assert _ladder(_crashed_bars(), pool="story", judgment=_never,
                   trace=trace, recorder=recorder) is None
    assert trace == []
    assert recorder.booked == []


@pytest.mark.parametrize("pool", ["strict", "rescued", "band"])
def test_another_pool_with_a_judgment_still_narrates_its_respect_refusal(pool):
    """The regression this pins: silence keyed off the JUDGMENT's presence
    would hand every future pool reusing the ladder a silent respect leg."""
    trace, recorder = [], _SpyRecorder()

    def _never():
        pytest.fail("the judgment ran after respect refused")

    assert _ladder(_crashed_bars(), pool=pool, judgment=_never,
                   trace=trace, recorder=recorder) is None
    assert [r["stage"] for r in trace] == ["respect"]
    assert recorder.booked == [("respect_share", pool)]


def test_the_judgmentless_pools_are_unmoved():
    """The occupancy-family path (no judgment at all) narrates as before."""
    trace, recorder = [], _SpyRecorder()
    assert _ladder(_crashed_bars(), pool="strict", judgment=None,
                   trace=trace, recorder=recorder) is None
    assert [r["stage"] for r in trace] == ["respect"]
    assert recorder.booked == [("respect_share", "strict")]


# ── 3. the judgment seam returns ONE record ─────────────────────────────────

def test_the_admission_record_is_the_seams_whole_output():
    """Profile / form / sentence arrive through the return value — the
    ladder reads the profile off the record, and nothing is smuggled out
    through the caller's scope."""
    record = Admission("contracting at resistance | S+ S+ R0",
                       "contracting at resistance", "S+ S+ R0")
    tup = _ladder(_respected_bars(), pool="story", judgment=lambda: record)
    assert tup is not None
    assert tup.pool == "story"
    assert tup.story_profile == record.profile
    assert record.form == "contracting at resistance"
    assert record.sentence == "S+ S+ R0"


def test_a_refusing_judgment_returns_none_and_the_ladder_honors_it():
    trace = []
    assert _ladder(_respected_bars(), pool="story", judgment=lambda: None,
                   trace=trace) is None
    assert all(r["verdict"] != "valid" for r in trace)


def test_the_live_story_pool_narrates_from_the_returned_record():
    """End to end through the real ruled admission: the trace detail and the
    Candidate's evidence slot both come from the one returned record."""
    df = _frame(_respected_bars())
    trace = []
    pool = _story_pool_candidates(df, df["High"].values, df["Low"].values,
                                  ZZ, ATR, 0, trace=trace,
                                  forms=frozenset((ADMISSION_FORM_S_TEST,)))
    assert len(pool) == 1
    tup = pool[0]
    valid = [r for r in trace if r["verdict"] == "valid"]
    assert len(valid) == 1
    assert valid[0]["detail"] == f"story-admitted (ruled form): {tup.story_profile}"
