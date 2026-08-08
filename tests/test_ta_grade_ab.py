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
from tools.ta_grade_ab import build_report, main


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
    # EC-13 stamps: the manifest hash + the EXACT population scored.
    assert report["engine_config_version"] == manifest_hash()
    assert report["population"] == {"n": 2, "by_source": {"screener": 2}}
    # In-process hygiene: the tool restored the flag.
    assert settings.TA_SCORE_V2 is False


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


def test_json_output_is_sealed_output_guarded(monkeypatch, tmp_path):
    import database

    monkeypatch.setattr(database, "SessionLocal", _mem_session)
    sealed = ROOT / "docs" / "marks" / "ab_evil.json"
    with pytest.raises(ValueError, match="sealed"):
        main(["--json", str(sealed)])
    assert not sealed.exists()
    out = tmp_path / "ab.json"
    assert main(["--json", str(out)]) == 0
    assert out.exists()
