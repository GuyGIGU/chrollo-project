"""Higher-timeframe (HTF) structure context — the SAME engine, weekly/monthly bars.

The screener reads daily charts. But the highest-quality daily setup is the one
that is *itself* a re-accumulation (an energy-gathering pause) inside a
higher-timeframe uptrend. Per Guy: HTF is not a bespoke classifier — it is the
exact same Wyckoff Trend + Box (A->B->C->D) logic, run on weekly and monthly
bars. "It's all relative and derivative."

That holds in the code: the structure detectors split into RATIO thresholds
(scale-invariant — box width, boundary-respect %, ATR/box ratios, traversal
fractions, LPS profiles) and BAR-COUNT WINDOWS (daily-calibrated). To read HTF
structure we resample to weekly/monthly, temporarily rescale ONLY the bar-count
windows (``timeframe_windows``), and run the same calibrated bricks.

Note we do NOT call ``read_structure`` here: it *requires* a right-side LPS and
returns None mid-range, so it cannot report a HTF chart that is simply in
Phase B. We run a box-tolerant walk over the same bricks instead, so "what stage
are we in?" can answer B (ranging), C (spring), or D (right-side LPS).

This layer is MEASURE-ONLY: it annotates and archives context on firing setups;
it never gates a setup. Window presets in config.settings are FIRST-PASS — eyeball
and tune with tools/htf_audit.py.
"""
from __future__ import annotations

import contextlib
from typing import Optional

import numpy as np
import pandas as pd

from config import settings
from engine_alpha.structure.indicators import calculate_atr

_AGG = {"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"}
_RULE = {"weekly": "W-FRI", "monthly": "ME"}
_PREFIX = {"weekly": "htf_w_", "monthly": "htf_m_"}

# Every context dict carries this full key set (with the timeframe prefix) so the
# archive columns are present and consistent even when the read is skipped.
_FIELDS = {
    "stage2": False,
    "trend_state": "unknown",
    "in_consol": False,
    "phase": None,
    "box_r": None,
    "box_s": None,
    "box_width": None,
    "reaccum": False,
    "daily_nested": None,
}


def _empty(prefix: str) -> dict:
    return {prefix + k: v for k, v in _FIELDS.items()}


# ── Archive column metadata ─────────────────────────────────────────────────
# The writer, live/seed archive value mapping, and dashboard payload derive from
# this list. ORM/API/migration declarations stay explicit, with tests enforcing
# that they carry the same HTF field set.
HTF_BOOL_FIELDS = ("stage2", "in_consol", "reaccum", "daily_nested")
HTF_COLUMNS = [f"{p}{k}" for p in ("htf_w_", "htf_m_") for k in _FIELDS]
HTF_BOOL_COLUMNS = frozenset(
    f"{p}{k}" for p in ("htf_w_", "htf_m_") for k in HTF_BOOL_FIELDS)


def _htf_sql_type(col: str) -> str:
    base = col.split("_", 2)[-1]                 # 'htf_w_box_width' -> 'box_width'
    if base in HTF_BOOL_FIELDS:
        return "INTEGER"
    if base in ("trend_state", "phase"):
        return "TEXT"
    return "FLOAT"


HTF_COLUMN_SQL = {c: _htf_sql_type(c) for c in HTF_COLUMNS}


def htf_archive_values(get, *, prefixed: bool) -> dict:
    """Map a result row to the {column: value} archive dict. ``get`` is the row's
    ``.get``; the LIVE result carries ``_``-prefixed keys (``prefixed=True``), the
    SEED result does not. Booleans are coerced to 0/1 (nullable) for SQLite."""
    out = {}
    for col in HTF_COLUMNS:
        value = get(("_" + col) if prefixed else col)
        out[col] = (int(bool(value)) if value is not None else None) \
            if col in HTF_BOOL_COLUMNS else value
    return out


def resample_ohlc(df: pd.DataFrame, tf: str) -> Optional[pd.DataFrame]:
    """Resample a daily OHLCV frame to weekly (``W-FRI``) or monthly (``ME``).

    Keeps the latest (still-forming) period as the final bar — the structure
    detectors reserve it via ``STRUCTURE_EDGE_SKIP_BARS`` exactly as on daily.
    Returns None on an unusable frame.
    """
    rule = _RULE.get(tf)
    if rule is None:
        raise ValueError(f"unknown timeframe {tf!r}")
    if df is None or len(df) == 0:
        return None
    if not isinstance(df.index, pd.DatetimeIndex):
        # Only coerce a genuinely date-like (string/object) index. A numeric index
        # would be silently epoch-coerced into 1970 and collapse every bar — skip it.
        if df.index.dtype != object:
            return None
        try:
            df = df.set_index(pd.to_datetime(df.index))
        except (ValueError, TypeError):
            return None
    cols = {c: how for c, how in _AGG.items() if c in df.columns}
    if not {"High", "Low", "Close"} <= set(cols):
        return None
    try:
        out = df.resample(rule).agg(cols)
    except (ValueError, KeyError):
        # Older pandas: 'ME'/'W-FRI' alias fallback.
        out = df.resample("M" if tf == "monthly" else "W").agg(cols)
    out = out.dropna(subset=["High", "Low", "Close"])
    return out if len(out) else None


@contextlib.contextmanager
def window_override(preset: dict):
    """Temporarily set the given settings overrides (bar-count windows and
    the rescue lane's in-read form flag), restoring every value (even on
    exception) — the ONE scoped override mechanism inside the engine.
    ``timeframe_windows`` (HTF weekly/monthly) is its declared preset (the
    Power-Play species preset was deleted with its lane, build step 12); a
    differently-clocked read enters HERE, never through a forked
    collector or a hand-threaded parameter, and the evidence instruments'
    ``tools.replay.flag_capture`` delegates to this same core (EC-3). Safe
    because the detectors read ``settings.X`` lazily at call-time and each
    read is synchronous within a worker. AttributeError on a typo'd key ->
    fail fast."""
    saved: dict = {}
    try:
        for key, value in preset.items():
            saved[key] = getattr(settings, key)
            setattr(settings, key, value)
        yield
    finally:
        for key, value in saved.items():
            setattr(settings, key, value)


@contextlib.contextmanager
def timeframe_windows(tf: str):
    """The HTF window preset, through the one override mechanism. The
    scale-invariant ratio thresholds are deliberately untouched."""
    preset = (settings.HTF_WEEKLY_WINDOWS if tf == "weekly"
              else settings.HTF_MONTHLY_WINDOWS)
    with window_override(preset):
        yield


def htf_stage2(df: pd.DataFrame) -> dict:
    """The HTF form of the one Stage-2 question — its daily twin is
    ``indicators.trend_template`` (the full Minervini criteria set). Two labeled
    forms by design (P6); wire keys of both are frozen.

    Weinstein/Minervini Stage-2 trend filter on the HTF frame: price above a
    rising ``HTF_STAGE_MA``-period MA (weekly MA-30 ~ daily MA-150/200). Measured
    on the last COMPLETED bar (the live partial is skipped). Never raises."""
    ma_n = int(settings.HTF_STAGE_MA)
    slope_bars = int(settings.HTF_STAGE_MA_SLOPE_BARS)
    try:
        close = df["Close"].astype(float)
        if len(close) < ma_n + slope_bars + 2:
            return {"stage2": False, "trend_state": "unknown"}
        ma = close.rolling(ma_n).mean()
        price = float(close.iloc[-2])
        ma_now = float(ma.iloc[-2])
        ma_prev = float(ma.iloc[-2 - slope_bars])
        if not all(np.isfinite(v) for v in (price, ma_now, ma_prev)) or ma_now <= 0:
            return {"stage2": False, "trend_state": "unknown"}
        above = price > ma_now
        rising = ma_now > ma_prev
        falling = ma_now < ma_prev
        if above and rising:
            state = "up"
        elif (not above) and falling:
            state = "down"
        else:
            state = "neutral"
        return {"stage2": bool(above and rising), "trend_state": state}
    except (KeyError, TypeError, ValueError, IndexError):
        return {"stage2": False, "trend_state": "unknown"}


def _read_htf_structure(df: pd.DataFrame, atr: float, max_roots: int = 40) -> Optional[dict]:
    """Box-tolerant walk over the calibrated bricks: the oldest worked equilibrium,
    then its optional spring and optional right-side LPS. Phase = D if a right-side
    LPS exists, else C if a spring exists, else B (still ranging). Returns None when
    no worked box is found."""
    from engine_alpha.structure import bricks  # lazy: avoids any import-order coupling

    search_from = 0
    for _ in range(max_roots):
        root = bricks.find_root_swing(df, search_from, atr)
        if root is None:
            return None
        search_from = int(root.climax_bar) + 1
        box = bricks.validate_equilibrium(df, root, atr)
        if box is None:
            continue
        # A crashing detector must ABSTAIN, not paint: both callers wrap this
        # walk in an honest catch-all (empty field set / None = "not measured").
        # Swallowing here instead would fabricate a phase read ("no spring" ->
        # B/D) out of a failure — the FLXS bug class (doctrine audit 2026-07-19).
        spring = bricks.find_spring(df, box, atr)
        lps = bricks.find_lps(df, box, atr)
        phase = "D" if lps is not None else ("C" if spring is not None else "B")
        return {"box": box, "spring": spring, "lps": lps, "phase": phase, "root": root}
    return None


def _prep_htf_frame(daily_df: pd.DataFrame, tf: str):
    """Resample + enrich (ATR_10 / Vol_50 / Spread) + right-edge ATR sample —
    the shared preamble of ``read_htf_context`` and ``chart_box``. Returns
    ``(htf_df, atr, atr_ok)``: ``htf_df`` is None when the resample refuses
    (too short); ``atr_ok`` is False when the sampled ATR refuses. Callers own
    their bail values — ``read_htf_context`` still writes its Stage-2 fields
    BEFORE honoring the ATR refusal. The structure walk stays with the callers
    (the ``_read_htf_structure`` monkeypatch seam)."""
    htf_df = resample_ohlc(daily_df, tf)
    if htf_df is None or len(htf_df) < 8:
        return None, 0.0, False
    htf_df = htf_df.copy()
    htf_df["ATR_10"] = calculate_atr(htf_df, 10)
    if "Volume" in htf_df.columns:
        htf_df["Vol_50"] = htf_df["Volume"].rolling(50, min_periods=1).mean()
    else:
        htf_df["Volume"] = 0.0
        htf_df["Vol_50"] = 0.0
    htf_df["Spread"] = htf_df["High"] - htf_df["Low"]
    # -2 unconditionally: the len<8 refusal above guarantees a completed bar
    # exists behind the forming right-edge bar (the right-edge reserve law).
    atr = float(htf_df["ATR_10"].iloc[-2])
    if not np.isfinite(atr) or atr <= 0:
        return htf_df, atr, False
    return htf_df, atr, True


def read_htf_context(daily_df: pd.DataFrame, tf: str,
                     daily_box: Optional[tuple] = None) -> dict:
    """The HTF context for one ticker at one timeframe, as a flat prefixed dict
    (``htf_w_*`` / ``htf_m_*``). Resamples the daily frame, runs the Stage-2 trend
    read + the box-tolerant structure walk under the timeframe window override, and
    derives the archived/charted fields. ``daily_box`` is the firing daily
    ``(R, S)`` used for the nesting test. Never raises — returns the empty field set
    on any problem (this layer must never break a scan)."""
    prefix = _PREFIX.get(tf)
    if prefix is None:
        raise ValueError(f"unknown timeframe {tf!r}")
    out = _empty(prefix)
    if not getattr(settings, "HTF_CONTEXT_ENABLED", True):
        return out
    try:
        htf_df, atr, atr_ok = _prep_htf_frame(daily_df, tf)
        if htf_df is None:
            return out

        stage = htf_stage2(htf_df)
        out[prefix + "stage2"] = stage["stage2"]
        out[prefix + "trend_state"] = stage["trend_state"]

        if not atr_ok:
            return out

        with timeframe_windows(tf):
            s = _read_htf_structure(htf_df, atr)

        if s is not None:
            box = s["box"]
            out[prefix + "in_consol"] = True
            out[prefix + "phase"] = s["phase"]
            out[prefix + "box_r"] = round(float(box.R), 4)
            out[prefix + "box_s"] = round(float(box.S), 4)
            out[prefix + "box_width"] = round(float(box.box_width), 4)
            out[prefix + "reaccum"] = bool(stage["stage2"])  # Stage-2 uptrend AND in_consol
            if daily_box is not None:
                d_r, d_s = float(daily_box[0]), float(daily_box[1])
                out[prefix + "daily_nested"] = bool(box.S <= d_s and d_r <= box.R)
        return out
    except Exception:
        return out


def chart_box(daily_df: pd.DataFrame, tf: str) -> Optional[dict]:
    """The worked HTF box for CHARTING: ``r``, ``s``, the box's START DATE, and
    phase. The start date lets the frontend anchor the rails to the bars the box is
    born from — exactly like the daily chart's bounded R/S lines, not a full-width
    rail. Reuses the same resample + window-override + box-tolerant walk as
    ``read_htf_context``. Returns None when there is no worked box. Never raises
    (charting must not break a scan)."""
    try:
        work, atr, atr_ok = _prep_htf_frame(daily_df, tf)
        if work is None or not atr_ok:
            return None
        with timeframe_windows(tf):
            s = _read_htf_structure(work, atr)
        if s is None:
            return None
        box = s["box"]
        lps = s.get("lps")
        idx = work.index
        n = len(idx)

        def _date(bar) -> str:
            return str(idx[max(0, min(int(bar), n - 1))])[:10]

        # Geometry as DATES so the chart can colour candles exactly like the daily
        # chart: the base-limb swing (the bars that set the rails) grey, and the
        # right-side LPS span gold. ``start_date`` anchors the R/S rails.
        return {
            "r": round(float(box.R), 4),
            "s": round(float(box.S), 4),
            "start_date": _date(box.start_bar),
            "phase": s["phase"],
            # start_bar in the min: the shared-rail back-extension can open the
            # box before the anchor pair; the grey limb must still mark its left
            # edge (mirrors the daily-chart sites in chartGeometry/overlay).
            "limb_start_date": _date(min(int(box.r_anchor_bar), int(box.s_anchor_bar),
                                         int(box.start_bar))),
            "limb_end_date": _date(max(int(box.r_anchor_bar), int(box.s_anchor_bar))),
            "lps_start_date": _date(lps.start_bar) if lps is not None else None,
            "lps_end_date": _date(lps.end_bar) if lps is not None else None,
        }
    except Exception:
        return None
