"""Negative-corpus precision gate wired into pytest/CI.

The shadow guard (``tools.shadow_diff``) freezes only previously-FIRING tickers
and seed-recall (``core.archive.seed_recall``) only fails on LOST winners, so
the guard net was one-directional: a change that made junk setups fire
universe-wide passed every gate. This module runs the REAL negative-corpus
guard (``tools.negative_corpus.check_corpus``) end-to-end against the COMMITTED
fixture: operator/dissection-labeled must-NOT-fire charts, each verified
non-firing + baseline-passing at freeze time, replayed through the per-ticker
pipeline on the fired-policy WINDOW the marks ratchet grades (the last ten
trading days ending at the frozen day, ``tools.replay.fired_window_walk``;
final method build step 1, 2026-09-13). Any case that fires on ANY window day
fails the default pytest run (and CI).

The real WINDOW replay is paid ONCE (flags off, the live engine) through a
module-scoped fixture; the three dark flag-ON states (holding shelf, story
pool, miss lanes) are replayed on the frozen day alone, as before build step 1,
so the suite pays the window cost once, not four times. Early-window fires the
engine already produced at the seam are PINNED as known (``tests/baselines/
negative_corpus_baseline.json``, ``--pin-known-fires``, Sun 13/09/2026): the
gate reds on any NEW fire day and prints the pinned ones as KNOWN, so they are
never invisible and never a free pass. The window semantics and the pin
semantics are proven on fakes in well under a second each.

Fully OFFLINE and deterministic - reads only the committed
``tests/baselines/negative_corpus.parquet`` + ``negative_corpus_meta.json``.
"""
from __future__ import annotations

import os

import pytest

from tools import negative_corpus
from tools.replay import fired_window_sessions

pytestmark = pytest.mark.regression

# The flag states the committed junk corpus is replayed under. Each flag-on
# state widens one admission form; none may make labeled junk fire.
FLAG_STATES: dict[str, dict[str, bool]] = {
    "flags_off": {},
    # Two-form guard (Event Map Task 9): the holding-shelf completion form
    # widens LPS acceptance.
    "holding_shelf_on": {"LPS_HOLDING_SHELF_ENABLED": True},
    # Story-pool guard (Event Map program Task 9): the last-resort story rung
    # widens BOX acceptance for occupancy-killed candidates. The census named
    # the exposure: RLGT is the one pool-REACHABLE junk case (every candidate
    # dies at occupancy), and KWR/GOOD carry parsing sentences behind standing
    # ordinary elections.
    "story_pool_on": {"STORY_POOL_ENABLED": True},
    # Miss-program guard (2026-08-28/29): all FOUR lanes forced ON - the
    # contraction rescue, the 50-day dip exception, the bottoming-base lane
    # (the universe door) and the ceiling-rest LPS exception (the completion
    # form). Also the ENIC razor's pin: the ceiling-rest bar (0.3 ATR) sits
    # between the drawn cluster (NOK 0.241) and ENIC's would-be rest (0.314);
    # at build time an 0.5 bar fired ENIC tier A and this went red.
    "miss_lanes_on": {
        "CONTRACTION_RESCUE_ENABLED": True,
        "SMA50_DIP_EXCEPTION_ENABLED": True,
        "BOTTOMING_BASE_LANE_ENABLED": True,
        "LPS_CEILING_REST_ENABLED": True,
    },
}


@pytest.fixture(scope="module")
def window_verdicts() -> dict[str, bool]:
    """The REAL replay of the whole corpus: the fired-policy WINDOW for the
    live engine (flags off; 17 cases x 10 days, about a minute and a half),
    the frozen day alone for each dark flag-ON state (17 evaluations each).

    Module-scoped so the suite pays the window cost exactly once, not once
    per test.
    """
    from config import settings

    verdicts: dict[str, bool] = {}
    for name, flags in FLAG_STATES.items():
        with pytest.MonkeyPatch.context() as mp:
            for flag, value in flags.items():
                mp.setattr(settings, flag, value)
            verdicts[name] = negative_corpus.check_corpus(frozen_day_only=bool(flags))
    return verdicts


def _window_days(df) -> list[str]:
    """The ISO days ``check_corpus`` walks for one frozen frame."""
    sessions, _note = fired_window_sessions(df, df.index[-1], [])
    return [ts.date().isoformat() for ts in sessions]


def _first_case():
    frames, meta = negative_corpus._load_fixture()
    case = meta["cases"][0]
    key = case.get("key", case["ticker"])
    return case, key, frames[key]


@pytest.fixture
def no_pins(monkeypatch):
    """Fake-based tests grade the window semantics with NOTHING pinned, so
    the committed known-fires baseline can never make one of them pass."""
    monkeypatch.setattr(negative_corpus, "load_known_fires", lambda: {})


def test_negative_fixture_and_meta_are_committed():
    """The guard is meaningless if its inputs are missing.

    Fail LOUDLY (never skip) if the committed fixture or meta has gone missing
    -- a silent skip would reopen the precision blind spot.
    """
    assert os.path.exists(negative_corpus._FIXTURE_PARQUET), (
        f"Missing frozen negative corpus at {negative_corpus._FIXTURE_PARQUET}; "
        "run `python -m tools.negative_corpus --build-fixture` and commit it."
    )
    assert os.path.exists(negative_corpus._FIXTURE_META), (
        f"Missing negative-corpus meta at {negative_corpus._FIXTURE_META}; "
        "run `python -m tools.negative_corpus --build-fixture` and commit it."
    )


def test_negative_corpus_still_rejects_every_case(window_verdicts):
    """Replay every frozen must-NOT-fire frame on its window; assert each
    cleanly rejects on every day.

    ``check_corpus()`` returns True iff every labeled junk case still produces
    no setup (None) on every window day - a fire, an eval crash, or a missing
    frame all fail.
    """
    assert window_verdicts["flags_off"] is True, (
        "Negative-corpus guard failed: a labeled must-NOT-fire chart fires (or "
        "crashes) on an UNPINNED window day under the current engine. Re-run "
        "`python -m tools.negative_corpus --check` to see which case and day, "
        "then either fix the precision regression or, if the fire is a "
        "deliberate recall change, re-eyeball that case and pin or re-freeze it "
        "deliberately (a declared seam, recorded in docs/decisions.md)."
    )


def test_negative_corpus_still_rejects_every_case_flag_on(window_verdicts):
    """Two-form guard (Event Map Task 9): the holding-shelf completion form
    widens LPS acceptance, so the SAME committed junk corpus is replayed with
    LPS_HOLDING_SHELF_ENABLED forced ON - a second completion form must not
    make labeled junk fire."""
    assert window_verdicts["holding_shelf_on"] is True, (
        "Negative-corpus guard failed with the holding-shelf form ON: the "
        "second completion form makes a labeled must-NOT-fire chart fire. "
        "Tighten the shelf predicate (position/monotone/length gates) before "
        "any flip."
    )


def test_negative_corpus_still_rejects_every_case_story_pool_on(window_verdicts):
    """Story-pool guard (Event Map program Task 9): the last-resort story
    rung widens BOX acceptance for occupancy-killed candidates, so the SAME
    committed junk corpus is replayed with STORY_POOL_ENABLED forced ON - the
    ruled narrative form must not make labeled junk fire."""
    assert window_verdicts["story_pool_on"] is True, (
        "Negative-corpus guard failed with the story pool ON: a labeled "
        "must-NOT-fire chart fires through the ruled admission form. Run "
        "`python -m tools.negative_corpus --check` to name the case; the "
        "admission form / in-pool gates must own it before any flip."
    )


def test_negative_corpus_still_rejects_every_case_miss_lanes_on(window_verdicts):
    """Miss-program guard (2026-08-28/29): the SAME committed junk corpus
    replayed with ALL FOUR miss-program lanes forced ON. None may make labeled
    junk fire (see FLAG_STATES for the lanes and the ENIC razor)."""
    assert window_verdicts["miss_lanes_on"] is True, (
        "Negative-corpus guard failed with the miss-program lanes ON: a "
        "labeled must-NOT-fire chart fires through one of the four lanes. "
        "Run `python -m tools.negative_corpus --check` with the flag(s) "
        "forced to name the case; the lane must own it before any flip."
    )


def test_meta_cases_all_have_frames():
    """Fixture integrity: every labeled case has a frame in the parquet.

    A meta/parquet mismatch would surface inside check_corpus as a failure, but
    this pins the direct cause when someone hand-edits one file and not the
    other.
    """
    frames, meta = negative_corpus._load_fixture()
    missing = [c["ticker"] for c in meta["cases"]
               if c["ticker"] not in frames or frames[c["ticker"]].empty]
    assert not missing, f"meta cases without fixture frames: {missing}"
    assert len(meta["cases"]) >= 15, (
        f"suspiciously small corpus ({len(meta['cases'])} cases) - the gate is "
        "only worth wiring if it protects the documented junk classes"
    )


def test_population_is_the_ruled_seventeen_without_nvt():
    """The junk population after the operator's ruling of Thu 10/09/2026:
    NVT left ("correct but would grade low" - a correct low-grade fire is not
    junk), COLM stays (ruled junk the same day). 17 cases in the meta, 17
    frames in the parquet, and NVT in neither - a stale NVT row would make
    the guard grade a chart he no longer calls junk."""
    frames, meta = negative_corpus._load_fixture()
    keys = [c.get("key", c["ticker"]) for c in meta["cases"]]
    assert len(keys) == 17, f"meta lists {len(keys)} cases, the ruled population is 17"
    assert len(frames) == 17, f"parquet holds {len(frames)} frames, the ruled population is 17"
    assert "NVT" not in keys and "NVT" not in frames, "NVT left the junk list on 2026-09-10"
    assert "COLM" in keys, "COLM was ruled junk on 2026-09-10 and stays"
    assert all(c["ticker"] != "NVT" for c in negative_corpus.CASES), (
        "NVT is still in the build recipe (tools.negative_corpus.CASES)"
    )


def test_negative_gate_bites_when_a_case_fires(no_pins, monkeypatch):
    """Bite proof: the guard must FAIL when a corpus case starts firing.

    Force one case's eval to return a firing result dict and assert
    ``check_corpus`` returns False against the REAL committed fixture. Without
    this, a guard that always returned True would look green while protecting
    nothing.

    Bite proof of the bite proof: revert check_corpus's ``walk["fires"]``
    branch and this test fails.
    """
    _frames, meta = negative_corpus._load_fixture()
    poisoned = meta["cases"][0]["ticker"]

    # Non-poisoned cases return None (a clean reject) without paying the real
    # eval - the bite proof only needs the poisoned case to reach the guard.
    def fake_eval(ticker, df, *args, **kwargs):
        if ticker == poisoned:
            return {"Setup": "LPS", "Score": 120.0, "Tier": "S"}
        return None

    # check_corpus calls the name bound in the negative_corpus module namespace.
    monkeypatch.setattr(negative_corpus, "_evaluate_ticker", fake_eval)

    assert negative_corpus.check_corpus() is False, (
        "check_corpus returned True even though a must-NOT-fire case fired - "
        "the guard is not actually gating on precision regressions."
    )


def test_negative_gate_bites_on_eval_error(no_pins, monkeypatch):
    """An eval CRASH on a corpus frame must FAIL the gate, not pass as a
    rejection.

    The corpus documents "the engine cleanly rejects this junk"; EVAL_ERROR is
    neither a rejection nor a fire - treating it as a pass would let a change
    that crashes on (and thereby hides) junk charts keep the gate green.
    """
    from engine_alpha.evaluation import EVAL_ERROR

    _frames, meta = negative_corpus._load_fixture()
    poisoned = meta["cases"][0]["ticker"]

    def fake_eval(ticker, df, *args, **kwargs):
        if ticker == poisoned:
            return EVAL_ERROR
        return None

    monkeypatch.setattr(negative_corpus, "_evaluate_ticker", fake_eval)

    assert negative_corpus.check_corpus() is False, (
        "check_corpus returned True even though a corpus frame crashed the eval "
        "chain - a crash must fail the gate loudly."
    )


# ----------------------------------------------------------------------------
# The window semantics (build step 1): proven on fakes, no real engine.
# ----------------------------------------------------------------------------
def test_negative_gate_can_pass_and_names_every_window(no_pins, monkeypatch, capsys):
    """Green-path bite: with an eval that never fires the guard must reach
    PASS, and the report must name each case's walked window - a guard
    wedged permanently red is indistinguishable from a genuine bite."""
    _case, key, df = _first_case()
    days = _window_days(df)
    monkeypatch.setattr(negative_corpus, "_evaluate_ticker", lambda *a, **k: None)

    assert negative_corpus.check_corpus() is True
    out = capsys.readouterr().out
    assert f"  {key}: window {days[0]} .. {days[-1]}" in out, out


def test_negative_gate_bites_on_a_non_final_window_day(no_pins, monkeypatch, capsys):
    """The one-day blind spot, closed: a case that fires on an EARLIER day of
    its window (and is clean on the frozen day) must FAIL, and the report must
    name that day with its score and tier."""
    case, key, df = _first_case()
    days = _window_days(df)
    assert len(days) >= 4, f"{key}: window too short to pick a non-final day: {days}"
    chosen = days[-4]

    def fire_on_chosen_day(ticker, sliced, *args, **kwargs):
        if ticker == case["ticker"] and sliced.index[-1].date().isoformat() == chosen:
            return {"Setup": "LPS", "Score": 77.7, "Tier": "B"}
        return None

    monkeypatch.setattr(negative_corpus, "_evaluate_ticker", fire_on_chosen_day)

    assert negative_corpus.check_corpus() is False, (
        f"check_corpus passed although {key} fires on window day {chosen}"
    )
    out = capsys.readouterr().out
    assert f"  {key}: FIRES on {chosen} (score=77.7, tier=B)" in out, out


def test_negative_gate_bites_on_a_non_final_eval_error_day(no_pins, monkeypatch, capsys):
    """A crash on an EARLIER window day (clean on the frozen day) fails the
    gate and is named by its day - a crash is neither a rejection nor a fire."""
    from engine_alpha.evaluation import EVAL_ERROR

    case, key, df = _first_case()
    days = _window_days(df)
    chosen = days[-3]

    def crash_on_chosen_day(ticker, sliced, *args, **kwargs):
        if ticker == case["ticker"] and sliced.index[-1].date().isoformat() == chosen:
            return EVAL_ERROR
        return None

    monkeypatch.setattr(negative_corpus, "_evaluate_ticker", crash_on_chosen_day)

    assert negative_corpus.check_corpus() is False
    out = capsys.readouterr().out
    assert f"  {key}: EVAL_ERROR on {chosen}" in out, out


# ----------------------------------------------------------------------------
# The known-fires pin (build step 1, Sun 13/09/2026): proven on fakes.
# ----------------------------------------------------------------------------
def _fire_on(case, days_to_fire):
    def fake(ticker, sliced, *args, **kwargs):
        if ticker == case["ticker"] and sliced.index[-1].date().isoformat() in days_to_fire:
            return {"Setup": "LPS", "Score": 66.6, "Tier": "B"}
        return None
    return fake


def test_negative_gate_reports_a_pinned_day_as_known_and_passes(monkeypatch, capsys):
    """A fire on a PINNED day is KNOWN: printed, never a pass in silence, and
    not a failure - the gate's teeth are for NEW fire days."""
    case, key, df = _first_case()
    days = _window_days(df)
    chosen = days[-4]
    monkeypatch.setattr(negative_corpus, "load_known_fires", lambda: {key: [chosen]})
    monkeypatch.setattr(negative_corpus, "_evaluate_ticker", _fire_on(case, {chosen}))

    assert negative_corpus.check_corpus() is True
    out = capsys.readouterr().out
    assert f"  {key}: KNOWN on {chosen} (score=66.6, tier=B)" in out, out
    assert "FIRES on" not in out


def test_negative_gate_still_bites_on_an_unpinned_day_beside_a_pinned_one(monkeypatch, capsys):
    """The pin covers exactly the pinned day: a second fire on the next day
    FAILS the gate and is named alone in the FIRES line."""
    case, key, df = _first_case()
    days = _window_days(df)
    pinned_day, new_day = days[-4], days[-3]
    monkeypatch.setattr(negative_corpus, "load_known_fires", lambda: {key: [pinned_day]})
    monkeypatch.setattr(negative_corpus, "_evaluate_ticker", _fire_on(case, {pinned_day, new_day}))

    assert negative_corpus.check_corpus() is False
    out = capsys.readouterr().out
    assert f"  {key}: FIRES on {new_day} (score=66.6, tier=B)" in out, out
    assert f"FIRES on {pinned_day}" not in out
    assert f"  {key}: KNOWN on {pinned_day}" in out


def test_frozen_day_only_ignores_earlier_window_days(no_pins, monkeypatch):
    """The dark flag-ON replays grade the frozen day alone: a fire on the
    first window day is a FAIL on the window and a PASS on the frozen day."""
    case, key, df = _first_case()
    days = _window_days(df)
    monkeypatch.setattr(negative_corpus, "_evaluate_ticker", _fire_on(case, {days[0]}))

    assert negative_corpus.check_corpus() is False
    assert negative_corpus.check_corpus(frozen_day_only=True) is True


def test_pin_known_fires_writes_early_days_and_refuses_a_frozen_day_fire(monkeypatch, tmp_path):
    """``--pin-known-fires`` pins early-window fire days only, and refuses
    outright when a case fires on its frozen day (the fixture's own premise)."""
    case, key, df = _first_case()
    days = _window_days(df)
    target = tmp_path / "negative_corpus_baseline.json"
    monkeypatch.setattr(negative_corpus, "_BASELINE_JSON", str(target))

    monkeypatch.setattr(negative_corpus, "_evaluate_ticker", _fire_on(case, {days[-4]}))
    out = negative_corpus.pin_known_fires()
    assert out["known_fires"] == {key: [days[-4]]}
    assert negative_corpus.load_known_fires() == {key: [days[-4]]}
    assert out["fired_policy"]["window_sessions"] == negative_corpus.FIRED_WINDOW_SESSIONS

    monkeypatch.setattr(negative_corpus, "_evaluate_ticker", _fire_on(case, {days[-1]}))
    with pytest.raises(RuntimeError, match="frozen day"):
        negative_corpus.pin_known_fires()


def test_known_fires_baseline_is_committed_and_coherent():
    """The committed pins: every pinned case is a corpus case, no pinned day
    is a case's frozen day, and the pin was taken under the ratchet's window
    policy. Fail LOUDLY if the file is missing - the seam was declared."""
    assert os.path.exists(negative_corpus._BASELINE_JSON), (
        f"Missing {negative_corpus._BASELINE_JSON}; the Sun 13/09/2026 seam pinned the "
        "early-window fires - run `python -m tools.negative_corpus --pin-known-fires` "
        "only as a declared seam and commit it."
    )
    import json
    frames, meta = negative_corpus._load_fixture()
    keys = {c.get("key", c["ticker"]) for c in meta["cases"]}
    with open(negative_corpus._BASELINE_JSON, "r", encoding="utf-8") as f:
        baseline = json.load(f)
    known = baseline["known_fires"]
    assert set(known) <= keys, f"pinned cases that are not in the corpus: {set(known) - keys}"
    for key, days in known.items():
        frozen_day = frames[key].index[-1].date().isoformat()
        assert frozen_day not in days, f"{key}: a frozen-day fire is pinned, which the seam forbids"
        assert days, f"{key}: pinned with no days"
    assert baseline["fired_policy"]["window_sessions"] == negative_corpus.FIRED_WINDOW_SESSIONS
