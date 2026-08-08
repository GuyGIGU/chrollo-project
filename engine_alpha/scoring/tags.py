"""The fired-tags resolver — chip verdicts computed ONCE, engine-side.

Build task 10: the judgment layer that lived only in frontend JS
(setupTagsData.js firesAt fractions, the touch-volume z trio, the density
literal) is absorbed into the ONE declarative registry
(``taxonomy.TAGS``); this module interprets it over the canonical result
row. Resolved verdicts are serialized, archived, and served verbatim — no
route or component ever re-derives a tag (EC-28: the wire carries verdicts,
never rules).

The resolver reads the SAME canonical result row all three writers read
(underscore-prefixed facts + the nested ``_sub_scores``); the seed twin's
adapted row (bare keys) works identically via the ``prefixed`` switch.
Presentation (labels, tones, group order, chip caps, emoji) stays in the
frontend's wireVocabulary — none of it lives here.
"""
from __future__ import annotations

from typing import Optional

from config import settings
from engine_alpha.scoring import taxonomy


def _finite_or_none(value) -> Optional[float]:
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return f if f == f and f not in (float("inf"), float("-inf")) else None


def _detail_value(value):
    """Quarantine non-finite NUMERIC detail facts to None at fire time —
    the fire-rules run through _finite_or_none but the detail dict used to
    copy facts RAW, and a NaN inside the JSON cell is invisible to the
    column-level EC-2 scrub (2026-08-08 review, finding 5). Strings and
    None pass through untouched (bin_c_type, htf_m_trend_state)."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value if value == value and value not in (
            float("inf"), float("-inf")) else None
    return value


def resolve_fired_tags(row: dict, *, prefixed: bool = True) -> list[dict]:
    """Resolve the registry's fire-rules over one canonical result row.

    Returns ``[{"id": ..., "detail": {...}}, ...]`` in REGISTRY order
    (deterministic; display ordering/weights are presentational and stay
    frontend-side). A missing or non-finite fact never fires a rule
    (absence is never evidence). A ZERO-cap term's fraction chip is DEAD BY
    DESIGN — the demoted rs/uptrend chips can never fire while their caps
    are 0, by rule rather than by the stale-JS-cap accident.
    """
    sub = row.get("_sub_scores" if prefixed else "sub_scores") or {}
    if not isinstance(sub, dict):
        sub = {}

    def fact(name: str):
        value = row.get(("_" + name) if prefixed else name)
        if value is None and name == "traversal_density":
            # Not a stored fact — derived from the trav counts exactly as the
            # wire serializes it (round 3dp), so the chip verdict matches what
            # the JS rule judged against. The wire's own literal folds onto
            # this helper at the legacy-deletion wave (task 15).
            n_full = _finite_or_none(fact("trav_n_full_traversals"))
            n_swings = _finite_or_none(fact("trav_n_swings"))
            if n_full is not None and n_swings:
                return round(n_full / n_swings, 3)
            return None
        return value

    caps = taxonomy.caps()
    fired: list[dict] = []
    for tag in taxonomy.TAGS:
        hit = False
        if tag.rule == "fraction":
            cap = caps.get(tag.term, 0.0)
            points = _finite_or_none(sub.get(tag.term))
            hit = cap > 0 and points is not None and points >= tag.fraction * cap
        elif tag.rule == "flag":
            hit = bool(fact(tag.field))
        elif tag.rule == "gt_setting":
            v = _finite_or_none(fact(tag.field))
            hit = v is not None and v > float(getattr(settings, tag.setting))
        elif tag.rule == "lt_setting":
            v = _finite_or_none(fact(tag.field))
            hit = v is not None and v < float(getattr(settings, tag.setting))
        elif tag.rule == "ge_setting":
            v = _finite_or_none(fact(tag.field))
            hit = v is not None and v >= float(getattr(settings, tag.setting))
        elif tag.rule == "eq":
            hit = fact(tag.field) == tag.value
        elif tag.rule == "any_gt0":
            for name in tag.fields or ():
                v = _finite_or_none(fact(name))
                if v is not None and v > 0:
                    hit = True
                    break
        else:  # pragma: no cover — a new rule kind must be added HERE deliberately
            raise ValueError(f"unknown tag rule kind {tag.rule!r} on {tag.id!r}")
        if hit:
            fired.append({
                "id": tag.id,
                "detail": {name: _detail_value(fact(name))
                           for name in tag.detail},
            })
    return fired
