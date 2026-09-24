import sys

from _paths import REPO_ROOT as ROOT
sys.path.insert(0, str(ROOT))

from core.archive.missed_winners import (
    Engagement,
    EpisodeOutcome,
    is_winner,
    summarize,
)


def _o(ticker, r, engagement, tier="S", score=80.0, first_seen="2026-05-31"):
    return EpisodeOutcome(
        ticker=ticker, first_seen=first_seen, tier=tier, score=score,
        r_multiple_60d=r, engagement=engagement,
    )


def test_is_winner_threshold():
    assert is_winner(2.0) is True       # at the bar
    assert is_winner(3.5) is True
    assert is_winner(1.9) is False
    assert is_winner(None) is False     # not matured
    assert is_winner(1.0, min_r=1.0) is True


def test_immature_episodes_excluded_from_winner_tally():
    outcomes = [
        _o("AAA", None, Engagement.NEVER_ENGAGED),   # no 60d data yet
        _o("BBB", 2.5, Engagement.NEVER_ENGAGED),
    ]
    s = summarize(outcomes)
    assert s["episodes_total"] == 2
    assert s["episodes_matured"] == 1
    assert s["winners_total"] == 1


def test_winner_bucketing_by_engagement():
    outcomes = [
        _o("WTRADE", 3.0, Engagement.TRADED),
        _o("WPASS", 2.2, Engagement.SAW_AND_PASSED),
        _o("WMISS", 4.0, Engagement.NEVER_ENGAGED),
        _o("LOSER", 0.5, Engagement.NEVER_ENGAGED),   # not a winner
    ]
    s = summarize(outcomes)
    assert s["winners_total"] == 3
    assert s["winners_traded"] == 1
    assert s["winners_saw_and_passed"] == 1
    assert s["winners_never_engaged"] == 1
    assert [w["ticker"] for w in s["missed_winners"]] == ["WMISS"]


def test_missed_winners_sorted_by_r_desc():
    outcomes = [
        _o("LOW", 2.1, Engagement.NEVER_ENGAGED),
        _o("HIGH", 6.0, Engagement.NEVER_ENGAGED),
        _o("MID", 3.3, Engagement.NEVER_ENGAGED),
    ]
    s = summarize(outcomes)
    assert [w["ticker"] for w in s["missed_winners"]] == ["HIGH", "MID", "LOW"]


def test_custom_min_r_bar():
    outcomes = [_o("AAA", 1.5, Engagement.NEVER_ENGAGED)]
    assert summarize(outcomes, min_r=2.0)["winners_total"] == 0
    assert summarize(outcomes, min_r=1.0)["winners_total"] == 1
