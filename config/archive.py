"""Archive persistence policy.

Edit defaults here; runtime consumers use config.settings so scoped overrides
and existing monkeypatches continue to share one settings namespace.
"""

# ============================================================
# 7. ARCHIVE & TELEMETRY
# ============================================================
# Live archiving — when True, every daily screener run upserts its full output
# (winners AND the setups that later fizzle) into setup_archive with
# source="screener". This is the fuel the calibration/analysis tools need:
# without live non-winners, every outcome metric is biased by the seed gallery.
# Idempotent per (ticker, scan_date); re-running the same day updates in place.
ARCHIVE_LIVE_SCANS = True
