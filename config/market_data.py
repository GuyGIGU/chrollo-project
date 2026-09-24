"""Provider, cache, universe admission and price-series policy.

Edit defaults here; runtime consumers use config.settings so scoped overrides
and existing monkeypatches continue to share one settings namespace.
"""

# Price-series regime (operator rule, 2026-07-02): structural analysis runs on
# REAL traded prices. False = as-traded OHLC (split-adjusted only — exactly what
# TradingView shows); True = legacy dividend+split-adjusted series, which
# repaints history every ex-div and shows prices that were never traded
# (confirmed distorting income names: GOOD/ENIC passed baseline only on
# adjusted data, DKL's box start moved). The cache meta is stamped with the
# regime; a mismatch forces a full cold refetch — regimes are never mixed.
DATA_DIVIDEND_ADJUSTED = False
# ============================================================
# 8. APP / PIPELINE / SCHEDULER / ALERTS
# ============================================================
# Market-data source. The screener fetches its canonical panel through
# core.pipeline.market_data.providers.get_provider(), not directly from a vendor, so a
# bulk-EOD source can be added behind the same contract and validated against
# the incumbent (tools/provider_parity.py) before it feeds an archiveable scan.
# "yahoo" wraps the existing yfinance path verbatim — the default is a no-op.
MARKET_DATA_PROVIDER = "yahoo"

CACHE_FILENAME = "market_data_cache_5y.parquet"
CACHE_META_FILENAME = "cache_meta.json"
MARKET_CONTEXT_FILENAME = "market_context.json"
PARQUET_ENGINE = "pyarrow"
PARQUET_COMPRESSION = "zstd"
DOWNLOAD_PERIOD = "5y"            # 5y of daily history so weekly (~260 bars) and monthly (~60 bars)
                                 # resampling for HTF context has enough depth. The DAILY structure
                                 # read is trimmed back to DAILY_STRUCTURE_PERIOD so this deeper cache
                                 # does NOT change daily behavior (see HTF section below + engine_alpha.structure.context.htf).
                                 # Renaming the cache file forces a clean cold 5y backfill on next run.
TICKER_CACHE_MAX_AGE_DAYS = 1     # Refresh the ticker universe CSV daily
TICKER_SKIPLIST_FILENAME = "ticker_skiplist.txt"  # One symbol per line; skipped before any Yahoo request
TICKER_ADMISSION_ENABLED = True
TICKER_ADMISSION_FILENAME = "ticker_admission.json"
ADMISSION_MIN_HISTORY_BARS = 200   # Same minimum used by the baseline history gate
ADMISSION_YOUNG_RECHECK_DAYS = 21  # Alive but too young: re-test after it may have gained bars
ADMISSION_EMPTY_RECHECK_DAYS = 7   # No Yahoo history: short cooldown before re-probing

# Incremental fetch tuning
TTL_FRESH_HOURS_MARKET = 1        # Re-fetch latest bars if cache is older than this during market hours
TTL_FRESH_HOURS_OFFHOURS = 12     # ...or this outside market hours
FULL_REFRESH_INTERVAL_DAYS = 7    # Force a cold 5y refetch at least weekly
INCREMENTAL_OVERLAP_BDAYS = 5     # Re-download this many business days before last_cached_date for split-probe overlap
INCREMENTAL_MAX_GAP_BDAYS = 10    # Above this gap, fall back to full refetch instead of incremental
MARKET_DATA_MIN_LATEST_COVERAGE = 0.95  # Required latest-session close coverage before cache/archive is trusted
# A daily bar is NOT final at the closing bell: Yahoo keeps settling the last-hour prints
# for a few minutes after the close. Until close + this margin, the current session is
# treated as NOT YET COMPLETE (latest_completed_session), so a partial/forming bar is never
# cached-as-complete nor archived (see _drop_forming_rows). The scheduled scan runs well
# after (18:00 ET) and is unaffected; this only guards near-close MANUAL refreshes/scans.
SESSION_FINALIZATION_MARGIN_MINUTES = 30
# Deep-history corruption floor (the "second half" of the multi-universe cache bug).
# A trusted cache spans years; the NaN-wipe failure leaves recent bars but ~6 bars of
# deep history. Only judged when the PANEL itself spans >= MIN_HISTORY_BARS rows (so a
# short/new cache is never falsely flagged); below MIN_HISTORY_COVERAGE of symbols
# clearing the bar floor => cache is deep-history-corrupted => force a full cold refetch.
# 100 is well below ADMISSION_MIN_HISTORY_BARS(200) yet ~16x above a wiped cache.
MARKET_DATA_MIN_HISTORY_BARS = 100
MARKET_DATA_MIN_HISTORY_COVERAGE = 0.5
# The provider can simply LOSE a whole trading session. Measured 2026-07-24: a normal
# Friday (S&P 500 settled 7,411.98) for which Yahoo carries no bar at all — every symbol
# probed goes 07-23 -> 07-27. Our calendar was right; the data was missing. Every freshness
# gate keys on Close, so that reads as 0% coverage and a cache complete through 07-23 looks
# dead. Allow EVALUATION (never archiving) to proceed on a cache this many completed
# sessions behind, provided the cache's own last session clears
# MARKET_DATA_MIN_LATEST_COVERAGE. 0 restores the previous hard block.
MARKET_DATA_EVALUATE_MAX_LAG_SESSIONS = 1
# A cold refetch that fails its coverage gate persists nothing, so repeating it for the SAME
# expected session re-pays the full-universe download (~30 min measured) to learn the same fact.
# When a full fetch proves a session essentially unpublished upstream, that session is recorded in
# cache_meta's `absent_sessions` ledger and no further cold fetch is attempted FOR THAT SESSION.
# Deliberately not time-bounded: a wall-clock window is dead exactly when it is needed (the measured
# repeats were ~24h apart, and a Friday loss spans ~72h to Monday's close). A newly completed
# session always gets a fresh attempt, and the operator's Refresh click clears the ledger, so the
# human override stays intact. Capped so meta cannot grow without bound.
ABSENT_SESSION_LEDGER_MAX = 20
# A session counts as "the provider does not have this" only at essentially-zero coverage — the
# measured 2026-07-24 incident recorded 0.0018. A partial response is a repair target, not an
# absent session, and must stay retryable.
PROVIDER_ABSENT_SESSION_MAX_COVERAGE = 0.02
LATEST_REPAIR_BATCH_SIZE = 100     # Smaller latest-bar repair batches after a sparse Yahoo response
LATEST_REPAIR_SLEEP_SECONDS = 2.0  # Gentle pause between repair batches to reduce Yahoo rate limits
# When essentially EVERY symbol lacks the latest close the cause is provider-side (an absent
# session), not per-symbol sparseness, and the batch-by-batch repair cannot help — skip it instead
# of paying ~55 serial batches. Uses the same "essentially unpublished" bar as the absent-session
# ledger, deliberately NOT a 50% one: between 51% and 95% missing the repair CAN lift a partial
# response back over the trust bar, and discarding it there would throw away a ~30-minute download.
LATEST_REPAIR_MAX_MISSING_FRACTION = 1.0 - PROVIDER_ABSENT_SESSION_MAX_COVERAGE
MARKET_DATA_REPAIR_FIRST_RETRY_MINUTES = 10   # Sparse eligible-symbol repair: first unchanged retry window
MARKET_DATA_REPAIR_SECOND_RETRY_MINUTES = 20  # Sparse eligible-symbol repair: second unchanged retry window

# Outbound Yahoo request rate limit (core.pipeline.market_data.rate_limit). yfinance spawns its
# own download threads and the screener fans the universe across a worker pool, so
# without a SHARED ceiling the concurrent workers each throttle independently and
# collectively burst Yahoo into 429s — the 2%-coverage stale-data days. Every
# yf.download call now passes through ONE process-global token bucket, and the
# download pool is bounded (workers) to cap concurrent connections. (yfinance 1.2.1
# requires a curl_cffi session and rejects a stdlib requests.Session, so a
# requests-ratelimiter LimiterSession can't be injected — hence the explicit gate.)
# Tuned from read-only probes on the active-ready universe. Higher rates (40-70/s)
# can complete after retries, but they trip Yahoo's rolling Too Many Requests path.
YAHOO_RATE_LIMIT_ENABLED = True
YAHOO_RATE_LIMIT_PER_SEC = 20.0    # sustained outbound requests/sec to Yahoo (global ceiling)
YAHOO_RATE_LIMIT_BURST = 40        # token-bucket capacity (max short burst)
YAHOO_DOWNLOAD_WORKERS = 24        # bounded download-pool size (caps simultaneous connections)
YAHOO_RATE_LIMIT_BACKOFF_SECONDS = 45.0  # shared cooldown after explicit Yahoo 429/rate-limit errors
YAHOO_BACKOFF_JITTER = 0.5         # fraction of each retry backoff that is randomized (0=off, 0.5=lower half random) so concurrently rate-limited workers don't retry in lockstep
YAHOO_COOLDOWN_JITTER_SECONDS = 2.0  # after a shared 429 cooldown clears, each worker waits up to this many extra random seconds so they don't all resume at once (thundering-herd guard)

# Split-detection probe — EVERY cached ticker is checked on the incremental
# overlap window (under the as-traded regime a split is the only corporate
# action that shifts the series, so this probe is the entire defense).
SPLIT_PROBE_DRIFT_THRESHOLD = 0.005          # Ticker-level: ratio (fresh/cached) deviating by > 0.5% on overlap = split
SPLIT_PROBE_UNIVERSE_DRIFT_PCT = 0.02        # If > 2% of probed tickers drift → cold refetch

# Dead-ticker quarantine — the universe (~6.9k NASDAQ-traded symbols) has a long
# tail of delisted / halted / invalid tickers that return nothing from Yahoo every
# run, wasting requests, driving 429s, and triggering per-ticker recovery storms.
# Symbols that come back empty on repeated COLD full-refetches (the strongest death
# signal) are skipped, then re-probed after a cooldown so a re-listing recovers.
# Updates are gated on a healthy run so a rate-limited day can't quarantine the
# whole universe. Index symbols are never quarantined. See core/pipeline/market_data/fetch_health.py.
QUARANTINE_ENABLED = True
QUARANTINE_FILENAME = "ticker_quarantine.json"
QUARANTINE_EMPTY_STREAK = 2          # consecutive empty cold-refetches before quarantine
QUARANTINE_COOLDOWN_DAYS = 7         # re-probe a quarantined ticker after this many days
QUARANTINE_MIN_HEALTHY_RATIO = 0.85  # only judge deadness on a near-complete run: a rate-limited day (429s crater the return ratio) falls below this and can't penalize missing tickers, while a healthy run returns ~95%+ of requested

# Market context cache
SPY_SYMBOL = "SPY"                # Stored in the parquet alongside the universe (not screened)
INDEX_SYMBOLS = ["SPY", "QQQ"]    # Market-regime indexes stored with the universe
MARKET_CONTEXT_TTL_HOURS_MARKET = 1
MARKET_CONTEXT_TTL_HOURS_OFFHOURS = 12
