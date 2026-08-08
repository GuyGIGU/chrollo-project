"""Single source of truth for the scoring sub-score taxonomy.

One ordered registry of every scoring sub-score term. For each term it records:
  - ``key``          the ``score_setup`` result-dict key,
  - ``column``       the ``setup_archive`` column (MANDATORY since task 5:
                     every registered term persists — a term without a column
                     is the puzzle_quality breach again, refused by test),
  - ``cap_setting``  the ``config.settings`` attribute holding its point cap,
  - ``layer``        ``'ta'``  = part of the 0-100 Technical Analysis Grade / tier,
                     ``'regime'`` = market-state, EXCLUDED from the grade (label only),
  - ``kind``         structural | context | puzzle | tag | warning | new_term,
  - ``present_when`` a settings BOOL flag gating emission (``None`` = always emitted),
  - ``chapter``      the story chapter this term grades inside (``CHAPTER_ORDER``;
                     ``None`` on the regime layer — no chapter, no grade membership).

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
    column: Optional[str]             # setup_archive column (mandatory — see docstring)
    cap_setting: str                  # config.settings attribute holding the point cap
    layer: str                        # 'ta' (in the TA Grade + tier) | 'regime' (label only)
    kind: str                         # structural | context | puzzle | tag | warning | new_term
    present_when: Optional[str] = None  # settings BOOL flag gating emission (None = always)
    chapter: Optional[str] = None     # story chapter (CHAPTER_ORDER); None on the regime layer

    def cap(self) -> float:
        """The term's point cap, resolved lazily from settings at call time."""
        return float(getattr(settings, self.cap_setting))

    def is_emitted(self) -> bool:
        """Whether this term is emitted under the CURRENT flags."""
        if self.present_when is None:
            return True
        return bool(getattr(settings, self.present_when))


# ── Story chapters — the grade's frame (operator-ruled 2026-08-06) ───────────
# The 0-100 Technical Analysis Grade decomposes into story chapters that read
# left→right like the chart, the way the operator narrates it:
#   cause          the base itself — is there a proper, tight, mature Phase-B range?
#   work           what happened inside — touches, genuine traversal, progressive
#                  contraction, the completeness of the told story
#   turn           the right-side improvement — rising support, spring/Phase-D
#   finish         the pre-breakout state — LPS tightness, its volume dry-up,
#                  the terminal ATR squeeze
#   trend_context  the chart around the base — trend, RS, 52w proximity, ADR
# Chapters are a DISPLAY PARTITION of the single fixed-divisor affine sum —
# never per-chapter normalization (the present-cap denominator is tested-DEAD).
# Membership is hashed into engine_config_version (freeze/manifest.py), so a
# re-chaptering is a visible archive seam, never a silent relabel.
CHAPTER_ORDER: tuple[str, ...] = ("cause", "work", "turn", "finish", "trend_context")

# Reserved result-dict / wire keys for the flag-gated v2 grade — settled BEFORE
# anything serializes so no rename ever crosses a frozen surface. NOTHING may
# emit these while TA_SCORE_V2 is off (the flag-off tripwires derive from this
# tuple); archive columns reuse the same names where they persist.
#   ta_grade           the 0-100 (post-normalization, post-warnings; full precision,
#                      rounding is display-only). NOT ta_score — it must never be
#                      confusable with the 0-100 rs_rating percentile beside it.
#   ta_grade_raw       the raw affine sum (pre-normalization)
#   ta_grade_chapters  fixed-arity {chapter_id: points on the 0-100 scale}
#   ta_grade_warnings  the resolved floored warning discounts applied
#   structure_tier     letter tier derived from ta_grade
#   fired_tags         backend-resolved chip verdicts (the wire carries verdicts,
#                      never rules)
#   regime_label       market-state label — OUTSIDE the grade (breadth/SPY leave
#                      the score, taxonomy layer='regime')
# (Replaces the pre-chapter reserved names ta_structure_score / context_score /
# ta_score_v2 — retired unserialized 2026-08-08; structure_tier carries over.)
V2_RESULT_KEYS: tuple[str, ...] = (
    "ta_grade", "ta_grade_raw", "ta_grade_chapters",
    "ta_grade_chapter_fractions",   # per-chapter earned fraction (task 12) —
                                    # the strip's fill, resolved engine-side
    "ta_grade_warnings",
    "structure_tier", "fired_tags", "regime_label",
)

# Ordered to match the score_setup result-dict emission order (scoring.py).
REGISTRY: tuple[TermSpec, ...] = (
    TermSpec("box_tightness",     "score_box_tightness",     "SCORE_BOX_TIGHTNESS",      "ta",     "structural", chapter="cause"),
    TermSpec("touch_density",     "score_touch_density",     "SCORE_TOUCH_DENSITY",      "ta",     "structural", chapter="work"),
    TermSpec("traversal_quality", "score_traversal_quality", "SCORE_TRAVERSAL_QUALITY",  "ta",     "structural", chapter="work"),
    # atr_squeeze is ATR_10/ATR_50 at the right edge — the TERMINAL volatility
    # squeeze into the pivot, not a whole-base trait; it finishes the story.
    TermSpec("atr_squeeze",       "score_atr_squeeze",       "SCORE_ATR_SQUEEZE",        "ta",     "structural", chapter="finish"),
    TermSpec("lps_tightness",     "score_lps_tightness",     "SCORE_LPS_TIGHTNESS",      "ta",     "structural", chapter="finish"),
    TermSpec("vol_contraction",   "score_vol_contraction",   "SCORE_VOL_CONTRACTION",    "ta",     "structural", chapter="finish"),
    TermSpec("base_age",          "score_base_age",          "SCORE_BASE_AGE",           "ta",     "structural", chapter="cause"),
    TermSpec("uptrend_bonus",     "score_uptrend_bonus",     "SCORE_UPTREND_BONUS",      "ta",     "context",    chapter="trend_context"),
    TermSpec("rs_bonus",          "score_rs_bonus",          "SCORE_RS_BONUS",           "ta",     "context",    chapter="trend_context"),
    TermSpec("high_proximity",    "score_high_proximity",    "SCORE_52W_HIGH_PROXIMITY", "ta",     "context",    chapter="trend_context"),
    TermSpec("breadth_bonus",     "score_breadth_bonus",     "SCORE_BREADTH_BONUS",      "regime", "context"),
    TermSpec("contraction",       "score_contraction",       "SCORE_CONTRACTION",        "ta",     "structural", chapter="work"),
    TermSpec("ascending_support", "score_ascending_support", "SCORE_ASCENDING_SUPPORT",  "ta",     "structural", chapter="turn"),
    TermSpec("adr",               "score_adr",               "SCORE_ADR",                "ta",     "context",    chapter="trend_context"),
    # Always emitted (folded 2026-07-18; formerly behind PUZZLE_SCORE_ENABLED);
    # archived since task 5 (the measure-first breach closed). Chapter: the puzzle grades
    # the completeness of the told story — the work the range did.
    TermSpec("puzzle_quality",    "score_puzzle_quality",    "SCORE_PUZZLE_QUALITY",     "ta",     "puzzle",     chapter="work"),
    # Promoted v2 term — emitted only behind TA_SCORE_V2 (the v2 result block
    # appends it after the always-on terms, so it sits last here to keep the
    # emission-order mirror). Shape-only: SCORE_SPRING=0 until the operator's
    # A/B assigns weights; its archive column is a task-5 add.
    TermSpec("spring",            "score_spring",            "SCORE_SPRING",             "ta",     "tag",        "TA_SCORE_V2", chapter="turn"),
    # Story terms (task 4) — the Event-Map substrate graded INSIDE the chapters
    # (the 2026-08-06 ruling: grade the setups by their story). Emitted only
    # behind TA_SCORE_V2; caps start 0 = shape-only until the A/B; archive
    # columns are a task-5 add. They consume the archived as-of scalars ONLY
    # (completed counts + right-edge stance) — never the tape, never the
    # profile sentence (AP-8; nothing re-derives counts downstream).
    TermSpec("story_s_tests",          "score_story_s_tests",          "SCORE_STORY_S_TESTS",          "ta", "new_term", "TA_SCORE_V2", chapter="work"),
    TermSpec("story_r_rejections",     "score_story_r_rejections",     "SCORE_STORY_R_REJECTIONS",     "ta", "new_term", "TA_SCORE_V2", chapter="work"),
    TermSpec("story_alternations",     "score_story_alternations",     "SCORE_STORY_ALTERNATIONS",     "ta", "new_term", "TA_SCORE_V2", chapter="work"),
    TermSpec("story_terminal_posture", "score_story_terminal_posture", "SCORE_STORY_TERMINAL_POSTURE", "ta", "new_term", "TA_SCORE_V2", chapter="finish"),
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


def chapter_map() -> dict[str, str]:
    """{key: chapter} for every ta-layer term — the grade's story partition."""
    return {t.key: t.chapter for t in REGISTRY if t.layer == "ta"}


# ── The tag fire-rules — chip verdicts resolved ENGINE-SIDE (build task 10) ──
# One declarative registry absorbing the judgments that lived only in
# frontend JS (setupTagsData.js): the three touch-volume z thresholds, the
# firesAt cap-fractions, and the worked-equilibrium density (LINKED to its
# settings twin TRAVERSAL_QUALITY_DENSITY_FULL — the 0.33 was an unlinked
# numeric copy). The resolver lives in engine_alpha/scoring/tags.py; the
# frontend keeps ONLY presentational lookups (labels, tones, order, copy) —
# the wire carries verdicts, never rules (EC-28).
#
# Rule kinds (interpreted by the resolver; params reference settings by NAME,
# resolved lazily like cap_setting):
#   fraction    term points >= fraction × the term's registered cap; a
#               ZERO-cap term's chip is DEAD BY DESIGN (0 >= 0×f must never
#               fire — the demoted rs/uptrend chips stay dead deliberately,
#               where the stale JS caps kept them dead by accident)
#   flag        a truthy result fact
#   gt_setting / lt_setting / ge_setting   fact compared to a settings value
#   eq          fact equals a literal
#   any_gt0     any of the listed facts > 0
# ``detail`` names the result facts that ride the fired entry (the tooltip
# interpolations the frontend used to re-derive).
@dataclass(frozen=True)
class TagSpec:
    id: str
    rule: str
    term: Optional[str] = None          # fraction rules: the registry term key
    fraction: Optional[float] = None
    field: Optional[str] = None         # fact rules: the result-fact name (bare)
    fields: Optional[tuple] = None      # any_gt0: the fact names
    setting: Optional[str] = None       # *_setting rules: the settings NAME
    value: Optional[str] = None         # eq rules: the literal
    warning: bool = False               # warning-side chip (display grouping)
    detail: tuple = ()                  # facts attached to the fired entry


TAGS: tuple[TagSpec, ...] = (
    TagSpec("phase_d",            "flag", field="phase_d_inner"),
    TagSpec("heavy_resistance",   "gt_setting", field="r_touch_vol_z",
            setting="TOUCH_VOL_Z_HEAVY_R", warning=True,
            detail=("r_touch_vol_z",)),
    TagSpec("last_supper",        "any_gt0",
            fields=("lps_stretch_box", "lps_stretch_atr"), warning=True,
            detail=("lps_stretch_box", "lps_stretch_atr",
                    "last_supper_pullback_from_extension_pct",
                    "last_supper_reclaim_quality")),
    # weak_monthly's settled disposition (task 10, per the 2026-08-06 HTF
    # ruling): it STAYS in the vocabulary as the natural warning-side chip —
    # a warning that silently vanishes is indistinguishable from one that
    # stopped firing — AND registers as a ta-grade warning discount
    # (TA_WARN_WEAK_MONTHLY, neutral 1.0 until the operator's A/B).
    TagSpec("weak_monthly",       "eq", field="htf_m_trend_state",
            value="down", warning=True, detail=("htf_m_trend_state",)),
    TagSpec("old_base",           "fraction", term="base_age",     fraction=0.80),
    TagSpec("vcp_coil",           "fraction", term="contraction",  fraction=0.80,
            detail=("contraction_count", "contraction_vol_trend")),
    TagSpec("tight_box",          "fraction", term="box_tightness", fraction=0.80),
    TagSpec("phase_c_test",       "flag", field="bin_c_present",
            detail=("bin_c_type", "bin_c_undercut_atr", "bin_c_recovery_bars")),
    TagSpec("tight_lps",          "fraction", term="lps_tightness", fraction=1.00),
    TagSpec("ascending_support",  "fraction", term="ascending_support", fraction=0.80),
    TagSpec("no_supply",          "lt_setting", field="r_touch_vol_z",
            setting="TOUCH_VOL_Z_NO_SUPPLY", detail=("r_touch_vol_z",)),
    TagSpec("vol_dryup",          "fraction", term="vol_contraction", fraction=0.80),
    TagSpec("demand_at_s",        "gt_setting", field="s_touch_vol_z",
            setting="TOUCH_VOL_Z_SPRING", detail=("s_touch_vol_z",)),
    TagSpec("strong_rs",          "fraction", term="rs_bonus",      fraction=0.95),
    TagSpec("weekly_reaccum",     "flag", field="htf_w_reaccum"),
    TagSpec("high_adr",           "fraction", term="adr",           fraction=0.80),
    TagSpec("uptrend",            "fraction", term="uptrend_bonus", fraction=0.95),
    TagSpec("worked_equilibrium", "ge_setting", field="traversal_density",
            setting="TRAVERSAL_QUALITY_DENSITY_FULL",
            detail=("traversal_density",)),
)

TAG_IDS: frozenset = frozenset(t.id for t in TAGS)


def tag_rules_manifest() -> dict:
    """The tag registry's hashable projection for the freeze manifest — a
    fire-rule change is a judgment change and must rotate
    engine_config_version like any weight."""
    return {
        t.id: {
            "rule": t.rule, "term": t.term, "fraction": t.fraction,
            "field": t.field, "fields": list(t.fields) if t.fields else None,
            "setting": t.setting, "value": t.value, "warning": t.warning,
        }
        for t in TAGS
    }


def ta_layer_terms() -> tuple[TermSpec, ...]:
    """The terms that make up the Technical Analysis Grade (layer 'ta') and are
    emitted under the CURRENT flags — everything except the regime label."""
    return tuple(t for t in REGISTRY if t.layer == "ta" and t.is_emitted())


def structural_cap_sum() -> float:
    """The grade's fixed 0-100 divisor: summed point caps of the emitted
    ta-layer terms (the regime label is excluded). A pure function of config
    that grows as new terms register — NEVER a per-row or cohort max (the
    present-cap denominator is tested-DEAD backend-side), so the affine map
    stays strictly monotonic and rank-preserving. Zero-cap demoted terms
    contribute zero by arithmetic, never by special-casing. This is the ONE
    derivation — no literal copy may exist anywhere (every hand-copied total
    in this codebase has eventually lied)."""
    return sum(t.cap() for t in ta_layer_terms())
