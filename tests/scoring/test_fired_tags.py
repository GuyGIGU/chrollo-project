"""The fired-tags resolver + closed-set battery (build task 10).

EC-22 adapted for the chip vocabulary: every registered tag id must be
producible by the REAL resolver under a legal configuration (the demoted
rs/uptrend chips prove their rules with monkeypatched non-zero caps, and
their dead-by-design state at cap 0 is pinned separately). EC-19 adapted
for the JSON cell: unknown ids are refused at the ONE write producer.
"""
import json
import sys

import pytest

from _paths import REPO_ROOT as ROOT
sys.path.insert(0, str(ROOT))

from config import settings
from engine_alpha.scoring import taxonomy
from engine_alpha.scoring.scoring import ta_grade_archive_values
from engine_alpha.scoring.tags import resolve_fired_tags


def _row(sub=None, **facts):
    row = {"_sub_scores": sub or {}}
    row.update({("_" + k): v for k, v in facts.items()})
    return row


def _fired_ids(row):
    return [e["id"] for e in resolve_fired_tags(row, prefixed=True)]


def _condition_for(tag, monkeypatch):
    """A minimal row firing exactly this tag's rule, hand-built per rule."""
    caps = taxonomy.caps()
    if tag.rule == "fraction":
        cap = caps.get(tag.term, 0.0)
        if cap <= 0:
            # Demoted terms: prove the RULE under a legal (non-zero) cap.
            monkeypatch.setattr(settings, tag.term and
                                next(t.cap_setting for t in taxonomy.REGISTRY
                                     if t.key == tag.term), 10)
            cap = 10.0
        return _row(sub={tag.term: tag.fraction * cap})
    if tag.rule == "flag":
        return _row(**{tag.field: 1})
    if tag.rule == "gt_setting":
        return _row(**{tag.field: float(getattr(settings, tag.setting)) + 0.1})
    if tag.rule == "lt_setting":
        return _row(**{tag.field: float(getattr(settings, tag.setting)) - 0.1})
    if tag.rule == "ge_setting":
        if tag.field == "traversal_density":
            # Derived fact: supply the raw counts, not the ratio.
            need = float(getattr(settings, tag.setting))
            return _row(trav_n_full_traversals=need * 10, trav_n_swings=10)
        return _row(**{tag.field: float(getattr(settings, tag.setting))})
    if tag.rule == "eq":
        return _row(**{tag.field: tag.value})
    if tag.rule == "any_gt0":
        return _row(**{tag.fields[0]: 0.2})
    raise AssertionError(f"unhandled rule kind {tag.rule!r}")


def test_every_registered_tag_id_is_producible(monkeypatch):
    """EC-22: each id fires end-to-end through the real resolver under a
    legal configuration — an id no rule can produce is an advertised
    capability the system does not have."""
    for tag in taxonomy.TAGS:
        row = _condition_for(tag, monkeypatch)
        assert tag.id in _fired_ids(row), (
            f"tag {tag.id!r} not producible by its own rule")


def test_each_rule_kind_refuses_a_present_finite_wrong_side_fact():
    """2026-08-08 review, finding 14: every comparison KIND gets one PRESENT,
    FINITE, wrong-side case — pre-fix no committed row ever sat on the
    refusing side of gt/lt or a non-demoted fraction, so a resolver mutated
    to 'fire whenever the fact is present and finite' stayed suite-green
    while every chip fired on every setup. One case per KIND (Beck
    composability), asserting the id ABSENT from the fired list."""
    caps = taxonomy.caps()
    # fraction at firesAt 1.00: just under the cap refuses.
    assert caps["lps_tightness"] > 0
    assert "tight_lps" not in _fired_ids(
        _row(sub={"lps_tightness": caps["lps_tightness"] - 0.01}))
    # fraction at firesAt 0.80: just under fraction × cap refuses.
    assert "tight_box" not in _fired_ids(
        _row(sub={"box_tightness": 0.80 * caps["box_tightness"] - 0.01}))
    # gt_setting: a fact AT the threshold exactly refuses (strict >)...
    assert "heavy_resistance" not in _fired_ids(
        _row(r_touch_vol_z=float(settings.TOUCH_VOL_Z_HEAVY_R)))
    # ...and one clearly below.
    assert "demand_at_s" not in _fired_ids(
        _row(s_touch_vol_z=float(settings.TOUCH_VOL_Z_SPRING) - 0.5))
    # lt_setting: a fact above the threshold refuses.
    assert "no_supply" not in _fired_ids(
        _row(r_touch_vol_z=float(settings.TOUCH_VOL_Z_NO_SUPPLY) + 0.5))
    # ge_setting (derived density): just under the setting refuses.
    need = float(settings.TRAVERSAL_QUALITY_DENSITY_FULL)
    assert "worked_equilibrium" not in _fired_ids(
        _row(trav_n_full_traversals=(need - 0.05) * 10, trav_n_swings=10))
    # eq: a present, different label refuses.
    assert "weak_monthly" not in _fired_ids(_row(htf_m_trend_state="range"))
    # flag: a present falsy fact refuses.
    assert "phase_d" not in _fired_ids(_row(phase_d_inner=0))
    # any_gt0: present zeros refuse.
    assert "last_supper" not in _fired_ids(
        _row(lps_stretch_box=0.0, lps_stretch_atr=0.0))


def test_zero_cap_fraction_chips_are_dead_by_design():
    """The demoted rs/uptrend chips can NEVER fire while their caps are 0 —
    by rule (cap > 0 required), not by the stale-JS-cap accident. Even an
    absurd point value cannot fire them."""
    row = _row(sub={"rs_bonus": 100.0, "uptrend_bonus": 100.0})
    fired = _fired_ids(row)
    assert "strong_rs" not in fired and "uptrend" not in fired


def test_density_rule_is_linked_to_its_settings_twin(monkeypatch):
    """worked_equilibrium reads TRAVERSAL_QUALITY_DENSITY_FULL — never an
    unlinked 0.33 copy: moving the setting moves the chip."""
    row = _row(trav_n_full_traversals=5, trav_n_swings=10)   # density 0.5
    assert "worked_equilibrium" in _fired_ids(row)
    monkeypatch.setattr(settings, "TRAVERSAL_QUALITY_DENSITY_FULL", 0.6)
    assert "worked_equilibrium" not in _fired_ids(row)


def test_absent_or_nonfinite_facts_never_fire():
    """Absence is never evidence: missing, None, and NaN facts fire nothing;
    an empty row resolves to the honest empty list (not None)."""
    assert resolve_fired_tags(_row(), prefixed=True) == []
    row = _row(r_touch_vol_z=float("nan"), lps_stretch_box=None,
               sub={"base_age": float("nan")})
    assert _fired_ids(row) == []
    # The flag kind's non-finite leg (EC-34 one-case-per-rule-KIND): a NaN
    # flag fact must read as absent, never as truthy evidence.
    assert "phase_d" not in _fired_ids(_row(phase_d_inner=float("nan")))
    assert "phase_d" in _fired_ids(_row(phase_d_inner=1))


def test_fired_entries_carry_their_detail_facts():
    """The tooltip interpolations the JS used to re-derive arrive as fields
    on the fired entry — the wire carries the numbers, resolved."""
    row = _row(bin_c_present=1, bin_c_type="spring",
               bin_c_undercut_atr=0.42, bin_c_recovery_bars=3)
    entry = next(e for e in resolve_fired_tags(row, prefixed=True)
                 if e["id"] == "phase_c_test")
    assert entry["detail"]["bin_c_undercut_atr"] == 0.42
    assert entry["detail"]["bin_c_type"] == "spring"


def test_numpy_scalar_detail_facts_unwrap_to_natives():
    """A leaked numpy scalar must land as a native value: the strict
    allow_nan=False archive write crashes on int64/bool_, and a numpy NaN
    must hit the same non-finite quarantine as a native one."""
    np = pytest.importorskip("numpy")
    row = _row(bin_c_present=np.bool_(True), bin_c_type="spring",
               bin_c_undercut_atr=np.float64("nan"),
               bin_c_recovery_bars=np.int64(3))
    entry = next(e for e in resolve_fired_tags(row, prefixed=True)
                 if e["id"] == "phase_c_test")
    assert entry["detail"]["bin_c_recovery_bars"] == 3
    assert type(entry["detail"]["bin_c_recovery_bars"]) is int
    assert entry["detail"]["bin_c_undercut_atr"] is None
    json.dumps(entry, allow_nan=False)  # the archive write's exact contract


def test_resolver_order_is_registry_order_and_twin_stable():
    """Deterministic REGISTRY order (display ordering stays presentational),
    and the seed twin's bare-key row resolves identically."""
    row = _row(sub={"lps_tightness": taxonomy.caps()["lps_tightness"]},
               bin_c_present=1, htf_m_trend_state="down")
    fired = _fired_ids(row)
    registry_order = [t.id for t in taxonomy.TAGS if t.id in fired]
    assert fired == registry_order
    bare = {"sub_scores": row["_sub_scores"], "bin_c_present": 1,
            "htf_m_trend_state": "down"}
    assert resolve_fired_tags(bare, prefixed=False) == \
        resolve_fired_tags(row, prefixed=True)


def test_extraction_serializes_and_refuses_unknown_ids():
    """EC-19 for the JSON cell: the ONE write producer serializes the list
    compactly and refuses any id outside the closed set; NULL rides through
    when dark; [] round-trips as resolved-nothing-fired."""
    fired = [{"id": "tight_lps", "detail": {}}]
    out = ta_grade_archive_values({"fired_tags": fired}.get, prefixed=False)
    assert json.loads(out["fired_tags"]) == fired
    empty = ta_grade_archive_values({"fired_tags": []}.get, prefixed=False)
    assert empty["fired_tags"] == "[]"
    dark = ta_grade_archive_values((lambda _k: None), prefixed=False)
    assert dark["fired_tags"] is None
    with pytest.raises(ValueError, match="registry-known"):
        ta_grade_archive_values(
            {"fired_tags": [{"id": "totally_bogus", "detail": {}}]}.get,
            prefixed=False)


def test_weak_monthly_is_both_chip_and_grade_warning(monkeypatch):
    """The settled disposition (2026-08-06 HTF ruling): ONE fact — a monthly
    downtrend — fires the warning chip AND enters the grade's warning
    mechanism (neutral 1.0 until the operator's A/B); a missing HTF read
    fires neither."""
    from engine_alpha.scoring.scoring import compose_ta_grade
    assert "weak_monthly" in _fired_ids(_row(htf_m_trend_state="down"))
    assert "weak_monthly" not in _fired_ids(_row(htf_m_trend_state="up"))
    down = compose_ta_grade({}, htf={"htf_m_trend_state": "down"})
    assert down["ta_grade_warnings"] == {
        "weak_monthly": settings.TA_WARN_WEAK_MONTHLY}
    absent = compose_ta_grade({}, htf=None)
    assert "weak_monthly" not in absent["ta_grade_warnings"]
