"""The universe door's floors: what a stock must be before its chart is read.

Edit defaults here; runtime consumers use config.settings so scoped overrides
and existing monkeypatches continue to share one settings namespace.
"""

MIN_PRICE = 3.0
MIN_VOLUME_50D = 50_000          # 50-day average daily volume floor
MIN_YEARLY_RETURN = -0.20        # Allows modest drawdowns (v1 used +0.30)
MIN_MARKET_CAP = 300_000_000     # Dollars; checked on the FIRES after the read (operator 2026-10-03), core/pipeline/screening/market_cap_floor.py
