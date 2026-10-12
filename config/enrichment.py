"""Optional fundamentals and relative-strength enrichment.

Edit defaults here; runtime consumers use config.settings so scoped overrides
and existing monkeypatches continue to share one settings namespace.
"""

# ============================================================
# --- DATA PRIMITIVES (Lane C) ---
# ============================================================
# Additive, NOT-YET-WIRED data layers (core/fundamentals, core/regime) that a
# later scoring/enrichment wave will consume. They read market data ONLY through
# core.pipeline.market_data.providers.get_provider() and compute pure functions over already-
# fetched frames, so nothing here changes the engine's computed output today.
# Every flag defaults OFF; the modules read these lazily via getattr(settings, ...)
# to respect the backend's config-vs-cwd shadowing constraint. Wire-up (feeding
# scoring / archive_models) is a separate, later wave — see each module docstring.

# Fundamentals: the 5 per-ticker metrics (core/fundamentals/metrics.py) — qtr EPS
# growth YoY, qtr sales growth YoY, EPS-growth acceleration, earnings surprise %,
# in-house RS rating. Null-safe (missing -> None). Read via the provider's
# get_income_stmt / get_earnings_dates / info accessors. LIVE 2026-10-03 on the
# operator's word, display + archive only: shown in the detail panel's
# Fundamentals section, archived as fund_*, never scored, never a filter.
FUNDAMENTALS_ENABLED = True
FUNDAMENTALS_EARNINGS_HISTORY_LIMIT = 12   # quarters of earnings history to request
# Point-in-time filing lag: yfinance carries no per-quarter SEC filing date, so a
# quarter keyed by its PERIOD-END date would be read before it was actually filed
# (lookahead leak). A quarter is only treated as usable when
# period_end + this many days <= as_of. 75 days is the conservative ceiling — the
# SEC 10-Q deadline for a non-accelerated filer (45 days) plus margin — so the
# gate can be a few weeks LATE but never admits a not-yet-filed quarter. Earnings
# history is gated on its own report-date index (no lag needed there).
FUNDAMENTALS_FILING_LAG_DAYS = 75

# The fundamentals sheet and the fundamental grade (core/fundamentals/sheet.py and
# grade.py; operator go-ahead Mon 12/10/2026: "yes go ahead with the fundamentals
# sheet ... and lets work on building the fundamental grade"). His list: the last
# four quarters of EPS and sales growth, margin trends, beats and misses, estimate
# revisions, the growth catalyst, earnings-quality concerns. Display and archive
# only: the grade never gates a fire and never moves the setup grade or the tier.
# The thresholds are OUR defaults from the O'Neil / Minervini canon, his to change;
# they are recalibrated later against the archive, never at add time.
FUND_SHEET_QUARTERS = 4                    # quarters (and earnings reports) the sheet shows
FUND_GRADE_EPS_GROWTH_MIN = 0.25           # latest report's EPS up 25%+ on the year (O'Neil's C)
FUND_GRADE_SALES_GROWTH_MIN = 0.25         # latest quarter's sales up 25%+ on the year, or speeding up
FUND_GRADE_BEATS_MIN = 3                   # beats of the estimate in the last four reports, the latest one included
FUND_GRADE_REACTION_RANGES = 2.0           # a report day closing up this many daily ranges (the 20-day ADR) ...
FUND_GRADE_REACTION_VOLUME = 2.0           # ... on this many times the 50-day volume: the market took the news
FUND_GRADE_SBC_MAX = 0.20                  # stock-based pay over this share of sales is an earnings-quality concern
FUND_GRADE_MIN_CHECKS = 5                  # fewer checks with data than this: no letter ("not enough data")
FUND_GRADE_LETTERS = ((0.85, "A"), (0.70, "B"), (0.50, "C"))   # share of the checks passed -> letter; under the last: D
# Earnings-quality flags (the second patch, same day): each raised flag fails the quality check.
FUND_FLAG_UNUSUAL_SHARE = 0.25            # one-time items worth this share of the latest quarter's net income
FUND_FLAG_SHARE_DROP = 0.04               # diluted share count down this much on the year: buybacks lift EPS
FUND_FLAG_ACQUISITION_SHARE = 0.10        # businesses bought for this share of the shown quarters' sales
# SEC filings (data.sec.gov, free, US filers only) fill the year-ago quarters yfinance
# does not keep, so four quarters of year-on-year sales can be read. The SEC refuses
# any request without a contact in its header (fair-access policy); empty turns the
# fill off (tests/conftest.py blanks it for every test, so no test asks the SEC). A data
# source, not a computation: ops-excluded from the engine manifest like the provider.
# Named by the operator, Mon 12/10/2026: "use my email for the SEC".
SEC_CONTACT = "Chrollo guycool5355@gmail.com"

# RS line (core/regime/rs_line.py) — stock/SPY ratio series + rs_line_new_high.
RS_LINE_ENABLED = False
RS_LINE_NEW_HIGH_LOOKBACK = 252            # ratio is a "new high" vs its rolling max over this many sessions (~52w)

# In-house RS rating (core/regime/percentile.py drives it via trailing return).
RS_RATING_LOOKBACK = 252                   # trailing-return window the RS rating percentile-ranks across the universe

# SPDR sector ranking (core/regime/sector_ranking.py) — rank the 11 SPDR sector
# ETFs by sector/SPY rs_ratio momentum over multiple lookbacks.
SECTOR_RANKING_ENABLED = False
SECTOR_RANKING_LOOKBACKS = (21, 63, 126)   # trading-day windows for the multi-horizon sector RS rank
SECTOR_RANKING_ETFS = (
    "XLK", "XLV", "XLF", "XLY", "XLP", "XLC",
    "XLI", "XLE", "XLU", "XLRE", "XLB",
)
