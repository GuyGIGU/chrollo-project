"""
Missed-winners analysis — did the engine flag winners I never engaged with?

This is the engine-validation payoff: it measures the screener's *standalone*
edge against the operator's discretion. It runs on episode-collapsed setups
(one row per real setup — see ``episodes.py`` — so a persisting base isn't
counted many times).

A setup is a WINNER if its achievable reward/risk reached the user's bar
(default **>= +2R within 60 days**, via MFE-based ``r_multiple_60d`` — the best
excursion, i.e. "what could have been caught"). Each winner is then bucketed by
how the operator engaged with it:

  - TRADED         — a real position was taken on that ticker near the setup
  - SAW_AND_PASSED — the setup was reviewed and explicitly skipped
  - NEVER_ENGAGED  — neither; the engine found it and the operator never looked

NEVER_ENGAGED winners are the headline number: edge the engine has that the
operator's own hand missed. Pure + dependency-free so it is trivially testable;
the caller supplies engagement + outcome, this module only classifies.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Optional

DEFAULT_WINNER_R = 2.0


class Engagement(str, Enum):
    TRADED = "traded"
    SAW_AND_PASSED = "saw_and_passed"
    NEVER_ENGAGED = "never_engaged"


@dataclass(frozen=True)
class EpisodeOutcome:
    """One episode's outcome + how the operator engaged with it."""

    ticker: str
    first_seen: str
    tier: str
    score: Optional[float]
    r_multiple_60d: Optional[float]   # MFE-based achievable R within 60d; None until matured
    engagement: Engagement


def is_winner(r_multiple_60d: Optional[float], min_r: float = DEFAULT_WINNER_R) -> bool:
    """True if the achievable reward reached the winner bar."""
    return r_multiple_60d is not None and r_multiple_60d >= min_r


def summarize(outcomes: Iterable[EpisodeOutcome], min_r: float = DEFAULT_WINNER_R) -> dict:
    """Classify episodes into the missed-winners scorecard.

    Only episodes with a computed ``r_multiple_60d`` count as "matured"; the
    rest are still waiting on the forward-return clock and are excluded from the
    winner tallies (but counted in ``episodes_total``).
    """
    outcomes = list(outcomes)
    matured = [o for o in outcomes if o.r_multiple_60d is not None]
    winners = [o for o in matured if is_winner(o.r_multiple_60d, min_r)]

    buckets: dict[Engagement, list[EpisodeOutcome]] = {e: [] for e in Engagement}
    for o in winners:
        buckets[o.engagement].append(o)

    missed = sorted(
        buckets[Engagement.NEVER_ENGAGED],
        key=lambda o: o.r_multiple_60d or 0.0,
        reverse=True,
    )

    return {
        "min_r": min_r,
        "episodes_total": len(outcomes),
        "episodes_matured": len(matured),
        "winners_total": len(winners),
        "winners_traded": len(buckets[Engagement.TRADED]),
        "winners_saw_and_passed": len(buckets[Engagement.SAW_AND_PASSED]),
        "winners_never_engaged": len(missed),
        "missed_winners": [
            {
                "ticker": o.ticker,
                "first_seen": o.first_seen,
                "tier": o.tier,
                "score": o.score,
                "r_multiple_60d": o.r_multiple_60d,
            }
            for o in missed
        ],
    }
