"""Flag-off tripwires + key-set snapshot at the WIRE boundary (TA-grade build
task 2).

The scorer tripwire (tests/test_scoring.py::test_ta_score_v2_flag_off_leaks_no_v2_keys)
guards score_setup's result dict; this file guards the second leak point — the
serialized per-ticker dashboard payload (output/dashboard._extract_chart_data),
which previously had no flag-off snapshot at all. It drives the REAL payload
builder on a synthetic frame (the established house pattern from
tests/test_fetch_repair.py) — never a booted server. The sector-ETF lookup is
the one monkeypatched boundary (external lookup + a disk cache write).

The key-set snapshot is deliberately exact: adding or removing a wire key with
TA_SCORE_V2 off must be a conscious edit here, never silent drift — that is
EC-8's byte-identical promise expressed at the boundary the frontend consumes.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(1, str(ROOT / "webapp" / "backend"))

from config import settings
from engine_alpha.scoring import taxonomy
from engine_alpha.scoring.scoring import TA_GRADE_COLUMN_SQL
from output import dashboard as dashboard_module


def _payload(monkeypatch, *, v2_overlay=None, flag=False):
    """The per-ticker payload exactly as a scan would serialize it; an
    optional overlay injects flag-on v2 result fields onto the row.

    NOTE (2026-08-08 review): the ``flag`` parameter mirrors the production
    ambient state only — the wire itself is NOT flag-gated; its v2 block
    keys on ROW CONTENT (``_ta_grade`` presence). The leak chain is: the
    cascade guards the row, this file's snapshot guards the serialization.
    Do not treat the wire as a second flag gate."""
    dates = pd.date_range("2026-01-01", periods=10, freq="B", name="Date")
    data = pd.DataFrame({
        "Open": np.linspace(10, 11, len(dates)),
        "High": np.linspace(10.5, 11.5, len(dates)),
        "Low": np.linspace(9.5, 10.5, len(dates)),
        "Close": np.linspace(10.2, 11.2, len(dates)),
        "Volume": np.linspace(1000, 1100, len(dates)),
    }, index=dates)
    sub_scores = {
        "box_tightness": 10.0, "touch_density": 12.0, "traversal_quality": 4.0,
        "atr_squeeze": 3.0, "lps_tightness": 11.0, "vol_contraction": 9.0,
        "base_age": 8.0, "uptrend_bonus": 0.0, "rs_bonus": 0.0,
        "high_proximity": 4.0, "breadth_bonus": 5.0, "contraction": 6.0,
        "ascending_support": 3.0, "adr": 4.0, "setup_quality": 5.0,
    }
    row = {
        "Ticker": "AAA",
        "Tier": "A",
        "Score": 100,
        "Setup": "LPS",
        "Current Price": 11.2,
        "_trigger_price": 11.6,
        "_R": 11.5,
        "_S": 9.5,
        "_base_len": 8,
        "_lps_len": 2,
        "_lps_offset": 0,
        "_r_anchor_bar": 2,
        "_s_anchor_bar": 3,
        "_sub_scores": sub_scores,
    }
    row.update(v2_overlay or {})
    results = pd.DataFrame([row])
    monkeypatch.setattr(dashboard_module, "_sector_etf_for_ticker",
                        lambda *_args: None)
    monkeypatch.setattr(settings, "TA_SCORE_V2", flag)
    return dashboard_module._extract_chart_data(data, results, ["AAA"])["AAA"]


def test_wire_flag_off_leaks_no_v2_keys(monkeypatch):
    """No reserved v2 key may reach the wire — top level or sub_scores — while
    TA_SCORE_V2 is off. Derives from the ONE settled vocabulary (task 1)."""
    chart = _payload(monkeypatch)
    for k in taxonomy.V2_RESULT_KEYS:
        assert k not in chart, (
            f"v2 key {k!r} leaked onto the flag-off wire payload")
        assert k not in chart["sub_scores"], (
            f"v2 key {k!r} leaked into flag-off sub_scores")


def test_wire_sub_scores_are_exactly_the_always_emitted_projection(monkeypatch):
    """The served sub_scores key set equals the ALWAYS-EMITTED projection —
    the wire cannot silently drop a registered term or invent an
    unregistered one. Pinned against always_emitted_terms(), NOT
    emitted_keys(): flag-on the two diverge (spring + story join
    emitted_keys), and the old pin held only because this test forces the
    flag off (2026-08-08 review). Proven under BOTH flag states."""
    for flag in (False, True):
        chart = _payload(monkeypatch, flag=flag,
                         v2_overlay=_V2_OVERLAY if flag else None)
        assert set(chart["sub_scores"]) == {
            t.key for t in taxonomy.always_emitted_terms()}


# The exact flag-off per-ticker key set (150 keys: 149 captured 2026-08-08 at
# the task-2 baseline, + zone_coverage 2026-08-10). Sorted. Changing the wire
# contract flag-off means editing this tuple deliberately in the same change —
# never drifting past it.
FLAG_OFF_WIRE_KEYS = (
    "R", "S",
    "_has_mini_consolidation",
    "_lps_zone_end_date", "_lps_zone_high", "_lps_zone_low",
    "_lps_zone_start_date",
    "_phase_a_end_date", "_phase_a_start_date", "_phase_b_start_date",
    "_phase_c_event_date", "_phase_d_start_date",
    "_scope_confidence",
    "adr_pct", "ascending_support_quality", "base_len",
    "bin_b_cog_corr", "bin_b_cog_crossings", "bin_b_cog_end", "bin_b_cog_rng",
    "bin_c_event_bar", "bin_c_event_date", "bin_c_present",
    "bin_c_recovery_bar", "bin_c_recovery_bars", "bin_c_spring_vol_z",
    "bin_c_time_loc", "bin_c_type", "bin_c_undercut_atr",
    "bin_d_ascending_support_quality", "bin_d_boundary_source",
    "bin_d_higher_low_frac", "bin_d_start_bar", "bin_d_support_slope_atr",
    "bin_d_vs_b_support_quality_delta",
    "candles",
    "contraction_count", "contraction_quality", "contraction_vol_trend",
    "days_to_earnings",
    "elected_pool", "election_trace",
    "event_map_alternations", "event_map_completed_r", "event_map_completed_s",
    "event_map_episode_nan_bars", "event_map_episode_profile",
    "event_map_episodes", "event_map_n_committed", "event_map_n_labels",
    "event_map_n_swings", "event_map_pre_box_trend",
    "event_map_story_admitted", "event_map_terminal_drift",
    "event_map_terminal_posture",
    # + zone_coverage 2026-08-10 (the geometry companion — deliberate edit)
    "event_map_zone_coverage",
    "final_contraction_depth",
    "fund_earnings_surprise", "fund_eps_growth_accel", "fund_eps_growth_yoy",
    "fund_sales_growth_yoy",
    "higher_low_frac",
    "htf_m_box_r", "htf_m_box_s", "htf_m_box_width", "htf_m_daily_nested",
    "htf_m_in_consol", "htf_m_phase", "htf_m_reaccum", "htf_m_stage2",
    "htf_m_trend_state",
    "htf_w_box_r", "htf_w_box_s", "htf_w_box_width", "htf_w_daily_nested",
    "htf_w_in_consol", "htf_w_phase", "htf_w_reaccum", "htf_w_stage2",
    "htf_w_trend_state",
    "inner_R", "inner_S", "inner_box_width", "inner_climax_bar",
    "inner_end_bar", "inner_reaction_bar", "inner_reaction_bars",
    "inner_reaction_pct", "inner_search_start_bar", "inner_source",
    "inner_start_bar",
    "last_supper_pullback_from_extension_pct", "last_supper_reclaim_quality",
    "last_supper_source_box_age",
    "lps_anchor_bar", "lps_anchor_date", "lps_descent_frac", "lps_first_high",
    "lps_high_descent_frac", "lps_high_extension_atr",
    "lps_high_extension_box", "lps_in_inner", "lps_last_low", "lps_len",
    "lps_low_bar", "lps_low_date", "lps_offset", "lps_profile_unit",
    "lps_profile_unit_pct", "lps_pullback_profile",
    "lps_spread_expansion_profile", "lps_stretch_atr", "lps_stretch_box",
    "lps_swing_depth_atr", "lps_swing_depth_box", "lps_swing_depth_pct",
    "lps_swing_type", "lps_terminal_low_tolerance",
    "lps_window_high", "lps_window_low", "lps_window_range_pct_box",
    "lps_zone_type",
    "monthly_box", "monthly_candles", "monthly_volumes",
    "phase_d_evidence_json", "phase_d_inner",
    "price",
    "r_anchor", "r_touch_vol_z",
    "rs_line_latest", "rs_line_new_high", "rs_rating",
    "s_anchor", "s_touch_vol_z",
    "score", "sector_etf", "sector_name", "setup",
    "story_admission_profile", "sub_scores", "support_slope_atr",
    "tier", "traversal_density", "trigger",
    "volumes",
    "weekly_box", "weekly_candles", "weekly_volumes",
)


def test_wire_flag_off_key_set_snapshot(monkeypatch):
    """The exact flag-off wire key set — the boundary snapshot EC-8's
    byte-identical promise was missing. Any add/remove/rename fails here until
    the snapshot is updated deliberately in the same change."""
    chart = _payload(monkeypatch)
    assert tuple(sorted(chart.keys())) == tuple(sorted(FLAG_OFF_WIRE_KEYS))


# ── Task 9: the flag-ON v2 block + coverage/drift tripwires ─────────────────

_V2_OVERLAY = {
    "_ta_grade": 61.2345, "_ta_grade_raw": 104.777,
    "_ta_grade_chapters": {ch: 12.345678 for ch in taxonomy.CHAPTER_ORDER},
    "_ta_grade_chapter_fractions": {ch: 0.654321 for ch in taxonomy.CHAPTER_ORDER},
    "_ta_grade_warnings": {"terminal_drift": 0.8},
    "_score_spring": 0.0, "_score_story_s_tests": 0.0,
    "_score_story_r_rejections": 0.0, "_score_story_alternations": 0.0,
    "_score_story_terminal_posture": 0.0,
    "_lps_shrink_frac": 2.0 / 3.0, "_lps_window_classification": "clean_dip",
    "_story_richness_rate": 0.123456, "_trend_base_count": 2,
    "_inter_base_width_ratio": 0.512345,
}


def test_wire_flag_on_v2_block_serializes_rounded_fixed_arity(monkeypatch):
    """Flag-ON the v2 block rides the payload: display-rounded ONCE here,
    chapters exactly the ruled five, warnings a small dict — fixed arity
    only, nothing that grows with the chart."""
    chart = _payload(monkeypatch, v2_overlay=_V2_OVERLAY, flag=True)
    assert chart["ta_grade"] == 61.2                    # 1dp headline
    assert chart["ta_grade_raw"] == 104.78              # 2dp raw
    assert tuple(chart["ta_grade_chapters"]) == taxonomy.CHAPTER_ORDER
    assert all(v == 12.35 for v in chart["ta_grade_chapters"].values())
    assert chart["ta_grade_warnings"] == {"terminal_drift": 0.8}
    assert tuple(chart["ta_grade_chapter_fractions"]) == taxonomy.CHAPTER_ORDER
    assert all(v == 0.6543 for v in chart["ta_grade_chapter_fractions"].values())
    assert chart["lps_shrink_frac"] == 0.6667           # 4dp measurement
    assert chart["lps_window_classification"] == "clean_dip"
    assert chart["story_richness_rate"] == 0.1235
    assert chart["trend_base_count"] == 2
    assert chart["inter_base_width_ratio"] == 0.5123
    assert chart["score_spring"] == 0.0


def test_wire_covers_every_registry_term_and_family_column(monkeypatch):
    """The 6th-copy disease dies structurally: every ALWAYS-EMITTED registry
    term reaches the wire through sub_scores (a registry iteration now, never
    a hand tuple), and every flag-gated term column + family column reaches
    it through the v2 block. A TermSpec without wire coverage fails HERE at
    add time."""
    chart = _payload(monkeypatch, v2_overlay=_V2_OVERLAY, flag=True)
    for t in taxonomy.REGISTRY:
        if t.present_when is None:
            assert t.key in chart["sub_scores"], (
                f"always-emitted term {t.key!r} missing from sub_scores")
        else:
            assert t.column in chart, (
                f"flag-gated term column {t.column!r} missing from the v2 block")
    for col in TA_GRADE_COLUMN_SQL:
        if col.startswith("setup_"):
            continue        # the setup grades ride the archive, not this wire block
        assert col in chart, f"family column {col!r} missing from the v2 block"


def test_setupout_covers_every_term_and_family_column():
    """SetupOut drift-tripwire: a registry term or family column the archive
    API cannot serve fails at add time (the ArchiveSummary 7th-copy lesson)."""
    from routers.archive_schemas import SetupOut
    fields = set(SetupOut.model_fields)
    for t in taxonomy.REGISTRY:
        assert t.column in fields, f"SetupOut is missing {t.column!r}"
    for col in TA_GRADE_COLUMN_SQL:
        assert col in fields, f"SetupOut is missing family column {col!r}"


def test_min_ta_grade_filter_excludes_ungraded_rows():
    """The grade's OWN filter: min_score keeps raw-sum semantics forever; a
    ta_grade floor excludes graded-below AND pre-v2 NULL rows (three-valued
    logic, deliberately — an ungraded row can never satisfy a grade floor)."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from database import Base
    from archive_models import SetupArchive
    from services.archive_queries import _apply_setup_filters

    eng = create_engine("sqlite://")
    Base.metadata.create_all(eng)
    session = sessionmaker(bind=eng)()

    def _row(ticker, grade):
        return SetupArchive(
            ticker=ticker, scan_date="2026-08-01", setup_type="LPS",
            tier="B", score=90.0, current_price=10.0, r_level=11.0,
            s_level=9.5, trigger_price=11.1, base_length=30, box_width=0.1,
            touches=4, atr_ratio=0.5, lps_length=3, breach_days=0,
            vol_contraction=0.4, tightness_ratio=0.4, ta_grade=grade)

    session.add_all([_row("HIGRD", 71.0), _row("LOGRD", 40.0),
                     _row("PREV2", None)])
    session.commit()
    got = {r.ticker for r in _apply_setup_filters(
        session.query(SetupArchive), min_ta_grade=50.0).all()}
    assert got == {"HIGRD"}
    unfiltered = {r.ticker for r in _apply_setup_filters(
        session.query(SetupArchive)).all()}
    assert unfiltered == {"HIGRD", "LOGRD", "PREV2"}


def test_episode_grade_floor_is_the_current_grade_and_keeps_the_anchor():
    """The episode view's ruled semantics (2026-08-08, operator-delegated):
    min_ta_grade floors on the episode's LATEST member's grade — a
    flip-straddling episode keeps its TRUE first-seen anchor, scan count,
    and saw-and-passed marker (the row-level filter re-anchored all three),
    and an episode whose grade decayed below the floor drops even though an
    older scan once passed. latest_ta_grade is served either way."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from database import Base
    from archive_models import SetupArchive
    import models
    from routers.archive_browse import list_episodes

    eng = create_engine("sqlite://")
    Base.metadata.create_all(eng)
    session = sessionmaker(bind=eng)()

    def _row(ticker, scan_date, grade):
        return SetupArchive(
            ticker=ticker, scan_date=scan_date, setup_type="LPS",
            tier="B", score=90.0, current_price=10.0, r_level=11.0,
            s_level=9.5, trigger_price=11.1, base_length=30, box_width=0.1,
            touches=4, atr_ratio=0.5, lps_length=3, breach_days=0,
            vol_contraction=0.4, tightness_ratio=0.4, ta_grade=grade)

    session.add_all([
        # STRAD: pre-flip NULL scan, then graded — one episode across the seam.
        _row("STRAD", "2026-08-03", None),
        _row("STRAD", "2026-08-04", 80.0),
        _row("STRAD", "2026-08-05", 75.0),
        # DECAY: once above the floor, latest below it.
        _row("DECAY", "2026-08-04", 90.0),
        _row("DECAY", "2026-08-05", 60.0),
        # PREV2: never graded.
        _row("PREV2", "2026-08-05", None),
    ])
    # The marker is keyed on the TRUE first_seen — it must survive the filter.
    session.add(models.SetupReview(ticker="STRAD", scan_date="2026-08-03",
                                   verdict="passed", note="looked, skipped"))
    session.commit()

    def _episodes(min_grade):
        # Plain-function route call: every Query default passed explicitly.
        return list_episodes(
            skip=0, limit=200, tier=None, setup_type=None, source=None,
            quality_label=None, min_score=None, min_ta_grade=min_grade,
            date_from=None, date_to=None, universe_type="us_equities",
            sort_by="first_seen", sort_dir="desc", db=session)

    eps = _episodes(70.0)
    assert [e.ticker for e in eps] == ["STRAD"]
    strad = eps[0]
    assert strad.first_seen == "2026-08-03"      # the true anchor, not 08-04
    assert strad.scan_count == 3                 # the NULL scan still counts
    assert strad.latest_ta_grade == 75.0         # the value the floor judged
    assert strad.ta_grade is None                # canonical row: honest NULL
    assert strad.passed is True                  # the marker did not detach

    lower = _episodes(50.0)
    assert {e.ticker for e in lower} == {"STRAD", "DECAY"}
    unfiltered = _episodes(None)
    assert {e.ticker for e in unfiltered} == {"STRAD", "DECAY", "PREV2"}
    by_ticker = {e.ticker: e for e in unfiltered}
    assert by_ticker["DECAY"].latest_ta_grade == 60.0   # served unfiltered too
    assert by_ticker["PREV2"].latest_ta_grade is None
