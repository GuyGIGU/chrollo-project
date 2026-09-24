"""Shared mark-validity judgment guards (Calibration at Scale, Task 2).

Hand-built payloads with expected verdicts reasoned in advance — the module is
the ONE check the CRUD write path and the harness load path both import, so
these cases are the contract. Plus a drift pin: the frozen DDL CHECKs in
models.py must name exactly the closed sets this module owns.
"""
import sys

from _paths import REPO_ROOT as ROOT
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


def test_rail_anchors_optional_but_judged_when_present():
    # Anchors are optional (pre-anchor marks have none) …
    assert validate_mark(_payload()) == []
    # … valid when well-formed …
    assert validate_mark(_payload(r_anchor_date="2026-01-10",
                                  s_anchor_date="2026-02-03",
                                  first_rail="resistance")) == []
    # … and judged when present: shape, at/before as-of, closed first_rail set.
    assert any("not YYYY-MM-DD" in p for p in validate_mark(
        _payload(r_anchor_date="Jan 10 2026")))
    assert any("after as_of_date" in p for p in validate_mark(
        _payload(s_anchor_date="2026-05-01")))
    assert any("first_rail" in p for p in validate_mark(
        _payload(first_rail="upper")))


def test_negative_mark_with_anchors_is_ambiguous():
    problems = validate_mark(_payload(
        verdict="no_structure", resistance=None, support=None,
        box_start_date=None, box_end_date=None, first_rail="support"))
    assert any("carries geometry (first_rail)" in p for p in problems)


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


def test_sos_is_a_plain_span_needing_no_band():
    """The SOS mark stores only the launch-low -> swing-top span: "decisive" is
    ground covered over days (operator ruling 2026-08-26), and the two prices
    re-derive from the frozen frame, the way the rail anchors already do."""
    assert validate_mark(_payload(events=[{
        "event_type": "sos", "start_date": "2026-03-02", "end_date": "2026-03-13",
    }])) == []


def test_last_supper_is_a_plain_span():
    """The Last Supper is a swing of one or more bars — the trapping run-up and
    the deep correction that follows. A span; no band, no required tip."""
    assert validate_mark(_payload(events=[{
        "event_type": "last_supper", "start_date": "2026-02-02",
        "end_date": "2026-02-06",
    }])) == []


def test_mini_consolidation_requires_a_well_formed_price_band():
    base = {"event_type": "mini_consolidation",
            "start_date": "2026-04-01", "end_date": "2026-04-10"}
    # A box with no top and no bottom is not a box.
    assert any("needs a price band" in p
               for p in validate_mark(_payload(events=[base])))
    # Half a band is a drawing bug, never a band.
    assert any("BOTH" in p for p in
               validate_mark(_payload(events=[{**base, "band_high": 12.40}])))
    assert any("above band_low" in p for p in validate_mark(
        _payload(events=[{**base, "band_high": 10.15, "band_low": 12.40}])))
    assert any("positive" in p for p in validate_mark(
        _payload(events=[{**base, "band_high": 12.40, "band_low": 0}])))
    assert validate_mark(_payload(events=[
        {**base, "band_high": 12.40, "band_low": 10.15}])) == []


def test_a_band_drawn_on_a_span_type_is_still_shape_checked():
    """Only the mini-consolidation REQUIRES a band, but a band that turns up on
    any other type must still be well-formed — a half band is a UI defect."""
    lps = {"event_type": "lps", "start_date": "2026-04-09", "end_date": "2026-04-15"}
    assert any("BOTH" in p for p in
               validate_mark(_payload(events=[{**lps, "band_low": 10.15}])))


def test_the_marking_ui_offers_exactly_the_types_the_backend_accepts():
    """EC-3 across the language boundary: the marking UI keeps its own copy of
    the vocabulary (it builds the toolbar from it). A type the backend accepts
    but the UI never offers is dead; a type the UI offers but the backend
    refuses is a button that always fails to save. The Python-to-Python DDL pin
    above cannot see this seam."""
    import re

    js = (ROOT / "webapp" / "frontend" / "src" / "features" / "calibration" / "model"
          / "calibrationMarking.js").read_text(encoding="utf-8")
    m = re.search(r"MARK_EVENT_TYPES\s*=\s*\[(.*?)\]", js, re.DOTALL)
    assert m, "MARK_EVENT_TYPES not found in calibrationMarking.js"
    assert set(re.findall(r"'([^']*)'", m.group(1))) == set(EVENT_TYPES)


def test_last_supper_is_a_descriptive_chip_not_a_warning():
    """Operator ruling 2026-08-26: a Last Supper is a deep correction stocks
    often pop off AFTER — it must never READ as a defect. It costs no points
    either way (it is not a registered grade warning); this pins the DISPLAY
    side, which is what actually trained the eye."""
    from engine_alpha.scoring import scoring, taxonomy

    spec = next(t for t in taxonomy.TAGS if t.id == "last_supper")
    assert spec.warning is False
    # ...and it is absent from the two warnings that DO discount the grade.
    assert "last_supper" not in scoring._ta_grade_warnings(None, None)


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


# ── Trigger (the operator's buy — the LPS-high breakout) ─────────────
# It inverts the event contract: a FORWARD point (>= as_of), one per box,
# requiring an LPS and landing strictly after that LPS's last bar.

_LPS = {"event_type": "lps", "start_date": "2026-04-09", "end_date": "2026-04-14"}


def _triggered(**over):
    p = _payload(events=[dict(_LPS)], trigger_date="2026-04-16", trigger_price=12.55)
    p.update(over)
    return p


def test_a_well_formed_trigger_on_a_box_with_an_lps_is_valid():
    assert validate_mark(_triggered()) == []
    # And a box with an LPS but NO trigger is equally valid (null = no buy yet).
    assert validate_mark(_payload(events=[dict(_LPS)])) == []


def test_trigger_requires_an_lps_event():
    assert any("requires an LPS" in p for p in validate_mark(_triggered(events=[])))


def test_trigger_must_land_after_the_last_lps_bar():
    # as-of == LPS end == trigger isolates the "after the last LPS bar" rule.
    problems = validate_mark(_triggered(
        as_of_date="2026-04-15", box_end_date="2026-04-15",
        events=[{**_LPS, "end_date": "2026-04-15"}], trigger_date="2026-04-15"))
    assert any("after the last LPS bar" in p for p in problems)


def test_trigger_may_precede_as_of_after_the_lps():
    # Relaxed 2026-07-22: the buy only needs to be strictly after the last LPS
    # bar; it MAY sit before the as-of (the operator marks the real breakout day
    # and locks the snapshot separately). LPS ends 04-14, as-of 04-20, buy 04-16.
    assert validate_mark(_triggered(
        as_of_date="2026-04-20", trigger_date="2026-04-16")) == []
    # A buy at/before the last LPS bar is still rejected — that rule is kept.
    assert any("after the last LPS bar" in p
               for p in validate_mark(_triggered(
                   as_of_date="2026-04-20", trigger_date="2026-04-14")))


def test_trigger_date_and_price_must_be_paired():
    assert any("set together" in p for p in validate_mark(_triggered(trigger_price=None)))
    assert any("set together" in p for p in validate_mark(_triggered(trigger_date=None)))


def test_trigger_price_must_be_positive_finite():
    for bad in (0, -3.0, float("nan")):
        assert any("trigger_price" in p
                   for p in validate_mark(_triggered(trigger_price=bad))), bad


def test_trigger_date_is_strict_iso():
    assert any("trigger_date" in p and "YYYY-MM-DD" in p
               for p in validate_mark(_triggered(trigger_date="2026-4-16")))


def test_a_negative_verdict_carries_no_trigger():
    problems = validate_mark(_payload(
        verdict="no_structure", resistance=None, support=None,
        box_start_date=None, box_end_date=None, events=[],
        trigger_date="2026-04-16", trigger_price=12.55))
    assert any("carries a trigger" in p for p in problems)
