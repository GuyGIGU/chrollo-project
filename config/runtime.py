"""Dashboard output, scan scheduling and alert policy.

Edit defaults here; runtime consumers use config.settings so scoped overrides
and existing monkeypatches continue to share one settings namespace.
"""

# ============================================================
# DASHBOARD
# ============================================================
DASHBOARD_CHART_TIERS = ['S', 'A', 'B', 'C', 'D']   # Default: generate chart data for all setups
DASHBOARD_CHART_DAYS = 300           # Max daily candles shown per chart
DASHBOARD_CHART_WEEKS = 110          # Max weekly candles per higher-timeframe chart
DASHBOARD_CHART_MONTHS = 60          # Max monthly candles per higher-timeframe chart

# ============================================================
# SCHEDULED WEBAPP SCANS
# ============================================================
# The backend scheduler runs in America/New_York time, after the regular US
# close so yfinance has time to publish the completed daily bar.
# 17:00 ET is 00:00 in the operator's local time (Israel), chosen 2026-09-07 so the
# ~17-minute run finishes well before his habitual 01:00-02:00 local power-off, which
# had been killing the scan mid-flight. Do NOT move this earlier than 16:30 ET without
# first measuring the provider: the close is 16:00 ET and SESSION_FINALIZATION_MARGIN_MINUTES
# (30) means 16:30 is the FIRST instant today's bar counts as final, so 16:30 has zero
# slack and a minute earlier silently scans YESTERDAY's session instead.
SCAN_SCHEDULE_HOUR_ET = 17
SCAN_SCHEDULE_MINUTE_ET = 0
FORWARD_RETURNS_MIN_AGE_DAYS = 5
ALERT_WEBHOOK_URL_ENV = "ALERT_WEBHOOK_URL"
ALERT_ON_ZERO_RESULTS = True
ALERT_ON_DEGRADED_FETCH = True    # also alert when a scan succeeds but its fetch-health came back unhealthy (low return ratio) — an early warning before a stale_data failure
