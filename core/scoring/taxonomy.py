"""Single source of truth for the scoring sub-score taxonomy.

One ordered registry of every scoring sub-score term. For each term it records:
  - ``key``          the ``score_setup`` result-dict key,
  - ``column``       the ``setup_archive`` column (``None`` = not persisted yet),
  - ``cap_setting``  the ``config.settings`` attribute holding its point cap,
  - ``layer``        ``'ta'``  = part of the 0-100 Technical Analysis Score / tier,
                     ``'regime'`` = market-state, EXCLUDED from the score (label only),
  - ``kind``         structural | context | puzzle | tag | warning | new_term,
  - ``present_when`` a settings BOOL flag gating emission (``None`` = always emitted).

Consumers (the ``score_setup`` result dict, the archive writers, ``analyze.py``,
the ``/calibration`` endpoint, the frontend chips, and — later — the 0-100
normalization divisor) derive their column / cap / key lists from THIS registry
instead of re-declaring literals. That kills the historical duplication where a
cap lived in ``config`` AND was re-typed in the frontend ``SUB_SCORE_CAPS`` plus
each archive site, so a cap change silently mis-fired chips.

Caps are referenced by settings ATTRIBUTE NAME and resolved lazily (``getattr``
at call time), never captured at import — a change in ``config/settings.py``
flows everywhere and the backend-cwd config-shadow trap is dodged.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from config import settings


@dataclass(frozen=True)
class TermSpec:
    key: str                          # score_setup result-dict key
    column: Optional[str]             # setup_archive column (None = not persisted yet)
    cap_setting: str                  # config.settings attribute holding the point cap
    layer: str                        # 'ta' (in the TA Score + tier) | 'regime' (label only)
    kind: str                         # structural | context | puzzle | tag | warning | new_term
    present_when: Optional[str] = None  # settings BOOL flag gating emission (None = always)

    def cap(self) -> float:
        """The term's point cap, resolved lazily from settings at call time."""
        return float(getattr(settings, self.cap_setting))

    def is_emitted(self) -> bool:
        """Whether this term is emitted under the CURRENT flags."""
        if self.present_when is None:
            return True
        return bool(getattr(settings, self.present_when))


# Ordered to match the score_setup result-dict emission order (scoring.py).
REGISTRY: tuple[TermSpec, ...] = (
    TermSpec("box_tightness",     "score_box_tightness",     "SCORE_BOX_TIGHTNESS",      "ta",     "structural"),
    TermSpec("touch_density",     "score_touch_density",     "SCORE_TOUCH_DENSITY",      "ta",     "structural"),
    TermSpec("traversal_quality", "score_traversal_quality", "SCORE_TRAVERSAL_QUALITY",  "ta",     "structural"),
    TermSpec("atr_squeeze",       "score_atr_squeeze",       "SCORE_ATR_SQUEEZE",        "ta",     "structural"),
    TermSpec("lps_tightness",     "score_lps_tightness",     "SCORE_LPS_TIGHTNESS",      "ta",     "structural"),
    TermSpec("vol_contraction",   "score_vol_contraction",   "SCORE_VOL_CONTRACTION",    "ta",     "structural"),
    TermSpec("base_age",          "score_base_age",          "SCORE_BASE_AGE",           "ta",     "structural"),
    TermSpec("uptrend_bonus",     "score_uptrend_bonus",     "SCORE_UPTREND_BONUS",      "ta",     "context"),
    TermSpec("rs_bonus",          "score_rs_bonus",          "SCORE_RS_BONUS",           "ta",     "context"),
    TermSpec("high_proximity",    "score_high_proximity",    "SCORE_52W_HIGH_PROXIMITY", "ta",     "context"),
    TermSpec("breadth_bonus",     "score_breadth_bonus",     "SCORE_BREADTH_BONUS",      "regime", "context"),
    TermSpec("contraction",       "score_contraction",       "SCORE_CONTRACTION",        "ta",     "structural"),
    TermSpec("ascending_support", "score_ascending_support", "SCORE_ASCENDING_SUPPORT",  "ta",     "structural"),
    TermSpec("adr",               "score_adr",               "SCORE_ADR",                "ta",     "context"),
    # Emitted only behind its own flag; its archive column is a Wave-2 add (design P3).
    TermSpec("puzzle_quality",    None,                      "SCORE_PUZZLE_QUALITY",     "ta",     "puzzle", "PUZZLE_SCORE_ENABLED"),
)


def emitted_keys() -> list[str]:
    """Result-dict sub-score keys emitted under the CURRENT flags (order-preserving)."""
    return [t.key for t in REGISTRY if t.is_emitted()]


def archive_columns() -> list[str]:
    """Persisted archive columns for every term that has one (order-preserving)."""
    return [t.column for t in REGISTRY if t.column is not None]


def caps() -> dict[str, float]:
    """{key: point cap} for every registered term, resolved from settings."""
    return {t.key: t.cap() for t in REGISTRY}


def ta_layer_terms() -> tuple[TermSpec, ...]:
    """The terms that make up the Technical Analysis Score (layer 'ta') and are
    emitted under the current flags — i.e. everything except the regime label."""
    return tuple(t for t in REGISTRY if t.layer == "ta" and t.is_emitted())


def structural_cap_sum() -> float:
    """Fixed 0-100 divisor for the TA Score: summed point caps of the emitted
    TA-layer terms (the regime-label term is excluded). A pure function of config
    that grows as new TA terms are registered — never a per-row or cohort max
    (that would be lookahead), so the 0-100 map stays strictly monotonic."""
    return sum(t.cap() for t in ta_layer_terms())
