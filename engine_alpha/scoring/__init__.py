"""
THE SCORING ENGINE — "how we RATE the setup".

The opinion layer. It takes the measured facts from the Structure Engine and
turns them into points and a letter tier. All the dials live in
``config/settings.py`` (the SCORE_* and TIER_* constants) — tuning the
strategy means changing numbers there, not the measurement code.

Public API:
    score_setup    -> total score + per-ingredient sub-scores
    (the tier derives from the TA grade inside compose_ta_grade — the legacy
    calculate_tier ladder retired at the 2026-08-22 consolidation)
"""
from engine_alpha.scoring.scoring import score_setup

__all__ = ["score_setup"]
