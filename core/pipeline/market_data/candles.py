"""The shared OHLCV→wire candle builders — the EC-3 fold.

Every surface that serializes chart candles imports THESE builders: the scan
writer (output/dashboard._extract_chart_data), the health board
(output/dashboard.build_health_payload), and the watchlist candle endpoint.
One implementation is the parity guarantee: same field names, date strings,
two-decimal prices, whole-number volumes, caps, and resample ordering from
every producer, so the same ticker can never draw differently depending on
which path served it.

Settings are read at call time, never cached at module level (AP-3 — the
established pattern for core modules the backend also imports).
"""
from __future__ import annotations

from config import settings
from engine_alpha.structure.context.htf import resample_ohlc


def clean_daily_frame(df):
    """THE pre-builder frame prep both wire paths share.

    A per-ticker slice of the multi-ticker cache panel legitimately carries
    all-NaN rows for sessions the ticker did not trade — those go. The drop
    keys on the PRICE columns only: a session with valid OHLC but a damaged
    or absent Volume is a real traded bar (the engine's own resampler keeps
    it via its High/Low/Close subset), so it stays, with Volume coerced to 0
    for display. An any-NaN drop deleted such sessions whole — silently
    moving last_bar_date and every forming verdict back a day (council
    review 2026-08-17, finding 9). Identical prep on the scan path and the
    endpoint path is part of the parity surface: the same builder fed a
    differently-prepped frame still diverges.
    """
    price_cols = [c for c in ("Open", "High", "Low", "Close") if c in df.columns]
    frame = df.dropna(subset=price_cols) if price_cols else df.dropna()
    if "Volume" in frame.columns and frame["Volume"].isna().any():
        frame = frame.copy()
        frame["Volume"] = frame["Volume"].fillna(0)
    return frame


def _wire_arrays(frame):
    """An OHLCV frame → (candles, volumes) wire dicts — THE one assembly.

    Both builders (daily and resampled) call this, so the field names, the
    date-string extraction, the rounding, and the volume color rule exist
    exactly once. Dates come from the frame's own index — never positional
    row numbers (a renamed/unnamed datetime index must not degrade to
    RangeIndex garbage; council review 2026-08-17, finding 10). Prices are
    widened to float64 BEFORE rounding so a float32 cache value rounds to a
    clean two-decimal wire value, not 17 digits of float32 noise; float32
    volume granularity at index-ETF scale is the cache dtype's inherent cost
    and is not correctable here.
    """
    dates = [str(idx)[:10] for idx in frame.index]
    opens = frame['Open'].astype('float64').round(2).values
    highs = frame['High'].astype('float64').round(2).values
    lows = frame['Low'].astype('float64').round(2).values
    closes = frame['Close'].astype('float64').round(2).values
    vols = frame['Volume'].round(0).values
    candles = [
        {'time': d, 'open': float(o), 'high': float(h), 'low': float(l), 'close': float(c)}
        for d, o, h, l, c in zip(dates, opens, highs, lows, closes)
    ]
    volumes = [
        {'time': d, 'value': float(v),
         'color': 'rgba(38,166,154,0.5)' if c >= o else 'rgba(239,83,80,0.5)'}
        for d, o, c, v in zip(dates, opens, closes, vols)
    ]
    return candles, volumes


def tf_candles(df, tf, cap):
    """Resample the daily frame to weekly/monthly and return (candles, volumes)
    for the higher-timeframe charts, capped to the last ``cap`` bars.

    Resamples from the FULL daily history handed in and tail-caps AFTER —
    capping the daily frame first would silently rebuild the leftmost
    weekly/monthly buckets from partial data."""
    resampled = resample_ohlc(df, tf)
    if resampled is None or resampled.empty:
        return [], []
    return _wire_arrays(resampled.tail(cap))


def daily_candles(df):
    """Daily (candles, volumes, show_days) for a ticker frame, capped to the
    last DASHBOARD_CHART_DAYS bars — the shared OHLCV→wire-dict extraction.
    It folds only the PURE candle shape (which every consumer genuinely
    shares), NOT the scan writer's firing-only results_df fields, so the
    diverging payloads stay decoupled. ``show_days`` is returned because the
    scan writer needs it for window-bar math."""
    show_days = min(settings.DASHBOARD_CHART_DAYS, len(df))
    candles, volumes = _wire_arrays(df.tail(show_days))
    return candles, volumes, show_days


def chart_candles(df):
    """The one entry point: a prepped daily frame → the complete
    daily/weekly/monthly candle set under the settings caps.

    This is the whole parity surface in one call — prep excepted (see
    clean_daily_frame), a consumer that wants the standard chart payload has
    no numbers or ordering of its own to get wrong. The caps live only in
    config.settings (DASHBOARD_CHART_DAYS / _WEEKS / _MONTHS)."""
    candles, volumes, show_days = daily_candles(df)
    weekly_candles, weekly_volumes = tf_candles(
        df, "weekly", settings.DASHBOARD_CHART_WEEKS)
    monthly_candles, monthly_volumes = tf_candles(
        df, "monthly", settings.DASHBOARD_CHART_MONTHS)
    return {
        'candles': candles,
        'volumes': volumes,
        'show_days': show_days,
        'weekly_candles': weekly_candles,
        'weekly_volumes': weekly_volumes,
        'monthly_candles': monthly_candles,
        'monthly_volumes': monthly_volumes,
    }
