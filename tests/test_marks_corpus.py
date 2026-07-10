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

_KNOWN_STAGES = {"holding-shelf-lps", "band-vs-excursion", "under-investigation"}


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
    frame; statuses are hit/miss only; every miss names a known converting
    stage; and the gate protects a non-trivial set."""
    setups = marks_corpus.load_corpus()
    baseline = _load_baseline()
    frames, _ = marks_corpus._load_fixture()

    keys = {marks_corpus.setup_key(s) for s in setups}
    baseline_keys = {s["key"] for s in baseline["setups"]}
    assert keys == baseline_keys, (
        f"corpus/baseline key mismatch: only-in-corpus={sorted(keys - baseline_keys)} "
        f"only-in-baseline={sorted(baseline_keys - keys)} — re-freeze deliberately."
    )
    missing_frames = [s["ticker"] for s in setups
                      if s["ticker"] not in frames or frames[s["ticker"]].empty]
    assert not missing_frames, f"baseline setups without fixture frames: {missing_frames}"

    for entry in baseline["setups"]:
        assert entry["status"] in ("hit", "miss"), f"{entry['key']}: bad status {entry['status']!r}"
        if entry["status"] == "miss":
            assert entry.get("stage") in _KNOWN_STAGES, (
                f"{entry['key']}: frozen miss without a known converting stage "
                f"({entry.get('stage')!r}) — the ratchet must explain every miss."
            )
    assert len(baseline["setups"]) >= 11, (
        f"suspiciously small corpus ({len(baseline['setups'])} setups)"
    )
    hits = sum(1 for s in baseline["setups"] if s["status"] == "hit")
    assert hits >= 6, f"suspiciously few pinned hits ({hits}) — the gate protects the hits"


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
