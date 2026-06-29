"""Fundamentals data primitives (Lane C).

A single module, ``metrics``, computing exactly five per-ticker fundamentals a
later scoring wave will consume:

  1. quarterly EPS growth YoY
  2. quarterly sales (revenue) growth YoY
  3. EPS-growth acceleration (latest YoY vs the prior quarter's YoY)
  4. earnings surprise %  (most recent reported vs estimate)
  5. in-house RS rating   (percentile of trailing return across the universe)

All metrics are null-safe: missing / shallow / gappy history yields ``None`` for
that metric, never an exception. Data is read ONLY through the provider seam
(``get_income_stmt`` / ``get_earnings_dates`` / ``info``), which wraps the MODERN
yfinance surfaces — the legacy ``.earnings`` / ``.quarterly_financials`` /
``.quarterly_earnings`` properties return empty in current yfinance and are never
touched. Nothing here is wired into scoring / evaluation / archive yet.
"""
