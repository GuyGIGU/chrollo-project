"""
THE VISUAL STRUCTURE ENGINE — "how we SEE the chart".

Pure geometry and measurement, zero opinion. Everything in this package looks at
price/volume bars and reports *facts*: where the consolidation box is, how tight
it is, where the LPS sits, how volume behaved at the edges, how the contractions
progressed. It never decides whether a setup is "good" — that is the Scoring
Engine's job (``engine_alpha.scoring``).

The engine reads a daily chart left-to-right and assembles ONE Wyckoff narrative
through these explicit layers — the order ``read_structure`` walks them:

    Trend          a qualifying Stage-2 advance + its daily range / strength context
    Consolidation  locate the equilibrium box (BC/AR -> a genuinely worked R/S range)
    Phase A        the root swing: climax -> automatic reaction; anchors R/S
    Phase B        the worked equilibrium oscillating between the rails
    Phase C        an OPTIONAL spring: an excursion below S that reclaims & holds
    Phase D        the right side: the LPS (required minimum) + supporting evidence
    LPS            the last point of support — the actionable trigger shelf

``read_structure(df, atr)`` is the reader; the ``Structure`` it returns is the
single daily-chart reading object every consumer (chart overlay, scope, scoring,
archive) reads from. The per-layer validators ("bricks") live in
``engine_alpha.structure.bricks`` and are injected into the reader, so the spine stays
testable in isolation with fakes:

    Trend / Phase A   bricks.find_root_swing, bricks.resolve_phase_a
    Consolidation/B   bricks.validate_equilibrium  (+ consolidation.py, box_primitives.py)
    Phase C           bricks.find_spring
    Phase D           bricks.find_lps, bricks.find_inner_box, phase_d.resolve_phase_d_boundary
    LPS               lps.detect_lps_candidates, lps.select_active_lps_candidate

Public API — grouped by layer (see ``__all__`` below).
"""

# ── The reader + its single source of truth ─────────────────────────────────
# narrative's module-level deps are leaf submodules (lps, phase_d); the real
# bricks load lazily at call time, so importing it here is circular-safe.
from engine_alpha.structure.narrative import Structure, read_structure

# ── Layer: Trend — a qualifying Stage-2 advance + range / strength context ───
from engine_alpha.structure.indicators import (
    adr_pct,
    calculate_adx,
    calculate_atr,
    distance_to_52w_high_pct,
    trend_template,
)

# ── Layer: Consolidation — locate the equilibrium box, measure how worked it is ─
from engine_alpha.structure.consolidation import detect_boxes, find_outer_box
from engine_alpha.structure.metrics import (
    descent_tail_rejects,
    measure_dwell_balance,
    measure_equilibrium,
    measure_gate_margins,
)

# ── Layer: Phase B texture — the VCP progressive-tightening / quiet-bar / touch footprint ─
from engine_alpha.structure.metrics import (
    assemble_box_narrative,
    measure_bar_compression,
    measure_contractions,
    measure_support_slope,
    measure_touch_volume,
)
from engine_alpha.structure.bin_features import measure_bins

# ── Layer: Phase D / LPS — the right-side trigger shelf + support-test staircase ─
from engine_alpha.structure.lps import (
    detect_lps,
    detect_lps_candidates,
    detect_lps_tests,
    lps_range_threshold,
    select_active_lps_candidate,
)

# ── Scope — clip the assembled narrative to the actionable window ────────────
from engine_alpha.structure.scope import scope_consolidation

# ── Layer: HTF — the same Trend+Box engine on weekly/monthly bars ────────────
from engine_alpha.structure.htf import (
    htf_stage2,
    read_htf_context,
    resample_ohlc,
    timeframe_windows,
)

__all__ = [
    # reader + reading object
    "read_structure",
    "Structure",
    # Trend
    "trend_template",
    "distance_to_52w_high_pct",
    "adr_pct",
    "calculate_atr",
    "calculate_adx",
    # Consolidation
    "detect_boxes",
    "find_outer_box",
    "measure_dwell_balance",
    "measure_equilibrium",
    "measure_gate_margins",
    "descent_tail_rejects",
    # Phase B texture
    "assemble_box_narrative",
    "measure_bar_compression",
    "measure_contractions",
    "measure_support_slope",
    "measure_touch_volume",
    "measure_bins",
    # Phase D / LPS
    "detect_lps",
    "detect_lps_candidates",
    "detect_lps_tests",
    "lps_range_threshold",
    "select_active_lps_candidate",
    # scope
    "scope_consolidation",
    # HTF
    "read_htf_context",
    "resample_ohlc",
    "htf_stage2",
    "timeframe_windows",
]
