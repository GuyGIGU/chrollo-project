"""Operator-marks acceptance gate wired into pytest/CI (Event Map, Task 1).

The FULL ratchet replay (``python -m tools.marks_corpus --check``) walks every
marked entry window through the real per-ticker pipeline (~minutes) and is the
dedicated CI / per-stage acceptance step, like the hermetic seed-recall gate.
This module keeps the plumbing honest on EVERY pytest run, cheaply: the corpus,
fixture, and ratchet baseline are committed and internally consistent; the EC-7
seal binds the marks files to the frozen baseline; the corpus loader refuses
malformed marks; and the guard actually BITES in both ratchet directions —
all without paying the replay.
"""
from __future__ import annotations

import json
import os

import pytest

from tools import marks_corpus

pytestmark = pytest.mark.regression

# The post-gap-breach stages (2026-07-24): Tasks 3/4/6 falsified
# engagement-respect, commit-the-cause, and lps-envelope in turn — every
# chart-readable miss converged on rail-placement (the named next program);
# SKYT is a universe-gate exclusion, not a chart-reading gap.
# The hand-curated stages, each naming the build-order work expected to convert
# that miss — plus the ONE stage the build assigns itself: a chart the operator
# has just drawn or redrawn that the engine cannot read. That one is not an
# explanation, it is an open question addressed to him (his 2026-09-08 ruling:
# drawing a mark must never break his gate before he has looked at it), and
# `test_a_freshly_drawn_mark_never_needs_a_hand_written_stage` keeps the two
# populations from blurring.
# "lps-ceiling" (2026-09-13): the LPS zone's R-side ceiling, 0.5 daily ranges today,
# ruled 1.35 by the operator (R12); ST's LPS low sits 1.30 above his resistance.
# Converts at build step 3 of the final method (LPS refusals to grades).
_KNOWN_STAGES = {"rail-placement", "universe-gate", "lps-ceiling", marks_corpus.NEW_MARK_STAGE}


def _load_baseline() -> dict:
    with open(marks_corpus._BASELINE_JSON, "r", encoding="utf-8") as f:
        return json.load(f)


def test_corpus_fixture_and_baseline_are_committed():
    """The gate is meaningless if its inputs are missing.

    Fail LOUDLY (never skip) if a marks file, the frozen fixture, or the
    ratchet baseline has gone missing — a silent skip would let a pinned-hit
    regression sail through CI.
    """
    for path in marks_corpus.CORPUS_FILES:
        assert os.path.exists(path), (
            f"Missing operator-marks corpus file {path}; marks are EC-7 ground "
            "truth and must stay committed."
        )
    assert os.path.exists(marks_corpus._FIXTURE_PARQUET), (
        f"Missing frozen marks fixture at {marks_corpus._FIXTURE_PARQUET}; run "
        "`python -m tools.marks_corpus --build-fixture` and commit it."
    )
    assert os.path.exists(marks_corpus._BASELINE_JSON), (
        f"Missing marks ratchet baseline at {marks_corpus._BASELINE_JSON}; run "
        "`python -m tools.marks_corpus --build-fixture` and commit it."
    )


def test_ec7_seal_binds_corpus_to_baseline():
    """EC-7: the marks files are immutable test specs.

    The baseline records a SHA-256 over the corpus files at freeze time; any
    divergence means someone edited a mark without a deliberate re-freeze. A
    failing corpus case is fixed in the ENGINE — never by editing a mark,
    widening a matcher window, or reinterpreting trigger rules.
    """
    baseline = _load_baseline()
    assert marks_corpus.corpus_sha256() == baseline["corpus_sha256"], (
        "docs/marks/ content differs from the frozen baseline seal (EC-7). If "
        "this is an operator-sanctioned correction, re-freeze deliberately with "
        "`python -m tools.marks_corpus --build-fixture`; otherwise revert the edit."
    )


def test_baseline_is_a_complete_ratchet():
    """Ratchet integrity: every corpus setup has a baseline entry and a frozen
    frame UNDER ITS EXACT KEY with the pinned bar count; statuses are hit/miss
    only; every miss names a known converting stage; provenance names the
    graduated population; and the floors sit at the Guided List's own numbers."""
    setups = marks_corpus.load_corpus()
    baseline = _load_baseline()
    frames, _ = marks_corpus._load_fixture()

    keys = {marks_corpus.setup_key(s) for s in setups}
    baseline_keys = {s["key"] for s in baseline["setups"]}
    assert keys == baseline_keys, (
        f"corpus/baseline key mismatch: only-in-corpus={sorted(keys - baseline_keys)} "
        f"only-in-baseline={sorted(baseline_keys - keys)} — re-freeze deliberately."
    )
    # Digest-graduated setups freeze under their FULL setup key — the lookup
    # takes no bare-ticker fallback for them, so a missing keyed frame is a
    # loud gap here, never a silently borrowed sibling basis.
    from tools.replay import fixture_frame

    graduated = [marks_corpus.setup_key(s) for s in setups if s.get("frame_digest")]
    not_keyed = [k for k in graduated if k not in frames]
    assert not not_keyed, (
        f"graduated setups without a frame under their exact key: {not_keyed}"
    )
    missing_frames = [k for k in sorted(keys)
                      if fixture_frame(frames, k) is None
                      or fixture_frame(frames, k).empty]
    assert not missing_frames, f"baseline setups without fixture frames: {missing_frames}"

    for entry in baseline["setups"]:
        assert entry["status"] in ("hit", "miss"), f"{entry['key']}: bad status {entry['status']!r}"
        if entry["status"] == "miss":
            assert entry.get("stage") in _KNOWN_STAGES, (
                f"{entry['key']}: frozen miss without a known converting stage "
                f"({entry.get('stage')!r}) — the ratchet must explain every miss."
            )
        # The committed parquet is the ONLY in-repo carrier of the drawn
        # bases: bind it to the baseline via the pinned bar count (the full
        # content digest is verified by --check).
        frame = fixture_frame(frames, entry["key"])
        assert len(frame) == entry["bars"], (
            f"{entry['key']}: fixture frame has {len(frame)} bars but the "
            f"baseline pinned {entry['bars']} — the parquet drifted from the "
            "freeze; rebuild the fixture deliberately."
        )
    # EC-9: the gate's own artifact must name its ground truth.
    assert baseline.get("population") == "guided-list", (
        f"baseline population {baseline.get('population')!r} — the gate lost "
        "its graduated-provenance stamp"
    )
    fp = baseline.get("marks_fingerprint") or ""
    assert len(fp) == 64 and all(c in "0123456789abcdef" for c in fp), (
        f"baseline marks_fingerprint is not a sha256 hex: {fp!r}"
    )
    assert fp == marks_corpus.corpus_provenance().get("marks_fingerprint"), (
        "baseline fingerprint differs from the corpus file's _provenance"
    )
    # Guided List floors (2026-07-24): the corpus is EC-7 append-only, so
    # these only ever move UP, deliberately, at a re-freeze.
    assert len(baseline["setups"]) >= 33, (
        f"corpus shrank below the Guided List floor ({len(baseline['setups'])}/33 setups)"
    )
    hits = sum(1 for s in baseline["setups"] if s["status"] == "hit")
    assert hits >= 28, (
        f"pinned hits fell below the Guided List floor ({hits}/28) — "
        "the gate protects the hits (26 -> 28 resealed 2026-07-26: the story "
        "pool's NKTR/YPF conversions, operator-eyeballed)"
    )


def test_fired_policy_is_pinned_to_the_replay_seam():
    """The frozen fired-policy is ENFORCED, not just stamped: the baseline's
    constants must equal the live replay seam's, and every graduated setup's
    frozen window span + clamp note must re-derive identically from the
    committed fixture (no evals — pure window arithmetic)."""
    from tools import replay

    baseline = _load_baseline()
    assert baseline["fired_policy"] == {
        "window_sessions": replay.FIRED_WINDOW_SESSIONS,
        "event_tail_sessions": replay.FIRED_EVENT_TAIL_SESSIONS,
        "max_walk_sessions": replay.FIRED_WALK_MAX_SESSIONS,
    }, ("the replay seam's fired-policy constants moved without a re-freeze — "
        "that is a deliberate EC-7 event, never a tuning knob")

    setups = {marks_corpus.setup_key(s): s for s in marks_corpus.load_corpus()}
    frames, _ = marks_corpus._load_fixture()
    for entry in baseline["setups"]:
        setup = setups[entry["key"]]
        df = replay.fixture_frame(frames, entry["key"])
        sessions, note = replay.fired_window_sessions(
            df, setup["as_of"], marks_corpus._lps_spans(setup),
            setup.get("knowable_from"))
        got = [sessions[0].date().isoformat(), sessions[-1].date().isoformat()]
        assert got == entry["windows"][0], (
            f"{entry['key']}: fired window re-derives as {got} but the baseline "
            f"froze {entry['windows'][0]} — the acceptance criterion moved"
        )
        assert (note or None) == entry.get("window_clamp"), (
            f"{entry['key']}: clamp note re-derives as {note!r} but the "
            f"baseline froze {entry.get('window_clamp')!r}"
        )


def test_loader_refuses_malformed_marks(tmp_path):
    """A malformed or unrecognized mark must FAIL the load, never be skipped —
    a silently skipped mark shrinks the acceptance set (EC-7)."""
    good = {"ticker": "TEST", "source": "operator", "lps": ["2026-01-05", "2026-01-08"],
            "trigger": "2026-01-09", "rails_drawn": {"R": 10.0, "S": 9.0}}

    def _write(setup: dict) -> tuple:
        p = tmp_path / "marks.json"
        p.write_text(json.dumps({"setups": [setup]}), encoding="utf-8")
        return (str(p),)

    # Sanity: the well-formed mark loads.
    assert marks_corpus.load_corpus(_write(good))[0]["ticker"] == "TEST"

    unknown = dict(good, lps_windows=["2026-01-05"])  # typo'd key
    with pytest.raises(ValueError, match="unrecognized keys"):
        marks_corpus.load_corpus(_write(unknown))

    missing = {k: v for k, v in good.items() if k != "lps"}
    with pytest.raises(ValueError, match="missing required key 'lps'"):
        marks_corpus.load_corpus(_write(missing))

    bad_date = dict(good, trigger="09/01/2026")
    with pytest.raises(ValueError, match="not an ISO date"):
        marks_corpus.load_corpus(_write(bad_date))

    bad_ticker = dict(good, ticker="te st;")
    with pytest.raises(ValueError, match="strict\\s+grammar"):
        marks_corpus.load_corpus(_write(bad_ticker))

    inverted_rails = dict(good, rails_drawn={"R": 9.0, "S": 10.0})
    with pytest.raises(ValueError, match="R above S"):
        marks_corpus.load_corpus(_write(inverted_rails))

    unaddressable = dict(good, frame_digest="ab" * 32)  # digest without as_of
    with pytest.raises(ValueError, match="no\\s+as_of"):
        marks_corpus.load_corpus(_write(unaddressable))


def test_gate_can_actually_pass(monkeypatch):
    """Green-path bite: the guard must be able to say PASS against the REAL
    committed artifacts — a wiring regression that wedges it permanently red
    would otherwise be indistinguishable from a genuine bite. The stub fires
    exactly when a slice reaches a pinned hit's frozen first_fire, so this
    also smoke-covers the graduated window walk end to end (each pinned fire
    date must lie INSIDE the re-derived window)."""
    baseline = _load_baseline()
    fire_dates = {(s["ticker"], s["first_fire"])
                  for s in baseline["setups"] if s["status"] == "hit"}

    def fire_on_pinned_date(ticker, sliced, *args, **kwargs):
        if (ticker, sliced.index[-1].date().isoformat()) in fire_dates:
            return {"Setup": "LPS", "Score": 120.0, "Tier": "S"}
        return None

    monkeypatch.setattr(marks_corpus, "_evaluate_ticker", fire_on_pinned_date)
    assert marks_corpus.check_corpus() is True, (
        "check_corpus cannot reach PASS even when every pinned hit fires on "
        "its frozen date — the gate is wedged red (wiring regression)."
    )


def test_gate_bites_when_a_pinned_hit_regresses(monkeypatch):
    """Bite proof: the guard must FAIL when the engine stops firing on a
    pinned hit. Force the eval to never fire and assert ``check_corpus``
    returns False against the REAL committed baseline."""
    monkeypatch.setattr(marks_corpus, "_evaluate_ticker", lambda *a, **k: None)
    assert marks_corpus.check_corpus() is False, (
        "check_corpus returned True even though every pinned hit regressed — "
        "the guard is not actually gating on acceptance regressions."
    )


def test_gate_bites_when_an_expected_miss_converts(monkeypatch):
    """Bite proof (strict ratchet): an expected miss that starts firing must
    ALSO fail until the baseline is deliberately re-frozen — a silent behavior
    change is never good news until a human verifies the stage's evidence."""
    monkeypatch.setattr(
        marks_corpus, "_evaluate_ticker",
        lambda *a, **k: {"Setup": "LPS", "Score": 120.0, "Tier": "S"},
    )
    assert marks_corpus.check_corpus() is False, (
        "check_corpus returned True while expected misses fired — unexpected "
        "conversions must break the ratchet loudly, not pass silently."
    )


# ─────────────────────────────────────────────────────────────────────────────
# The population follows the operator (his ruling, 2026-09-08). These pin the
# half that had to SURVIVE that: the standard tracks his drawings, but a verdict
# is still about one specific drawing and still cannot move silently.
# ─────────────────────────────────────────────────────────────────────────────
def _setup(**over):
    base = {"ticker": "AAA", "as_of": "2026-04-01",
            "rails_drawn": {"R": 10.0, "S": 9.0},
            "lps": ["2026-03-20", "2026-03-25"], "trigger": "2026-04-01",
            "frame_digest": "deadbeef"}
    base.update(over)
    return base


def test_setup_digest_moves_when_the_DRAWING_moves():
    """The digest is the identity a pinned verdict belongs to. Every field the
    operator can redraw must change it, or a verdict about an old chart would be
    carried onto a new one."""
    base = marks_corpus.setup_digest(_setup())
    assert base == marks_corpus.setup_digest(_setup()), "digest is not deterministic"
    for field, moved in (
        ("rails_drawn", {"R": 10.5, "S": 9.0}),        # he moved R
        ("rails_drawn", {"R": 10.0, "S": 9.2}),        # he moved S
        ("lps", ["2026-03-21", "2026-03-25"]),         # he re-dated the shelf
        ("trigger", "2026-04-02"),                     # he moved his buy
        ("as_of", "2026-04-02"),
        ("frame_digest", "cafef00d"),                  # different bars
    ):
        assert marks_corpus.setup_digest(_setup(**{field: moved})) != base, (
            f"redrawing {field} left the digest unchanged — a stale verdict would carry"
        )


def test_setup_digest_ignores_fields_that_are_not_the_drawing():
    """Notes and free text are not the chart; churning them must not void a
    hard-won pinned verdict."""
    assert marks_corpus.setup_digest(_setup(notes="typo fixed")) == \
        marks_corpus.setup_digest(_setup())


def test_population_currency_passes_when_there_is_no_marks_db(monkeypatch):
    """CI and any hermetic checkout have no calibration DB. They grade the
    committed fixture; only a machine holding his drawings can judge currency.
    An absent DB must never be reported as drift."""
    import database
    monkeypatch.setattr(database, "_DB_PATH", "/nonexistent/chrollo/marks.db")
    ok, note = marks_corpus.population_is_current("whatever")
    assert ok is True
    assert "not checked" in note


def test_population_currency_fails_on_a_stale_corpus(monkeypatch):
    """The heart of his ruling: a corpus built from drawings he has since
    changed must FAIL, not advise. It sat advisory for six weeks while the
    standard demanded three marks he had deleted."""
    monkeypatch.setattr(marks_corpus, "population_is_current",
                        lambda fp: (False, "THE CORPUS IS STALE: pretend drift"))
    assert marks_corpus.check_corpus() is False, (
        "check_corpus passed against a stale corpus — the population no longer "
        "tracks the operator and the gate did not say so"
    )


def test_a_freshly_drawn_mark_never_needs_a_hand_written_stage():
    """Drawing a chart must not break his gate. A mark absent from the previous
    baseline that the engine cannot read enters MEASURED — pinned so it cannot
    start firing unannounced, but never blocking the rebuild on someone
    hand-writing a STAGE_TAGS entry first."""
    assert marks_corpus.NEW_MARK_STAGE not in marks_corpus.STAGE_TAGS.values(), (
        "the new-mark stage leaked into the hand-curated tags — it must only ever "
        "be assigned automatically"
    )
    committed = _load_baseline()
    unreviewed = [s for s in committed["setups"]
                  if s.get("stage") == marks_corpus.NEW_MARK_STAGE]
    reviewed = [s for s in committed["setups"]
                if s["status"] == "miss" and s.get("stage") != marks_corpus.NEW_MARK_STAGE]
    # The reviewed population always exists; the unreviewed one exists only
    # while a freshly drawn mark the engine cannot read is waiting for his eye.
    # At the 2026-09-13 re-seal every such mark had been reviewed by measurement
    # (MDT: universe-gate; ST: lps-ceiling) and the one newly drawn mark
    # (SYRE:2026-02-19) fires, so an EMPTY unreviewed set is the honest state,
    # not a dark path: the assignment is exercised by the build whenever a new
    # unread mark appears, and pinned here when it does.
    assert reviewed, "no reviewed misses in the baseline — the split is meaningless"
    for s in unreviewed:
        assert s["status"] == "miss", f"{s['key']}: an unreviewed new mark must be pinned as a miss"
    for s in reviewed:
        assert s["stage"] in marks_corpus.STAGE_TAGS.values(), (
            f"{s['key']} carries stage {s['stage']!r}, which no STAGE_TAGS entry names"
        )


def test_every_pinned_verdict_records_the_drawing_it_is_about():
    """Without this the ratchet cannot tell 'the engine regressed' from 'he
    redrew the chart', which is the failure the 2026-09-08 rebuild fixed."""
    for s in _load_baseline()["setups"]:
        assert s.get("setup_digest"), f"{s['key']} pins a verdict with no drawing digest"


def test_deleted_marks_are_gone_from_the_stage_tags():
    """Two of the five 'expected misses' were charts he had DELETED, so the
    engine was permanently excused for missing ground truth that no longer
    existed. Every tag must name a mark that is still in the corpus."""
    keys = {marks_corpus.setup_key(s) for s in marks_corpus.load_corpus()}
    orphans = sorted(set(marks_corpus.STAGE_TAGS) - keys)
    assert not orphans, (
        f"STAGE_TAGS still excuses marks the operator no longer draws: {orphans}"
    )


def test_an_empty_marks_db_is_not_read_as_the_operator_deleting_everything():
    """The pytest session points CHROLLO_DB_PATH at a throwaway file whose
    migrations create an EMPTY calibration_marks table. Reading that as "he
    deleted every drawing" is drift, and it wedged the whole suite red until it
    was fixed. A DB with no marks in it simply is not his."""
    ok, note = marks_corpus.population_is_current("a-fingerprint-nothing-will-match")
    assert ok is True, (
        "the currency check judged a database with no drawings in it — under "
        f"pytest that is the throwaway DB, not the operator's archive ({note})"
    )
