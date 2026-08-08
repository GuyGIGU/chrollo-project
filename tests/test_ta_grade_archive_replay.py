"""Pure-logic battery for the archive-wide TA-grade replay instrument.

The replay loop itself runs the ONE live eval chain over the real cache (its
faithfulness is the eval chain's own test surface); what is pinned here is the
instrument's judgment layer — the concordance gate and the rollup — so a
silent join or a miscounted funnel can never reach the operator's eyes.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(1, str(ROOT / "webapp" / "backend"))

from tools.ta_grade_archive_replay import (  # noqa: E402
    RAIL_TOL,
    rails_concordant,
    summarize,
)


def test_rails_concordant_is_the_same_shelf_within_tol():
    # Exact identity and sub-tolerance drift join; a different shelf refuses.
    assert rails_concordant(62.81, 56.05, 62.81, 56.05)
    assert rails_concordant(100.0 * (1 + RAIL_TOL * 0.9), 50.0, 100.0, 50.0)
    assert not rails_concordant(100.0 * (1 + RAIL_TOL * 1.1), 50.0, 100.0, 50.0)
    # ONE drifted rail refuses — partial identity is not identity.
    assert not rails_concordant(100.0, 50.0 * 1.02, 100.0, 50.0)
    # Missing/zero rails refuse, never crash and never silently join.
    assert not rails_concordant(None, 50.0, 100.0, 50.0)
    assert not rails_concordant(100.0, 50.0, None, 50.0)
    assert not rails_concordant(100.0, 50.0, 0.0, 50.0)


def _rec(ticker, scan_date, outcome, epoch="aaaaaaaa", quality=None,
         grade=None, old_score=None):
    return {"ticker": ticker, "scan_date": scan_date, "outcome": outcome,
            "epoch": epoch,
            "setup": ({"quality": quality} if quality is not None else None),
            "ta_grade": grade, "old": {"score": old_score, "tier": "A"}}


def test_summarize_funnel_epochs_setup_quality_and_movement():
    records = [
        _rec("AAA", "2026-08-08", "concordant", quality=8.0, grade=60.0,
             old_score=120.0),
        _rec("BBB", "2026-08-08", "concordant", quality=0.0, grade=55.0,
             old_score=100.0),
        # Inverted pair on the latest date: CCC out-scores BBB on v1 but
        # under-grades it on v2 -> both move one rank.
        _rec("CCC", "2026-08-08", "concordant", quality=4.0, grade=50.0,
             old_score=110.0),
        _rec("DDD", "2026-07-01", "concordant", epoch="bbbbbbbb", quality=2.0,
             grade=40.0, old_score=90.0),
        _rec("EEE", "2026-07-01", "discordant", epoch="bbbbbbbb"),
        _rec("FFF", "2026-06-01", "no_fire", epoch="cccccccc"),
        _rec("GGG", "2026-06-01", "cache_missing", epoch="cccccccc"),
    ]
    s = summarize(records)
    assert s["funnel"] == {"concordant": 4, "discordant": 1, "no_fire": 1,
                           "cache_missing": 1}
    assert s["epochs"]["aaaaaaaa"] == {"n": 3, "concordant": 3}
    assert s["epochs"]["bbbbbbbb"] == {"n": 2, "concordant": 1}
    assert s["epochs"]["cccccccc"] == {"n": 2, "concordant": 0}
    pz = s["setup_quality"]
    assert pz["n"] == 4 and pz["at_zero"] == 1 and pz["at_cap"] == 1
    assert pz["mean"] == (8.0 + 0.0 + 4.0 + 2.0) / 4
    # Monthly means cover only concordant reads with a measured setup_quality.
    assert s["monthly"]["2026-08"]["n"] == 3
    assert s["monthly"]["2026-07"] == {"n": 1, "mean_setup_quality": 2.0}
    # Latest-date movement: old order AAA>CCC>BBB, grade order AAA>BBB>CCC.
    mv = s["latest_date_movement"]
    assert mv["scan_date"] == "2026-08-08" and mv["n"] == 3
    assert mv["median_abs_rank_delta"] == 1 and mv["max_abs_rank_delta"] == 1


def test_summarize_is_affirmative_when_nothing_joins():
    s = summarize([_rec("AAA", "2026-08-08", "no_fire")])
    assert s["funnel"] == {"no_fire": 1}
    assert s["setup_quality"] is None
    assert s["monthly"] == {}
    assert s["latest_date_movement"] is None
