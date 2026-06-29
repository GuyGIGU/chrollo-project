"""Regime / relative-strength data primitives (Lane C).

Additive, flag-gated modules a later scoring wave will consume:

  * ``percentile``      — self-normalizing 0..100 percentile rank across a universe.
  * ``rs_line``         — stock/SPY ratio series + ``rs_line_new_high`` boolean.
  * ``sector_ranking``  — rank the 11 SPDR sector ETFs by sector/SPY momentum.

Each module separates a PURE compute core (takes already-fetched frames/series,
no IO, deterministic, unit-testable offline) from an optional thin fetch wrapper
that reaches market data only through ``core.pipeline.providers.get_provider()``.
Nothing here is wired into scoring / evaluation / archive yet.
"""
