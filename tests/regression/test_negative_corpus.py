"""Negative-corpus precision gate wired into pytest/CI.

The shadow guard (``tools.regression.shadow_diff``) freezes only previously-FIRING tickers
and seed-recall (``core.archive.seed_recall``) only fails on LOST winners, so the guard
net was one-directional: a change that made junk setups fire universe-wide passed every
gate. This module runs the REAL negative-corpus replay (``tools.regression.negative_corpus``)
end-to-end against the COMMITTED fixture: the 16 operator/dissection-labeled junk charts
through the reader door on the fired-policy WINDOW the marks ratchet grades (the last ten
trading days ending at the frozen day, ``core.calibration.replay.fired_window_walk``).

The gate pins the junk charts' FIRE DAYS (decision E of the one-reader plan, Sat
31/10/2026; ``tests/baselines/negative_corpus_baseline.json``, ``--pin-known-fires``): every
pinned day must fire and no other day may. A new fire day, a crash, a missing frame or the
silent chart (GOOD) firing fails the default pytest run (and CI). The real WINDOW replay is
paid ONCE through a module-scoped fixture; the window and pin semantics are proven on fakes
in well under a second each.

Fully OFFLINE and deterministic - reads only the committed
``tests/baselines/negative_corpus.parquet`` + ``negative_corpus_meta.json`` + the pins.
"""
from __future__ import annotations

import json
import os

import pandas as pd
import pytest

from tools.regression import negative_corpus
from core.calibration.replay import fired_window_sessions

pytestmark = pytest.mark.regression


@pytest.fixture(scope="module")
def real_walks() -> tuple[list, dict]:
    """The REAL replay of the whole corpus on the fired-policy WINDOW through the reader door (16 cases x 10
    days, about a minute and a half). Module-scoped so the suite pays the window cost exactly once."""
    return negative_corpus.walk_corpus()


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
        "run `python -m tools.regression.negative_corpus --build-fixture` and commit it."
    )
    assert os.path.exists(negative_corpus._FIXTURE_META), (
        f"Missing negative-corpus meta at {negative_corpus._FIXTURE_META}; "
        "run `python -m tools.regression.negative_corpus --build-fixture` and commit it."
    )


def test_every_pinned_day_fires_and_no_other(real_walks):
    """The pin, both ways, on the real replay: each junk chart's fire days are EXACTLY its pinned days
    (a silent chart's pinned list is empty, so GOOD firing on any day fails here too), and no case
    crashed or went missing."""
    cases, walks = real_walks
    known = negative_corpus.load_known_fires()
    fired = {key: [f["day"] for f in walk["fires"]] for key, walk in walks.items() if walk is not None}
    assert set(fired) == {c.get("key", c["ticker"]) for c in cases}, "a junk frame is missing from the parquet"
    assert not any(walk["errors"] for walk in walks.values()), "the reader crashed on a junk chart"
    assert fired == known, (
        "the junk charts' fire days moved against the pins. Re-run "
        "`python -m tools.regression.negative_corpus --check` to see which case and day, then either fix "
        "the precision regression or, if the change is a deliberate reading change, re-eyeball that case "
        "and re-pin deliberately (a declared seam, recorded in docs/decisions.md)."
    )


def test_the_gate_passes_on_the_real_replay(real_walks):
    """``check_corpus``'s own verdict on the same replay: PASS, with every window named and no failure."""
    cases, walks = real_walks
    ok, failures, notes = negative_corpus.judge(cases, walks, negative_corpus.load_known_fires())
    assert ok is True and failures == [], failures
    assert sum(1 for line in notes if ": window " in line) == len(cases)


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


def test_population_is_the_ruled_sixteen():
    """The junk population after the operator's rulings: NVT left on Thu
    10/09/2026 ("correct but would grade low" - a correct low-grade fire is
    not junk), CHCT left on Sun 13/09/2026 ("The setups is valid", ruled on
    its pinned Thu 18/06/2026 window fire), COLM and DGII stay. 16 cases in
    the meta, 16 frames in the parquet, no pin for a case that left, and
    neither NVT nor CHCT anywhere - a stale row would make the guard grade a
    chart he no longer calls junk."""
    frames, meta = negative_corpus._load_fixture()
    keys = [c.get("key", c["ticker"]) for c in meta["cases"]]
    assert len(keys) == 16, f"meta lists {len(keys)} cases, the ruled population is 16"
    assert len(frames) == 16, f"parquet holds {len(frames)} frames, the ruled population is 16"
    for gone in ("NVT", "CHCT"):
        assert gone not in keys and gone not in frames, f"{gone} left the junk list on his ruling"
        assert all(c["ticker"] != gone for c in negative_corpus.CASES), (
            f"{gone} is still in the build recipe (tools.regression.negative_corpus.CASES)")
        assert gone not in negative_corpus.load_known_fires(), f"{gone} still carries a pinned fire day"
    assert "COLM" in keys, "COLM was ruled junk on 2026-09-10 and stays"
    assert "DGII" in keys, "DGII was not ruled on and stays"


def _fake_frame(seed: float) -> pd.DataFrame:
    idx = pd.bdate_range("2026-01-05", periods=6)
    base = pd.Series(range(6), index=idx, dtype=float) + seed
    return pd.DataFrame({"Open": base, "High": base + 1, "Low": base - 1,
                         "Close": base + 0.5, "Volume": 1000.0}, index=idx)


@pytest.fixture
def sealed_fake_fixture(tmp_path, monkeypatch):
    """A two-case sealed fixture (parquet + meta + one pinned fire day each)
    written under tmp_path, with the module's paths pointed at it and the
    recipe holding only BBB - so AAA is droppable and BBB is not."""
    parquet = tmp_path / "negative_corpus.parquet"
    meta_path = tmp_path / "negative_corpus_meta.json"
    pins_path = tmp_path / "negative_corpus_baseline.json"
    pd.concat({"AAA": _fake_frame(10.0), "BBB": _fake_frame(20.0)}, axis=1).to_parquet(
        parquet, engine=negative_corpus.settings.PARQUET_ENGINE)
    meta_path.write_text(json.dumps({"captured_at": "x", "breadth_pct": 0.5, "cases": [
        {"ticker": "AAA", "as_of": "2026-01-12", "label": "l", "evidence": "e"},
        {"ticker": "BBB", "as_of": "2026-01-12", "label": "l", "evidence": "e"}]}), encoding="utf-8")
    pins_path.write_text(json.dumps({"note": "n", "known_fires": {
        "AAA": ["2026-01-08"], "BBB": ["2026-01-09"]}}), encoding="utf-8")
    monkeypatch.setattr(negative_corpus, "_FIXTURE_PARQUET", str(parquet))
    monkeypatch.setattr(negative_corpus, "_FIXTURE_META", str(meta_path))
    monkeypatch.setattr(negative_corpus, "_BASELINE_JSON", str(pins_path))
    monkeypatch.setattr(negative_corpus, "CASES", (
        {"ticker": "BBB", "as_of": None, "label": "l", "evidence": "e"},))
    return parquet, meta_path, pins_path


def test_drop_case_removes_the_frame_the_meta_row_and_the_pins_together(sealed_fake_fixture):
    parquet, meta_path, pins_path = sealed_fake_fixture
    out = negative_corpus.drop_case("AAA")
    assert out == {"dropped": "AAA", "cases": 1, "pins_dropped": ["2026-01-08"]}
    data = pd.read_parquet(parquet, engine=negative_corpus.settings.PARQUET_ENGINE)
    assert set(data.columns.get_level_values(0)) == {"BBB"}, "the dropped frame's columns must leave the parquet"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    assert [c["ticker"] for c in meta["cases"]] == ["BBB"]
    assert meta["captured_at"] == "x", "dropping a case is not a re-seal"
    pins = json.loads(pins_path.read_text(encoding="utf-8"))
    assert pins["known_fires"] == {"BBB": ["2026-01-09"]}, "only the dropped case's pins leave"
    assert b"\r\n" not in pins_path.read_bytes(), "tests/baselines/*.json is LF-pinned"
    frames, meta2 = negative_corpus._load_fixture()
    assert set(frames) == {"BBB"} and len(meta2["cases"]) == 1


def test_drop_case_refuses_a_key_still_in_the_recipe_or_absent_from_the_seal(sealed_fake_fixture):
    parquet, meta_path, pins_path = sealed_fake_fixture
    with pytest.raises(RuntimeError, match="still in the build recipe"):
        negative_corpus.drop_case("BBB")
    with pytest.raises(RuntimeError, match="not in the sealed fixture"):
        negative_corpus.drop_case("ZZZ")
    data = pd.read_parquet(parquet, engine=negative_corpus.settings.PARQUET_ENGINE)
    assert set(data.columns.get_level_values(0)) == {"AAA", "BBB"}, "a refusal must not touch the seal"
    assert json.loads(pins_path.read_text(encoding="utf-8"))["known_fires"] == {
        "AAA": ["2026-01-08"], "BBB": ["2026-01-09"]}


def test_negative_gate_bites_when_a_case_fires(no_pins, monkeypatch):
    """Bite proof: the guard must FAIL when a corpus case fires on an unpinned day.

    Force one case's eval to return a firing result dict and assert
    ``check_corpus`` returns False against the REAL committed fixture. Without
    this, a guard that always returned True would look green while protecting
    nothing.
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
        "check_corpus returned True even though a must-NOT-fire case fired on an unpinned day - "
        "the guard is not actually gating on precision regressions."
    )


def test_negative_gate_bites_on_eval_error(no_pins, monkeypatch):
    """An eval CRASH on a corpus frame must FAIL the gate, not pass as a
    rejection.

    EVAL_ERROR is neither a rejection nor a fire - treating it as a pass would
    let a change that crashes on (and thereby hides) junk charts keep the gate
    green.
    """
    from engine_alpha.sentinels import EVAL_ERROR

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
    """Green-path bite: with an eval that never fires and nothing pinned the guard must reach
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
    from engine_alpha.sentinels import EVAL_ERROR

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
# The known-fires pin: proven on fakes.
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


def test_a_pinned_day_that_goes_quiet_is_named_and_not_failed(monkeypatch, capsys):
    """A junk chart that stops firing on a pinned day is good news, and still a change: the gate names the day
    and passes (its teeth are for new junk fires)."""
    case, key, df = _first_case()
    days = _window_days(df)
    monkeypatch.setattr(negative_corpus, "load_known_fires", lambda: {key: [days[-4]]})
    monkeypatch.setattr(negative_corpus, "_evaluate_ticker", lambda *a, **k: None)

    assert negative_corpus.check_corpus() is True
    out = capsys.readouterr().out
    assert f"  {key}: no longer fires on {days[-4]}" in out, out


def test_the_final_day_is_pinnable_and_the_silent_chart_is_pinned_empty(monkeypatch, tmp_path):
    """``--pin-known-fires`` pins EVERY fire day, the frozen day included (DBD fires on its last day), writes an
    empty list for a silent chart, writes LF, and refuses outright on a crash."""
    from engine_alpha.sentinels import EVAL_ERROR

    case, key, df = _first_case()
    days = _window_days(df)
    target = tmp_path / "negative_corpus_baseline.json"
    monkeypatch.setattr(negative_corpus, "_BASELINE_JSON", str(target))

    monkeypatch.setattr(negative_corpus, "_evaluate_ticker", _fire_on(case, {days[-4], days[-1]}))
    out = negative_corpus.pin_known_fires()
    _frames, meta = negative_corpus._load_fixture()
    assert out["known_fires"][key] == [days[-4], days[-1]]
    assert set(out["known_fires"]) == {c.get("key", c["ticker"]) for c in meta["cases"]}, "every case is pinned"
    assert all(v == [] for k, v in out["known_fires"].items() if k != key), "a silent chart pins an empty list"
    assert negative_corpus.load_known_fires() == out["known_fires"]
    assert out["fired_policy"]["window_sessions"] == negative_corpus.FIRED_WINDOW_SESSIONS
    assert b"\r\n" not in target.read_bytes(), "tests/baselines/*.json is LF-pinned"

    def crash(ticker, sliced, *args, **kwargs):
        return EVAL_ERROR if ticker == case["ticker"] else None

    monkeypatch.setattr(negative_corpus, "_evaluate_ticker", crash)
    with pytest.raises(RuntimeError, match="EVAL_ERROR"):
        negative_corpus.pin_known_fires()


def test_known_fires_baseline_is_committed_and_coherent():
    """The committed pins: every corpus case has an entry (GOOD's is empty), every pinned day lies inside its
    case's walked window, the pin was taken under the ratchet's window policy, and the count is the 47 days
    over 15 charts the alpha reader fires (the before-baseline of the one-reader plan, Fri 30/10/2026)."""
    assert os.path.exists(negative_corpus._BASELINE_JSON), (
        f"Missing {negative_corpus._BASELINE_JSON}; run `python -m tools.regression.negative_corpus "
        "--pin-known-fires` only as a declared seam and commit it."
    )
    frames, meta = negative_corpus._load_fixture()
    keys = {c.get("key", c["ticker"]) for c in meta["cases"]}
    with open(negative_corpus._BASELINE_JSON, "r", encoding="utf-8") as f:
        baseline = json.load(f)
    known = baseline["known_fires"]
    assert set(known) == keys, f"pinned cases and corpus cases differ: {set(known) ^ keys}"
    for key, days in known.items():
        window = _window_days(frames[key])
        assert set(days) <= set(window), f"{key}: a pinned day lies outside the walked window"
        assert days == sorted(days), f"{key}: pinned days out of order"
    assert known["GOOD"] == [], "GOOD is the silent chart"
    assert sum(len(d) for d in known.values()) == 47
    assert sum(1 for d in known.values() if d) == 15
    assert baseline["fired_policy"]["window_sessions"] == negative_corpus.FIRED_WINDOW_SESSIONS
