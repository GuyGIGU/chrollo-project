"""Shared mark-validity judgment guards (Calibration at Scale, Task 2).

Hand-built payloads with expected verdicts reasoned in advance — the module is
the ONE check the CRUD write path and the harness load path both import, so
these cases are the contract. Plus a drift pin: the frozen DDL CHECKs in
models.py must name exactly the closed sets this module owns.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "webapp" / "backend"
sys.path.insert(0, str(ROOT))
sys.path.insert(1, str(BACKEND_DIR))

import marks_validity  # noqa: E402
from marks_validity import EVENT_TYPES, MARK_VERDICTS, validate_mark  # noqa: E402


def _payload(**overrides):
    fields = dict(
        ticker="BODI",
        as_of_date="2026-04-15",
        verdict="box",
        resistance=12.40,
        support=10.15,
        box_start_date="2025-12-12",
        box_end_date="2026-04-15",
        data_regime="as_traded",
        engine_config_version="test-config",
        anchor_close=11.02,
        frame_digest="a" * 64,
        events=[],
    )
    fields.update(overrides)
    return fields


def test_full_positive_mark_is_valid():
    payload = _payload(events=[{
        "event_type": "phase_c", "start_date": "2026-02-10",
        "end_date": "2026-03-20", "tip_date": "2026-03-02", "tip_price": 6.77,
        "source": "extraction",
    }])
    assert validate_mark(payload) == []


def test_negative_mark_is_valid_without_geometry():
    assert validate_mark(_payload(
        verdict="no_structure", resistance=None, support=None,
        box_start_date=None, box_end_date=None)) == []


def test_negative_mark_with_geometry_is_ambiguous():
    problems = validate_mark(_payload(verdict="engine_wrong",
                                      box_start_date=None, box_end_date=None))
    assert any("carries geometry" in p for p in problems)


def test_box_requires_rails_and_span():
    assert any("rails" in p for p in validate_mark(_payload(resistance=None)))
    assert any("box_start_date" in p for p in validate_mark(_payload(box_start_date=None)))


def test_inverted_rails_and_span_rejected():
    assert validate_mark(_payload(resistance=10.15, support=12.40))
    assert any("inverted" in p for p in validate_mark(
        _payload(box_start_date="2026-04-15", box_end_date="2025-12-12")))


def test_box_end_after_as_of_rejected():
    # The frame's last bar is the as-of date; a span reaching past it marks
    # bars the operator never saw.
    assert any("after as_of_date" in p for p in validate_mark(
        _payload(box_end_date="2026-05-01")))


def test_strict_ticker_grammar_rejects():
    for bad in ("bodi", "", "A" * 11, "../BODI", "BODI;--", "CON:"):
        assert any("grammar" in p for p in validate_mark(_payload(ticker=bad))), bad
    for good in ("A", "BRK.B", "NGL-B", "BODI"):
        assert not any("grammar" in p for p in validate_mark(_payload(ticker=good))), good


def test_dates_are_strict_single_format():
    # Lenient parsing would read ambiguous day/month input differently than
    # the operator meant — exactly YYYY-MM-DD or rejected.
    assert validate_mark(_payload(as_of_date="04/15/2026"))
    assert validate_mark(_payload(as_of_date="2026-4-15"))


def test_provenance_is_required():
    assert any("data_regime" in p for p in validate_mark(_payload(data_regime="")))
    assert any("anchor_close" in p for p in validate_mark(_payload(anchor_close=None)))
    assert any("anchor_close" in p for p in validate_mark(_payload(anchor_close=float("nan"))))


def test_frame_digest_is_required_provenance():
    # A mark without its frame's digest can never be replayed — refused at
    # birth, never silently excluded from every future denominator.
    for bad in (None, "", "not-a-digest", "A" * 64, "a" * 63):
        assert any("frame_digest" in p
                   for p in validate_mark(_payload(frame_digest=bad))), bad


def test_label_is_bounded_and_whitespace_free():
    assert any("label" in p for p in validate_mark(_payload(label="x" * 41)))
    assert any("label" in p for p in validate_mark(_payload(label=" lps")))
    assert validate_mark(_payload(label="second box")) == []


def test_rails_source_closed_set():
    assert any("rails_source" in p
               for p in validate_mark(_payload(rails_source="scraper")))


def test_knowable_from_date_rules():
    assert any("knowable_from_date" in p
               for p in validate_mark(_payload(knowable_from_date="4/1/2026")))
    assert any("after as_of_date" in p
               for p in validate_mark(_payload(knowable_from_date="2026-05-01")))
    assert validate_mark(_payload(knowable_from_date="2026-04-01")) == []


def test_event_rules():
    base = {"event_type": "lps", "start_date": "2026-04-09", "end_date": "2026-04-15"}
    assert validate_mark(_payload(events=[base])) == []
    assert validate_mark(_payload(events=[{**base, "event_type": "breakout"}]))
    assert validate_mark(_payload(events=[{**base, "source": "scraper"}]))
    assert validate_mark(_payload(events=[{**base, "end_date": "2026-04-01"}]))
    assert validate_mark(_payload(events=[{**base, "tip_date": "2026-05-01"}]))
    assert validate_mark(_payload(events=[{**base, "end_date": "2026-05-01"}]))


def test_ddl_checks_pin_the_same_closed_sets():
    """The frozen CHECK constraints in models.py must name exactly the sets
    this module owns — set EQUALITY in both directions: a module set the DDL
    doesn't know is drift, and a DDL enum wider than the module is a weaker
    backstop than this test claims exists."""
    import re

    import models
    ddl = " ".join(
        str(c.sqltext)
        for table in (models.CalibrationMark, models.CalibrationMarkEvent)
        for c in table.__table_args__
        if hasattr(c, "sqltext")
    ).lower()

    def enum_of(column: str) -> set:
        m = re.search(rf"{column}\s+in\s+\(([^)]*)\)", ddl)
        assert m, f"no closed-set CHECK found for {column}"
        return set(re.findall(r"'([^']*)'", m.group(1)))

    assert enum_of("verdict") == set(MARK_VERDICTS)
    assert enum_of("event_type") == set(EVENT_TYPES)
