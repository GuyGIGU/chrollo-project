"""Adapter: canonical live-evaluation result -> seed/archive-writer key shape.

The live path (`engine_alpha.evaluation._build_live_result`) is the single source of
truth for an evaluation result. It emits a dict whose internal fields are `_`-prefixed
(e.g. ``_lps_descent_frac``, ``_bin_a_bars``) plus a few display-named fields
(``Setup``, ``Score``, ``Current Price`` ...).

The seed archive writer (`core.archive.seed`) historically consumed a *separate*,
unprefixed result dict produced by a hand-mirrored twin (`_evaluate_at_date`). To unify
the two engines onto one numeric path without rewriting the writer's ~150-line column
mapping, this module maps the canonical dict to exactly the unprefixed keys the writer
reads via ``best_result.get(...)``.

Pure function, no I/O. The only new surface introduced by the live/seed unification.

Rule:
  * Most fields: strip a single leading underscore (``_eq_r_touches`` -> ``eq_r_touches``,
    ``_bin_a_bars`` -> ``bin_a_bars``, ``_stage2_trend_pass`` -> ``stage2_trend_pass``,
    ``_htf_w_*`` -> ``htf_w_*`` which ``htf_archive_values(..., prefixed=False)`` then reads).
  * A small set of fields are renamed, not just unprefixed (display names and a handful of
    anchor/length fields). Those are listed in ``_CANONICAL_TO_SEED`` and applied last so
    they win over the strip pass.

Extra keys produced by the strip pass (e.g. ``R``, ``Ticker``, ``base_len``) are harmless:
the writer builds its row from an explicit ``values=dict(...)`` block and only reads the
keys it names, so unreferenced keys are ignored.
"""
from __future__ import annotations

from typing import Any, Dict

# Canonical (live `_build_live_result`) key -> the key the seed writer reads.
# Only fields whose seed name is NOT simply the unprefixed canonical name appear here.
_CANONICAL_TO_SEED = {
    "Setup": "setup_type",
    "Tier": "tier",
    "Score": "score",
    "Current Price": "current_price",
    "Box Width": "box_width",
    "Touches": "touches",
    "ATR Ratio": "atr_ratio",
    "Breach Days": "breach_days",
    "_R": "r_level",
    "_S": "s_level",
    "_base_len": "base_length",
    "_lps_len": "lps_length",
    "_r_anchor_bar": "r_anchor",
    "_s_anchor_bar": "s_anchor",
    "_bars_since_BC": "bars_since_BC",
}


def seed_row_from_result(result: Dict[str, Any]) -> Dict[str, Any]:
    """Return the canonical evaluation ``result`` re-keyed the way the seed archive
    writer consumes it. Pure; does not mutate ``result``."""
    # 1. Strip a single leading underscore from every internal field. Display-named
    #    fields (no leading underscore) pass through unchanged here and are fixed below.
    out: Dict[str, Any] = {
        (k[1:] if k.startswith("_") else k): v for k, v in result.items()
    }
    # 2. Apply explicit renames last so they override any strip-pass value.
    for canon_key, seed_key in _CANONICAL_TO_SEED.items():
        if canon_key in result:
            out[seed_key] = result[canon_key]
    return out
