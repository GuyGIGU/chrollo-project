"""
THE SCORING ENGINE — "how we RATE the setup".

The opinion layer. It takes the measured facts from the Structure Engine and
turns them into points and a letter tier. All the dials live in
``config/settings.py`` (the SCORE_* and TIER_* constants) — tuning the
strategy means changing numbers there, not the measurement code.

Public API:
    score_setup    -> total score + per-ingredient sub-scores
    calculate_tier -> map a score to S / A / B / C / D
"""
from engine_alpha.scoring.scoring import calculate_tier, score_setup

__all__ = ["score_setup", "calculate_tier"]
