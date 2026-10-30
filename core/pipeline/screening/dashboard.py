# ============================================================================
# ⚠️  DO NOT DELETE — THIS MODULE IS LIVE, NOT RETIRED HTML RESIDUE  ⚠️
# ----------------------------------------------------------------------------
# The name `generate_dashboard` (and this module's old home, output/) LOOK like
# the retired static-HTML dashboard, but they are NOT. This module is the LIVE writer of
# the React frontend's data artifact and is on the hot path of every scan.
# A name-trusting dead-code sweep that deletes this file WILL break scan -> UI.
#
#   • Writes   output/screener_data.json  (+ per-universe variants) — the data
#     artifact the React frontend loads. No writer => the UI never updates.
#   • Called   on EVERY scan by core/pipeline/screening/scan_job.py (~lines 176 & 186).
#   • Exports  SECTOR_ETF_NAMES — imported by
#     webapp/backend/domains/screener/router.py for the sector drill-down.
#   • Coupled  to DASHBOARD_CHART_TIERS (tiering of the chart payload).
#   • Emits    the "UI update available on local webapp." stdout sentinel that
#     the frontend's scan stream waits on to reveal fresh results.
#
# Renaming the module/function is a DEFERRED nicety — do it deliberately and
# update ALL call sites + imports above; do not "clean it up" as dead code.
# ============================================================================
"""
Data export module for Wyckoff VCP/LPS Screener.

LIVE artifact writer — DO NOT DELETE (see banner above). Despite being named
generate_dashboard, this is the current, on-every-scan
writer of the React frontend's JSON data artifact (output/screener_data.json),
NOT the retired static-HTML dashboard. It also exports SECTOR_ETF_NAMES for the
sector drill-down and prints the "UI update available on local webapp." reveal
sentinel the frontend's scan stream watches. Removing or stubbing this module
silently breaks the scan -> UI pipeline.
"""
import os
import json
import math
import sys

import pandas as pd

from config import settings
from core.archive.writer import load_sector_etf_cache, save_sector_etf_cache
from core.fundamentals import industry as _industry
from core.pipeline.market_data.candles import chart_candles, clean_daily_frame, daily_candles
from core.pipeline.json_safety import to_json_safe
from core.pipeline.universe.descriptor import resolve_universe
# Volume at a key point: ONE measure (EC-3), beside the archive column it also fills,
# so the panel and the new reader's archive read the same number.
from engine_alpha.two_eyes_archive import SCREEN_KEY, volume_vs_50d as _volume_vs_50d

PROJECT_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..'))
BACKEND_DIR = os.path.join(PROJECT_ROOT, "webapp", "backend")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "output")
SECTOR_ETF_CACHE_PATH = os.path.join(OUTPUT_DIR, "sector_etf_cache.json")

SECTOR_ETF_NAMES = {
    "XLB": "Materials",
    "XLC": "Communication Services",
    "XLE": "Energy",
    "XLF": "Financials",
    "XLI": "Industrials",
    "XLK": "Technology",
    "XLP": "Consumer Staples",
    "XLRE": "Real Estate",
    "XLU": "Utilities",
    "XLV": "Health Care",
    "XLY": "Consumer Discretionary",
}


# Same on-disk cache the archive writer keeps; ONE implementation lives there
# (conventions.md EC-3) — these thin wrappers only bind this module's path.
def _load_sector_etf_cache():
    return load_sector_etf_cache(SECTOR_ETF_CACHE_PATH)


def _save_sector_etf_cache(cache):
    save_sector_etf_cache(cache, SECTOR_ETF_CACHE_PATH)


def _resolve_sector_etf(ticker):
    try:
        if BACKEND_DIR not in sys.path:
            sys.path.append(BACKEND_DIR)
        from archive_models import get_sector_etf
        return get_sector_etf(ticker) or ""
    except Exception:
        return ""


def _sector_etf_for_ticker(ticker, sector_etf_cache):
    normalized = str(ticker).upper()
    if normalized not in sector_etf_cache:
        sector_etf_cache[normalized] = _resolve_sector_etf(normalized)
        _save_sector_etf_cache(sector_etf_cache)
    return sector_etf_cache.get(normalized) or None


def _industry_cache_path():
    return _industry.cache_path()


def _group_facts(results_df, tickers, data, universe_type):
    """ticker -> the group facts for every fired row (his yes, Fri 23/10/2026):
    the industry its fundamentals sheet names, how many of that industry fired
    tonight, how many in the last 10 trading days (the archive's own nights plus
    tonight, each name once), and the group's size in the scanned universe
    through the industry cache. None for a row that names no industry. Display
    only, resolved here so the browser only prints it (EC-28): no sort, no gate.
    Tonight's sheets and the archived ones are remembered in the cache, so the
    group's size grows toward the universe night by night."""
    path = _industry_cache_path()
    cache = _industry.load_cache(path)
    sessions = getattr(data, "index", None)
    if sessions is None or len(sessions) == 0:
        last = pd.Timestamp.today().normalize()
        first = last - pd.Timedelta(days=14)
    else:
        last = pd.Timestamp(sessions[-1])
        first = pd.Timestamp(sessions[max(len(sessions) - 10, 0)])
    tonight_day, since = str(last.date()), str(first.date())
    tonight = {}
    for _, row in results_df.iterrows():
        ticker, sheet = row['Ticker'], row.get('_fund_sheet')
        _industry.remember(cache, ticker, sheet, tonight_day)
        tonight[ticker] = _industry.industry_of_sheet(sheet) or _industry.industry_of(cache, ticker)
    recent = _industry.recent_fires(since, tonight_day,
                                    universe_type or resolve_universe(None).universe_type)
    for ticker, name in recent.items():
        _industry.remember_name(cache, ticker, name, since)
    recent = {ticker: name or _industry.industry_of(cache, ticker) for ticker, name in recent.items()}
    counts = _industry.group_counts(tonight, recent, _industry.members_of(tickers, cache))
    _industry.save_cache(cache, path)
    return {ticker: ({'industry': name, **counts[name]} if name else None) for ticker, name in tonight.items()}


def _round_opt(value, digits):
    """Display-round a nullable scalar: None passes through (NULL = not
    measured — never coerced to a number at the wire)."""
    return None if value is None else round(float(value), digits)


# The advisory facts the scan attaches to ANY firing row after the read (the
# fundamentals and RS-line post-pass, the market cap the $300M floor stamps on
# the fires it kept) — graded chip data, NOT scored, NOT a veto, None while
# their flags are off. Whichever reader fired, the row carries them, so both
# chart shapes take this ONE list. The universe RS rating rides in the
# leadership read (`_leadership_read`), which both shapes take too.
ADVISORY_KEYS = (
    'fund_eps_growth_yoy', 'fund_sales_growth_yoy', 'fund_eps_growth_accel',
    'fund_earnings_surprise', 'fund_quarter_end', 'days_to_earnings',
    'market_cap', 'rs_line_latest', 'rs_line_new_high',
    # the fundamentals sheet (verdicts resolved: each check passed / failed / not
    # known, with its words) and the fundamental grade (2026-10-12)
    'fund_sheet', 'fund_grade', 'fund_grade_score',
)


def _leadership_read(row, df):
    """The leadership read (operator go-ahead 2026-10-02): the STOCK, kept apart
    from the setup's grade — none of it is scored or gated. ONE builder for both
    chart shapes (go-live plan task 3; EC-3), because none of it depends on the
    reader: the RS rating ranks twelve-month strength against every stock the
    scan read (attached after the read); the trend template is Minervini's seven
    price criteria passed (the archived count), the old chain's own measure on
    the old chain's own frame for either reader's fire; the dollar volume is the
    50-day liquidity off the frame. Two of the template's own measures ride
    along for the stage read (go-ahead 2026-10-03): the fraction above the
    52-week low and the 200-day average's one-month change in percent (archive
    names, archive values). The stage itself (1 to 4, on the weekly chart) and
    the week the advance began ride beside them (Fri 16/10/2026,
    ``engine_alpha/stage_read.py``): a new-reader fire carries them, an
    old-reader fire leaves them empty."""
    return {
        'rs_rating': row.get('_rs_rating'),
        'stage2_trend_pass_count': row.get('_stage2_trend_pass_count'),
        'stage2_52w_low_pct': row.get('_stage2_52w_low_pct'),
        'stage2_ma200_slope_1m_pct': row.get('_stage2_ma200_slope_1m_pct'),
        'cycle_stage': row.get('_cycle_stage'),
        'advance_start': row.get('_advance_start'),
        'advance_weeks': row.get('_advance_weeks'),
        'dollar_volume_50d': _dollar_volume_50d(df),
    }


def _timeframe_box(block):
    """The weekly and monthly panes' box: the parent box's own R and S (a box is
    a price pair; it holds on every timeframe — decision A of the retirement,
    Fri 30/10/2026), in the dict the panes read: the rails, the day the box
    opened (where the rails start), the anchor days that set the rails (the
    grey limb) and the LPS days (gold). None when the block holds no parent."""
    parent = next((box for box in block['boxes'] if box['role'] == 'parent'), None)
    if parent is None:
        return None
    anchors = [day for day in (parent.get('r_day'), parent.get('s_day')) if day]
    lps = block.get('lps') or {}
    return {
        'r': round(float(parent['r']), 4),
        's': round(float(parent['s']), 4),
        'start_date': parent.get('opened'),
        'limb_start_date': min([parent['opened'], *anchors]) if parent.get('opened') else (min(anchors) if anchors else None),
        'limb_end_date': max(anchors) if anchors else None,
        'lps_start_date': lps.get('start'),
        'lps_end_date': lps.get('end'),
    }


def _two_eyes_chart(row, block, tf_set, sector_etf, df, group=None):
    """A fire's chart (build task 15 of the two-eyes reader).

    The frame's own candles, the verdicts every row carries (the lines, the
    tier, the score, the price, the trigger), the sector, the advisory facts,
    the leadership read, the stock's ADR and the volume at key points (the
    volume read on the reader's own LPS pullback and spring days, empty when it
    has none), the grade's 0-100 number, and THE block: the boxes with their
    roles and each line's day, the LPS and the box it was read against, the
    state word, the grade. The wire carries days and resolved prices; the
    browser only finds each day's bar and draws. A key this reader does not
    fill is ABSENT, never a null a panel reads as "this row predates the read",
    never a zero that reads as measured. The weekly and monthly panes carry
    the parent box's own rails (``_timeframe_box``).
    """
    timeframe_box = _timeframe_box(block)
    return {
        'candles': tf_set['candles'],
        'volumes': tf_set['volumes'],
        'weekly_candles': tf_set['weekly_candles'],
        'weekly_volumes': tf_set['weekly_volumes'],
        'weekly_box': timeframe_box,
        'monthly_candles': tf_set['monthly_candles'],
        'monthly_volumes': tf_set['monthly_volumes'],
        'monthly_box': timeframe_box,
        'R': round(float(row['_R']), 2),
        'S': round(float(row['_S']), 2),
        # Trading sessions in the parent box through this read, not the
        # grade's shorter, pre-SOS base_days window.
        'base_len': _two_eyes_base_length(block, df),
        'tier': row['Tier'],
        'score': row['Score'],
        'setup': row['Setup'],
        'sector_etf': sector_etf,
        'sector_name': SECTOR_ETF_NAMES.get(sector_etf) if sector_etf else None,
        # the group facts (2026-10-23): the industry and "N of M fired tonight / in 10 days", shown only
        'group': group,
        'price': round(float(row['Current Price']), 2),
        'trigger': round(float(row['_trigger_price']), 2),
        **_leadership_read(row, df),
        # The stock's ADR (the lens's leadership grid shows it), as the old shape carries it.
        'adr_pct': row.get('_adr_pct'),
        'lps_volume_ratio': _volume_vs_50d(df, block['lps']['end'], first_day=block['lps']['start']),
        'spring_volume_ratio': _volume_vs_50d(df, row.get('_spring_date')),
        **{key: row.get('_' + key) for key in ADVISORY_KEYS},
        'ta_grade': _round_opt(row.get('_ta_grade'), 1),
        'two_eyes': block,
    }


def _two_eyes_base_length(block, df):
    parent = next((box for box in block['boxes'] if box['role'] == 'parent'), None)
    if parent is None or df.empty:
        return None
    start = pd.Timestamp(parent['opened'])
    end = pd.Timestamp(parent['end']) if parent['end'] else df.index[-1]
    if start not in df.index or end not in df.index:
        return None
    return int(((df.index >= start) & (df.index <= end)).sum())


def _dollar_volume_50d(df):
    """Average daily dollar volume (close x volume) over the last 50 trading
    days — the liquidity half of the leadership read. Display only: it gates
    nothing (the entry filter's floor is in shares). None when unreadable."""
    traded = [float(v) for v in (df["Close"] * df["Volume"]).iloc[-50:]
              if math.isfinite(v)]
    return round(sum(traded) / len(traded)) if traded else None


def _json_safe(obj):
    """Recursively coerce NumPy/Pandas scalars and replace NaN/Inf with None.

    Starlette's JSONResponse serves /screener-data/ with allow_nan=False, so a
    single NaN/Inf anywhere in the payload makes the endpoint 500 — and the
    frontend silently stays on "Loading Screener Data...". Sanitizing here, at
    the one place the file is written, guarantees the served file is always
    serveable regardless of which metric produced a degenerate value.
    """
    return to_json_safe(obj)

def _extract_chart_data(data, results_df, tickers, universe_type=None):
    """Extract OHLCV data as JSON-serializable dicts for each chartable ticker."""
    chart_data = {}
    chart_candidates = results_df[results_df['Tier'].isin(settings.DASHBOARD_CHART_TIERS)]
    sector_etf_cache = _load_sector_etf_cache()
    # The group facts are display only: a fault there blanks the group, never the night's charts.
    try:
        groups = _group_facts(results_df, tickers, data, universe_type)
    except Exception as e:
        print(f"  Group facts error: {type(e).__name__}: {e}")
        groups = {}

    for _, row in chart_candidates.iterrows():
        ticker = row['Ticker']
        try:
            # Multi-panel detection by column shape (the health board's
            # predicate) — a one-name MultiIndex panel still slices, and a
            # plain dict-of-frames (the cascade harness) slices too.
            columns = getattr(data, "columns", None)
            is_multi = columns is None or getattr(columns, "nlevels", 1) > 1
            df = clean_daily_frame(data[ticker] if is_multi else data)

            # The complete D/W/M candle set from the ONE shared builder
            # (core.pipeline.market_data.candles — the EC-3 fold with the watchlist candle
            # endpoint); weekly/monthly resample from the FULL daily history,
            # caps live in settings only.
            tf_set = chart_candles(df)
            # Every fire carries ONE dated block: the reader's boxes, LPS, state and grade.
            block = row.get(SCREEN_KEY)
            if not isinstance(block, dict):
                print(f"  Chart data error on {ticker}: the row carries no {SCREEN_KEY} block")
                continue
            chart_data[ticker] = _two_eyes_chart(
                row, block, tf_set,
                _sector_etf_for_ticker(ticker, sector_etf_cache), df, groups.get(ticker))
        except Exception as e:
            print(f"  Chart data error on {ticker}: {e}")

    return chart_data


def build_health_payload(members, unreadable, data, universe=None):
    """Assemble the ``health_board`` artifact section from classified members.

    ``members`` maps ticker -> ``core.pipeline.context.health_board.MemberHealth`` and
    ``unreadable`` is a list of ``{ticker, reason}`` (short_history / not_available
    / error). Emits ONE dict per member — the closed-set ``state``, the small
    scale-invariant sort fields, the box geometry (``R``/``S``/``base_len``, all
    ``None``/``0`` when there is no box so the reused card draws bare candles), and
    the daily candles/volumes — carrying NO score / tier / trigger / setup field
    (the "no buy language" contract, enforced at the emit site).

    A member whose candle extraction fails degrades into ``unreadable`` rather than
    tearing the section. The returned dict is added to the SAME per-universe
    artifact and rides the single atomic write in ``generate_dashboard`` (it is not
    written here); every value passes through that write's ``_json_safe`` chokepoint.
    """
    is_multi = getattr(data.columns, "nlevels", 1) > 1
    degraded = list(unreadable)
    member_rows = []
    for ticker, health in members.items():
        try:
            # The fold's shared prep — a documented consumer must never
            # re-type it (a bare dropna here silently diverges the day the
            # prep gains a step).
            frame = clean_daily_frame(data[ticker] if is_multi else data)
            candles, volumes, _ = daily_candles(frame)
        except Exception as exc:  # a member that can't render degrades honestly
            print(f"  Health chart error on {ticker}: {exc}")
            degraded.append({"ticker": ticker, "reason": "error"})
            continue
        etf = str(ticker).upper()
        member_rows.append({
            "ticker": etf,
            "name": SECTOR_ETF_NAMES.get(etf),  # friendly sector name when known, else None
            "state": health.state.value,        # exactly one closed-set state string
            "box_pos": health.box_pos,
            "breakout_extension": health.breakout_extension,
            "distance_to_high_pct": health.distance_to_high_pct,
            "R": health.R,
            "S": health.S,
            "base_len": int(health.base_len),
            "candles": candles,
            "volumes": volumes,
        })
    return {
        "members": member_rows,
        "unreadable": degraded,
        # Total members the board attempted this scan (classified + unreadable) so
        # the UI can say "29 members · 5 unavailable" without recomputing.
        "member_count": len(member_rows) + len(degraded),
    }


# ⚠️ LIVE — invoked on every scan by core/pipeline/screening/scan_job.py; writes the React
#    frontend's screener_data.json artifact. DO NOT delete as retired HTML residue.
def generate_dashboard(results_df, data=None, tickers=None, market_context=None,
                       universe=None, health_board=None, *, scan_date):
    """Extract chart data and export it as JSON for the React frontend.

    ``universe`` selects which artifact to write (``None`` = US-Stocks ->
    ``output/screener_data.json``, byte-identical to before); the path is resolved
    through the universe descriptor so the writer and the serving reader stay in
    lockstep on a single closed set of artifact names.

    ``scan_date`` is REQUIRED (council review 2026-08-05, finding 2): it is the
    SAME string ``archive_scan_results`` stamps (scan_job computes it once and
    threads it to both writers), so a verdict recorded against a payload row
    binds to the archive row's identity verbatim — (ticker, scan_date,
    universe_type) — never a client-derived date. An optional default here
    would let an ad-hoc caller publish a live-shaped payload with a null
    identity (EC-26's trap shape).
    """

    # Extract chart data if market data is provided. Skip on an empty result set:
    # an empty scan still writes a valid (empty) artifact so the universe reads as
    # "scanned, matched nothing" rather than "never scanned".
    chart_data = {}
    if data is not None and tickers is not None and not results_df.empty:
        chart_data = _extract_chart_data(data, results_df, tickers,
                                         resolve_universe(universe).universe_type)
        print(f"\nExtracted {len(chart_data)} interactive chart models for React dashboard...", flush=True)

    ordered_tickers = []
    for _, row in results_df.iterrows():
        if row['Ticker'] in chart_data:
            ordered_tickers.append(row['Ticker'])

    json_path = resolve_universe(universe).artifact_path()
    os.makedirs(os.path.dirname(json_path), exist_ok=True)

    # Provenance for the concordance loop: the archive identity key's scan-level
    # half plus the engine version that produced this read. Lazy import mirrors
    # the writer's own manifest_hash call site.
    from engine_alpha.freeze.manifest import manifest_hash
    payload_body = {
        "chart_data": chart_data,
        "ordered_tickers": ordered_tickers,
        "market_context": market_context or {},
        "scan_identity": {
            "scan_date": scan_date,
            "universe_type": resolve_universe(universe).universe_type,
            "engine_config_version": manifest_hash(),
        },
    }
    # The health-board section rides this SAME atomic write. Added ONLY when the
    # caller passed one (flag on, non-equities universe) — absent otherwise, so the
    # flag-off / us_equities artifact is byte-identical to before.
    if health_board is not None:
        payload_body["health_board"] = health_board
    payload = _json_safe(payload_body)
    tmp_path = json_path + ".tmp"
    try:
        with open(tmp_path, 'w', encoding='utf-8') as f:
            json.dump(payload, f, allow_nan=False)
        os.replace(tmp_path, json_path)
    except Exception:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except OSError:
            pass
        raise
    
    # flush=True so the webapp's scan stream receives these sentinels immediately
    # — the frontend reveals results on "UI update available" without waiting for
    # the slow archive step that runs after this.
    print(f"Data exported to: {json_path}", flush=True)
    print("UI update available on local webapp.", flush=True)
