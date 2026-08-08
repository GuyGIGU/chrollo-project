"""The A/B flip instrument's battery (TA-grade build task 13).

The instrument is the one surface the operator's flip decision consumes, so
its numbers are pinned hand-computed on an in-memory archive: the would-be
grade from archived facts, the two rank orders, the movement deltas, the
EC-13 stamps, the affirmative empty state, and the EC-14 sealed-output leg.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(1, str(ROOT / "webapp" / "backend"))

from config import settings
from engine_alpha.freeze.manifest import manifest_hash
from engine_alpha.scoring import taxonomy
from tools.ta_grade_ab import _identity_ranks, _ranks, build_report, main


def _mem_session():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from database import Base
    import archive_models  # noqa: F401 — registers SetupArchive on Base first

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _fire(ticker, score, tier, **cols):
    from archive_models import SetupArchive

    base = dict(ticker=ticker, scan_date="2026-08-07", setup_type="LPS",
                tier=tier, score=score, current_price=10.0, r_level=11.0,
                s_level=9.5, trigger_price=11.1, base_length=30,
                box_width=0.1, touches=4, atr_ratio=0.5, lps_length=3,
                breach_days=0, vol_contraction=0.4, tightness_ratio=0.4,
                source="screener")
    base.update(cols)
    return SetupArchive(**base)


def _cap_sum_flag_on(monkeypatch_free=False):
    prev = settings.TA_SCORE_V2
    settings.TA_SCORE_V2 = True
    try:
        return taxonomy.structural_cap_sum()
    finally:
        settings.TA_SCORE_V2 = prev


def test_report_grades_ranks_and_stamps_hand_computed():
    session = _mem_session()
    # AAA: v1 ta points 20+20 = raw 40 (hand). BBB: 15+15 = raw 30, but the
    # OLD scores invert the order (BBB stored 90 > AAA 50) — the movement the
    # operator judges is exactly this inversion.
    session.add_all([
        _fire("AAA", 50.0, "C",
              score_box_tightness=20.0, score_touch_density=20.0),
        _fire("BBB", 90.0, "B",
              score_box_tightness=15.0, score_touch_density=15.0,
              htf_m_trend_state="down"),
    ])
    session.commit()
    report = build_report(session, None)
    assert report["scan_date"] == "2026-08-07"
    a = next(g for g in report["rows"] if g["ticker"] == "AAA")
    b = next(g for g in report["rows"] if g["ticker"] == "BBB")
    cap_sum = _cap_sum_flag_on()
    assert a["ta_grade_raw"] == pytest.approx(40.0)          # the hand anchor
    assert b["ta_grade_raw"] == pytest.approx(30.0)
    assert a["ta_grade"] == pytest.approx(40.0 * 100.0 / cap_sum)
    # v1→v2 MOVEMENT: AAA climbs to 1 (Δ+1), BBB falls (Δ−1).
    assert a["rank_old"] == 2 and a["rank_new"] == 1 and a["rank_delta"] == 1
    assert b["rank_delta"] == -1
    # The AFFINE IDENTITY holds — kept strictly apart from the movement.
    assert report["identity_ok"] is True
    # weak_monthly rides BBB visibly; its neutral 1.0 factor costs nothing.
    assert "weak_monthly" in b["warnings"]
    assert b["ta_grade"] == pytest.approx(30.0 * 100.0 / cap_sum)
    # EC-13 stamps: the manifest hash of the config that PRODUCED the numbers
    # (stamped inside the forced-flag window — 2026-08-08 review, finding 7),
    # discriminably different from the ambient flag-off hash pre-flip.
    prev = settings.TA_SCORE_V2
    settings.TA_SCORE_V2 = True
    try:
        flag_on_hash = manifest_hash()
    finally:
        settings.TA_SCORE_V2 = prev
    assert report["engine_config_version"] == flag_on_hash
    if prev is False:
        assert report["engine_config_version"] != manifest_hash()
    # ... plus the EXACT population scored, fingerprinted (EC-13).
    assert report["population"]["n"] == 2
    assert report["population"]["by_source"] == {"screener": 2}
    assert len(report["population"]["fingerprint"]) == 16
    assert report["universe_type"] == "us_equities"


def test_flag_is_restored_to_its_prior_value():
    """In-process hygiene: build_report restores the flag to whatever it WAS
    — asserted against the captured prior value, not the repo default (the
    old `is False` pin was a guaranteed unexplained red inside the atomic
    flip commit; 2026-08-08 review, finding 10)."""
    session = _mem_session()
    session.add(_fire("AAA", 50.0, "C", score_box_tightness=20.0))
    session.commit()
    prev = settings.TA_SCORE_V2
    build_report(session, None)
    assert settings.TA_SCORE_V2 is prev


def test_identity_checks_the_prewarning_operand_not_the_headline(monkeypatch):
    """The affine identity must NOT false-alarm the day a warning cost lands
    (2026-08-08 review, finding 2): with a sub-1.0 factor the post-warning
    headline legitimately reorders against raw — that is MOVEMENT — while
    the pre-warning ordering stays the affine image of raw."""
    monkeypatch.setattr(settings, "TA_WARN_WEAK_MONTHLY", 0.8)
    session = _mem_session()
    session.add_all([
        # BBB out-raws AAA (40 > 39) but fires weak_monthly: at factor 0.8
        # its HEADLINE falls below AAA's — the post-warning ordering differs
        # from raw, which the old headline-based check called a BUG.
        _fire("AAA", 50.0, "C",
              score_box_tightness=20.0, score_touch_density=19.0),
        _fire("BBB", 90.0, "B",
              score_box_tightness=20.0, score_touch_density=20.0,
              htf_m_trend_state="down"),
    ])
    session.commit()
    report = build_report(session, None)
    a = next(g for g in report["rows"] if g["ticker"] == "AAA")
    b = next(g for g in report["rows"] if g["ticker"] == "BBB")
    cap_sum = _cap_sum_flag_on()
    assert b["ta_grade_raw"] > a["ta_grade_raw"]
    assert b["warnings"] == {"weak_monthly": 0.8}
    assert b["ta_grade"] == pytest.approx(40.0 * 100.0 / cap_sum * 0.8)
    assert b["ta_grade"] < a["ta_grade"]          # the headline reordered...
    assert report["identity_ok"] is True          # ...and that is MOVEMENT
    assert a["rank_new"] == 1 and b["rank_new"] == 2
    # The pre-warning operand is what the identity ranked.
    assert b["ta_grade_prewarn"] > a["ta_grade_prewarn"]


def test_identity_survives_float_noise_ties():
    """First live population (2026-08-08, 256 fires): OHI and NTES both truly
    summed to raw 84.28, but term-order accumulation put them 3e-14 apart in
    raw while their chapter-grouped prewarn sums came out bit-identical — the
    raw ordering split them by noise, the prewarn ordering tie-broke by
    ticker, and the identity false-alarmed exit 2 on a correct map. The
    operands are quantized before ranking: a true tie must rank identically
    in both orderings. Values below are the ACTUAL live doubles."""
    graded = [
        {"ticker": "OHI", "ta_grade_raw": 84.28000000000002,
         "ta_grade_prewarn": 49.28654970760233},
        {"ticker": "NTES", "ta_grade_raw": 84.27999999999999,
         "ta_grade_prewarn": 49.28654970760233},
    ]
    # The red step, kept in the pin: unquantized, the two orderings disagree.
    assert (_ranks([(g["ticker"], g["ta_grade_raw"]) for g in graded])
            != _ranks([(g["ticker"], g["ta_grade_prewarn"]) for g in graded]))
    raw_ranks, prewarn_ranks = _identity_ranks(graded)
    assert raw_ranks == prewarn_ranks == {"NTES": 1, "OHI": 2}


def test_epoch_basis_banner_names_the_missing_setup_quality(monkeypatch, tmp_path,
                                                     capsys):
    """Rows archived before the grade columns existed carry score_setup_quality
    NULL: the replay grades setup_quality absence-neutral 0 while the stored v1 score
    still contains its points, so their rank Δ is the missing setup-quality
    differential (first live A/B 2026-08-08: the whole ±31 movers list was
    exactly this). The banner names that basis on BOTH output modes and stays
    silent when every row carries setup_quality."""
    import database

    session = _mem_session()
    session.add_all([
        _fire("AAA", 50.0, "C", score_box_tightness=20.0),
        _fire("BBB", 90.0, "B", score_box_tightness=15.0,
              score_setup_quality=2.0),
    ])
    session.commit()
    report = build_report(session, None)
    assert report["setup_quality_absent_rows"] == 1

    monkeypatch.setattr(database, "SessionLocal", lambda: session)
    assert main([]) == 0
    human = capsys.readouterr().out
    assert "1 of 2 rows carry no archived setup_quality" in human
    assert main(["--json", str(tmp_path / "ab.json")]) == 0
    assert "1 of 2 rows carry no archived setup_quality" in capsys.readouterr().out

    merged = _mem_session()
    merged.add(_fire("CCC", 50.0, "C", score_box_tightness=20.0,
                     score_setup_quality=0.0))
    merged.commit()
    assert build_report(merged, None)["setup_quality_absent_rows"] == 0
    monkeypatch.setattr(database, "SessionLocal", lambda: merged)
    assert main([]) == 0
    assert "setup_quality" not in capsys.readouterr().out


def test_empty_state_is_affirmative():
    session = _mem_session()
    report = build_report(session, None)
    assert report["rows"] == [] and report["scan_date"] is None
    assert report["identity_ok"] is True
    session.add(_fire("AAA", 50.0, "C"))
    session.commit()
    later = build_report(session, "1999-01-01")
    assert later["rows"] == []
    assert later["recent_dates"] == ["2026-08-07"]   # the affirmative pointer


def test_json_output_is_sealed_output_guarded(monkeypatch, tmp_path, capsys):
    import database

    monkeypatch.setattr(database, "SessionLocal", _mem_session)
    sealed = ROOT / "docs" / "marks" / "ab_evil.json"
    with pytest.raises(ValueError, match="sealed"):
        main(["--json", str(sealed)])
    assert not sealed.exists()
    out = tmp_path / "ab.json"
    assert main(["--json", str(out)]) == 0
    assert out.exists()
    # The identity verdict speaks on the --json path too (finding 2: the
    # violation banner used to exist only in the human print path, silent on
    # exactly the mode the flip checklist routes the evidence through).
    assert "affine identity: OK" in capsys.readouterr().out
