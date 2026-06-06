"""
THE VISUAL STRUCTURE ENGINE — "how we SEE the chart".

Pure geometry and measurement, zero opinion. Everything in this package looks
at price/volume bars and reports *facts*: where the consolidation box is, how
tight it is, where the LPS sits, how the volume behaved at the edges, and how
the contractions progressed. It never decides whether a setup is "good" — that
is the Scoring Engine's job (``core.scoring``).

Public API:
    detect_boxes         -> live parent+inner detector
    find_consolidation   -> legacy single-box hierarchical detector
    find_outer_box       -> parent outer-box detector
    measure_bar_compression -> low-spread / quiet-bar texture inside the base
    measure_contractions -> the VCP progressive-tightening footprint
    measure_support_slope-> the ascending-support / higher-lows footprint
    measure_touch_volume -> volume z-scores at the R/S touch bars
    measure_bins         -> per-region (A/B/D/LPS) size/range/volume + Last Supper
    detect_lps           -> the Last-Point-of-Support / spring finder
    adr_pct              -> Qullamaggie Average Daily Range %
    trend_template       -> Minervini Stage-2 trend-template criteria
    calculate_atr / calculate_adx -> volatility & trend-strength math
"""
from core.structure.bin_features import measure_bins
from core.structure.consolidation import detect_boxes, find_consolidation, find_outer_box
from core.structure.metrics import (
    measure_bar_compression,
    measure_contractions,
    measure_support_slope,
    measure_touch_volume,
)
from core.structure.indicators import adr_pct, calculate_adx, calculate_atr, trend_template
from core.structure.lps import detect_lps
from core.structure.scope import scope_consolidation

__all__ = [
    "find_consolidation",
    "find_outer_box",
    "detect_boxes",
    "measure_bar_compression",
    "measure_contractions",
    "measure_support_slope",
    "measure_touch_volume",
    "measure_bins",
    "detect_lps",
    "scope_consolidation",
    "adr_pct",
    "trend_template",
    "calculate_atr",
    "calculate_adx",
]
