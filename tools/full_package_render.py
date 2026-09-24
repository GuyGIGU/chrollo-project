"""Full-package structure render — the WHOLE read on one faithful chart.

The Phase-A AR overlay is illegible in isolation (``tools/ar_first_reaction_diff``)
because you cannot see which consolidation and root swing the engine actually
elected. This tool draws the COMPLETE structural read of a ticker on one chart,
on the faithful live 2y frame, so the operator can tune the automatic reaction
AND the root-swing / box election together:

  * the elected equilibrium box (Phase B) + inner consolidation,
  * the root swing (Phase A climax -> AR) the box was elected on,
  * the HH/HL vs LH/LL TREND MODEL that EXPLAINS that root swing — trend
    segments with their start / climax(terminal) / CHoCH(end) + the terminal
    impulse leg that is the AR's retrace basis (the not-live substrate),
  * the raw AR vs the first-reaction (trend-derived) AR — the flag being tuned,
  * the spring (Phase C), the LPS + trigger and Phase-D divider (Phase D),
  * the L2 event zones (spring/SOS/upthrust/test/LPS) as low-alpha context,
  * a text panel: the trend-segment table, the structure summary, the AR off/on
    tighten, and the one-line election trace.

FAITHFULNESS (non-negotiable — see docs/strategy_alpha.md + the sibling tools): it
reuses ``operator_marks_diff._prep_live`` (baseline filter -> trim to
DAILY_STRUCTURE_PERIOD (2y) -> ATR_10/50 -> atr = ATR_10.iloc[-6]) and
``read_structure`` on that SAME frame — NEVER the untrimmed 5y frame that
``structure_case_audit._prep`` uses (that resolves an
OLDER root / different box than live). Every ``*_bar`` from Structure + the trend
model is df-positional; L2 event zones are box-relative (translated by
``+ box.start_bar``). It draws the ELECTED ``read_structure`` output (box / root /
AR / spring / LPS) — the struct the pipeline archives — but does NOT re-apply the
post-read live vetoes (crash / extension / base_len, LPS distance-to-trigger,
descent-tail), so a rendered name may be one the screener later drops: the frame
and the elected geometry are faithful, the firing decision is not re-run.
Read-only: reads the parquet cache, restores the AR flag after every capture,
writes PNGs to tools/fidelity/full_package/. Nothing live imports it -> shadow
stays byte-identical.

    python -m tools.full_package_render AGCO TFX PH        # render these tickers
    python -m tools.full_package_render AGCO --window 0    # show the whole 2y frame
    python -m tools.full_package_render PH --no-events     # drop the L2 zone context
    python -m tools.full_package_render TOL --cache "C:/.../market_data_cache_5y.parquet"
"""
from __future__ import annotations

import argparse
import os
import sys

_THIS = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.normpath(os.path.join(_THIS, ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import pandas as pd

from config import settings
from tools._bootstrap import refuse_sealed_output
from engine_alpha.structure.events.market_structure import (
    elected_trend_leg_base,
    read_market_structure,
    segment_trends,
)
from engine_alpha.structure.metrics.base import read_box_events
from engine_alpha.structure.narrative.reader import read_structure
# Reuse the ONE faithful frame + AR-capture path (single source of truth).
from tools.operator_marks_diff import _prep_live

_OUT_DIR = os.path.join(_THIS, "fidelity", "full_package")

# L2 event-zone colors — the one L2 legend (inherited from the retired l2_staircase_render).
_ZONE_STYLE = {
    "SOS": "#1f9d8b", "markup": "#e0a030", "upthrust": "#e04848",
    "spring": "#8b5cf6", "test": "#5b8aff", "lps": "#0ea5a5",
    "in_progress": "#9aa0aa", "failed": "#c98a8a",
}
_ZONE_SKIP = {"rejection", "range"}

# Trend-model direction colors (HH/HL = up, LH/LL = down).
# Blind fallback bound for the full-leg base when no confirmed trend segment tops
# at the climax. Was settings.AR_UP_LEG_LOOKBACK until 2026-09-08, when the AR
# flag it belonged to was ruled DELETED; the value is unchanged and it is a
# RENDER constant now — nothing the engine reads consults it.
_LEG_BASE_LOOKBACK = 40

def _overlay(df, atr):
    """The (climax_bar, ar_bar, box_start_bar) the pipeline would archive for
    ``df`` right now, or None when no structure fires. Inlined here 2026-09-08
    from the deleted ``tools/ar_first_reaction_diff.py``; the off/on pair it used
    to sit beside went with ``AR_FIRST_REACTION_ENABLED``."""
    s = read_structure(df, atr)
    if s is None:
        return None
    return int(s.climax_bar), int(s.ar_bar), int(s.box.start_bar)


_UP = "#16a34a"
_DOWN = "#dc2626"
_RANGE = "#9aa0aa"
_ROOT_COLOR = "#1f2937"      # the elected root swing — the boldest line on the chart
_AR_OFF = "#8b5cf6"          # the automatic reaction the engine reads


def _draw_bars(ax, o, h, low, c):
    """OHLC bars, up teal / down red (matches the sibling tools)."""
    n = len(c)
    tick = 0.34
    lw = 1.0 if n > 90 else 1.3
    for i in range(n):
        up = c[i] >= o[i]
        col = "#1f9d8b" if up else "#e04848"
        ax.plot([i, i], [low[i], h[i]], color=col, lw=lw, alpha=0.55, zorder=2)
        ax.plot([i - tick, i], [o[i], o[i]], color=col, lw=lw, alpha=0.55, zorder=2)
        ax.plot([i, i + tick], [c[i], c[i]], color=col, lw=lw, alpha=0.55, zorder=2)


def _winning_rec(trace):
    """The elected root record (the completed story read_structure returned)."""
    if not trace:
        return None
    if trace[-1].get("outcome") == "complete":
        return trace[-1]
    return next((r for r in reversed(trace) if r.get("outcome") == "complete"), None)


def _cascade_summary(rec):
    """One-line summary of the box election: elected note + reject tally."""
    if not rec:
        return "no elected root"
    casc = rec.get("box_cascade") or []
    elected = next((c for c in casc if str(c.get("verdict", "")).startswith("elected")), None)
    rejects = {}
    for c in casc:
        v = str(c.get("verdict", ""))
        if v and not v.startswith("elected"):
            stage = v.split(":")[0].split()[0] if v else "?"
            rejects[stage] = rejects.get(stage, 0) + 1
    rej = " ".join(f"{k}:{v}" for k, v in sorted(rejects.items())) or "none"
    note = (elected.get("verdict") if elected else "elected")
    return f"{note}; rejected {sum(rejects.values())} ({rej})"


def _draw_trend_model(ax, df, base_off, n_win, climax_bar, climax_price,
                      direction, atr):
    """Draw the HH/HL/LH/LL skeleton + trend segments + the LIVE impulse leg.

    ``direction``/``climax_price`` describe the root swing (+1 buying climax at a
    high, -1 selling climax at a low). Returns ``(segs, elected)``.

    Faithfulness (2026-07-05, retargeted): the bold FULL LEG is the SAME leg the
    live AR now measures against — ``_full_leg_base(climax, direction)`` from
    ``first_reaction_after`` = the elected trend segment's start
    (``elected_trend_leg_base``), window-extreme fallback — NOT the terminal
    impulse sub-leg. The elected segment is matched by DIRECTION + terminal price
    ≈ the climax price (never merely a nearby bar, so a down-seg ending at the AR
    can't masquerade as the trend); it is ``None`` when the fine skeleton has no
    pivot at the macro-derived climax (~half of fires) — the segments are then
    honest CONTEXT, and the full-leg fallback still anchors the AR-retrace basis.
    """
    highs = df["High"].values.astype(float)
    lows = df["Low"].values.astype(float)
    ms = read_market_structure(df)
    points = ms.get("points", [])
    segs = segment_trends(points)

    def _x(bar):
        return bar - base_off

    # Faint HH/HL/LH/LL labels on every visible pivot.
    for p in points:
        x = _x(p["bar"])
        if not (0 <= x < n_win):
            continue
        lab = p.get("label")
        if lab not in ("HH", "HL", "LH", "LL"):
            continue
        up = p["kind"] == "peak"
        col = _UP if lab in ("HH", "HL") else _DOWN
        ax.annotate(lab, (x, p["price"]), textcoords="offset points",
                    xytext=(0, 7 if up else -7), ha="center", fontsize=6,
                    color=col, alpha=0.55, va="bottom" if up else "top", zorder=3)

    # The ELECTED segment: same direction as the root AND its terminal is the
    # climax (bar near + price within tolerance), so a down-seg topping at the AR
    # bar can never win. None => no fine-skeleton pivot at the macro climax.
    tol = max(2.0 * float(atr), 0.01 * abs(float(climax_price)))
    elected = next(
        (sg for sg in segs
         if sg["direction"] == direction
         and abs(int(sg["terminal_bar"]) - int(climax_bar)) <= 8
         and abs(float(sg["terminal_price"]) - float(climax_price)) <= tol),
        None)

    for seg in segs:
        is_el = seg is elected
        col = _UP if seg["direction"] > 0 else _DOWN
        lw = 2.2 if is_el else 1.0
        alpha = 0.9 if is_el else 0.30
        sx, tx = _x(seg["start_bar"]), _x(seg["terminal_bar"])
        ax.plot([sx, tx], [seg["start_price"], seg["terminal_price"]],
                color=col, lw=lw, alpha=alpha, ls="-", zorder=4)
        if 0 <= tx < n_win:
            ax.scatter([tx], [seg["terminal_price"]],
                       marker="^" if seg["direction"] > 0 else "v",
                       s=120 if is_el else 45, color=col, alpha=alpha,
                       edgecolor="white", linewidth=0.5, zorder=6)
        # Mechanical trend break (end) — NOT the Wyckoff CHoCH regime read.
        if is_el and seg["end_bar"] is not None:
            ex = _x(seg["end_bar"])
            if 0 <= ex < n_win:
                ax.axvline(ex, color=col, ls=":", lw=1.0, alpha=0.4, zorder=2)
                ax.annotate("trend break", (ex, seg["end_price"]),
                            textcoords="offset points", xytext=(2, 0),
                            fontsize=6.5, color=col, va="center", alpha=0.8)

    # The FULL trend leg — the whole advance the climax
    # ended, from the elected trend segment's start; the same basis
    # first_reaction_after measures against. Window-extreme fallback (with its bar)
    # when no fine-skeleton segment tops at the macro climax.
    col = _UP if direction > 0 else _DOWN
    base = elected_trend_leg_base(df, int(climax_bar), direction)
    if base is not None:
        bbar, bprice = int(base[0]), float(base[1])
    else:
        lo = max(0, int(climax_bar) - _LEG_BASE_LOOKBACK)
        rng = range(lo, int(climax_bar) + 1)
        bbar = (min(rng, key=lambda i: lows[i]) if direction > 0
                else max(rng, key=lambda i: highs[i]))
        bprice = float(lows[bbar] if direction > 0 else highs[bbar])
    bx, cxx = _x(bbar), _x(int(climax_bar))
    ax.plot([bx, cxx], [bprice, float(climax_price)], color=col,
            lw=3.2, alpha=0.5, zorder=3)
    if 0 <= bx < n_win:
        ax.scatter([bx], [bprice], marker="|", s=130, color=col, zorder=5)
        ax.annotate("full-leg base", (bx, bprice), textcoords="offset points",
                    xytext=(0, -11 if direction > 0 else 11), ha="center",
                    fontsize=6.5, color=col,
                    va="top" if direction > 0 else "bottom", alpha=0.85)
    return segs, elected


def _panel_text(ticker, s, ovs, segs, elected, rec):
    """Build the right-margin monospace text panel. ``elected`` is the trend
    segment whose terminal IS the root climax (direction + price matched), or
    None when the fine skeleton has no pivot there."""
    L = []
    L.append(f"{ticker}")
    L.append("=" * 30)
    L.append("TREND SEGMENTS (HH/HL, df-bar)")
    L.append("dir  start conf term  end   climax")
    # Keep the ELECTED segment (topping at the climax) in view when it exists; it
    # is what explains the root swing. Show it + the most recent context rows.
    show = list(segs[-9:])
    if elected is not None and elected not in show:
        show = [elected] + show
    for seg in show:
        d = "UP " if seg["direction"] > 0 else "DN "
        mark = ">" if seg is elected else " "
        end = seg["end_bar"] if seg["end_bar"] is not None else "run"
        L.append(f"{mark}{d} {seg['start_bar']:>4} {seg['confirm_bar']:>4} "
                 f"{seg['terminal_bar']:>4} {str(end):>4}  {seg['terminal_price']:.2f}")
    if elected is None:
        L.append("  (no fine-skel seg tops at climax;")
        L.append("   segs are context, impulse leg")
        L.append("   is the live AR basis)")
    L.append("")
    L.append("STRUCTURE (read_structure elect,")
    L.append("  pre crash/ext/descent-tail veto)")
    L.append(f"S={s.S:.2f}  R={s.R:.2f}  w={s.R - s.S:.2f}")
    L.append(f"base_len={s.box.base_len}  {s.box.r_touches}R/{s.box.s_touches}S")
    L.append(f"trav_dens={s.box.traversal_density:.2f}")
    L.append(f"box_start_bar={s.box.start_bar}")
    L.append(f"inner={'yes' if s.inner is not None else 'no'}  "
             f"spring={'yes' if s.spring is not None else 'no'}")
    L.append(f"terminator={s.terminator}")
    L.append(f"phase_d_start={s.phase_d_start_bar} ({s.phase_d_source})")
    if s.spring is not None:
        L.append(f"spring undercut={s.spring.undercut_atr:.2f}atr")
    L.append(f"lps_low_bar={s.lps.low_bar}  trig={s.lps.trigger:.2f}")
    L.append(f"lps_in_inner={s.lps_in_inner}")
    L.append("")
    L.append("AUTOMATIC REACTION")
    if ovs:
        L.append(f"cx {ovs[0]} -> AR {ovs[1]}  span {ovs[1] - ovs[0]}")
    L.append("")
    L.append("ELECTION TRACE")
    for chunk in _wrap(_cascade_summary(rec), 30):
        L.append(chunk)
    return "\n".join(L)


def _wrap(text, width):
    words = text.split()
    lines, cur = [], ""
    for w in words:
        if len(cur) + len(w) + 1 > width:
            lines.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    if cur:
        lines.append(cur)
    return lines


def _render_one(fig, ax, tax, ticker, df, atr, *, window, show_events, show_macro):
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch, Rectangle

    trace = []
    s = read_structure(df, atr, trace=trace)
    n_all = len(df)
    highs = df["High"].values.astype(float)
    lows = df["Low"].values.astype(float)

    if s is None:
        ax.text(0.5, 0.5, f"{ticker}: no structure fires on the live 2y frame",
                ha="center", va="center", transform=ax.transAxes, fontsize=12)
        # Still show the bars for context.
        win = window if (window and 0 < window < n_all) else n_all
        base_off = n_all - win
        sl = df.iloc[base_off:]
        _draw_bars(ax, sl.get("Open", sl["Close"]).values.astype(float),
                   sl["High"].values.astype(float), sl["Low"].values.astype(float),
                   sl["Close"].values.astype(float))
        tax.axis("off")
        return None

    cx = int(s.climax_bar)
    ar0 = int(s.ar_bar)
    # Orientation (MF-1): a buying climax tops at a HIGH into a lower AR; a selling
    # climax troughs at a LOW into a higher AR. Paint every root-swing marker on
    # the correct side of the candle — same test first_reaction_after uses.
    bc = float(highs[cx]) >= float(highs[ar0])
    direction = 1 if bc else -1
    climax_price = float(highs[cx]) if bc else float(lows[cx])
    ar_price = float(lows[ar0]) if bc else float(highs[ar0])
    # Window: default keeps the elected climax visible with lead-in; 0 = whole frame.
    if window == 0:
        win = n_all
    else:
        need = n_all - cx + 45
        win = min(n_all, max(window, need))
    base_off = n_all - win
    last_x = win - 1

    def _x(bar):
        return bar - base_off

    sl = df.iloc[base_off:]
    o = sl.get("Open", sl["Close"]).values.astype(float)
    _draw_bars(ax, o, sl["High"].values.astype(float),
               sl["Low"].values.astype(float), sl["Close"].values.astype(float))

    # --- P1: elected equilibrium box + inner ---------------------------------
    bx = _x(int(s.box.start_bar))
    ax.add_patch(Rectangle((bx - 0.4, s.S), (last_x - bx + 0.8), max(s.R - s.S, 1e-9),
                           facecolor="#8b5cf6", alpha=0.07, edgecolor="#8b5cf6",
                           lw=1.0, zorder=1))
    ax.hlines([s.R, s.S], bx, last_x, colors="#5b8aff", ls="--", lw=1.1, alpha=0.9, zorder=3)
    ax.text(last_x, s.R, " R", color="#5b8aff", va="center", fontsize=8, fontweight="bold")
    ax.text(last_x, s.S, " S", color="#5b8aff", va="center", fontsize=8, fontweight="bold")
    for abar, lvl in ((s.box.r_anchor_bar, s.R), (s.box.s_anchor_bar, s.S)):
        axx = _x(int(abar))
        if 0 <= axx < win:
            ax.scatter([axx], [lvl], marker="o", s=28, facecolor="none",
                       edgecolor="#8aa0c8", zorder=4)
    if s.inner is not None:
        ix = _x(int(s.inner.start_bar))
        ax.add_patch(Rectangle((ix - 0.4, s.inner.S), (last_x - ix + 0.8),
                               max(s.inner.R - s.inner.S, 1e-9), facecolor="#0ea5a5",
                               alpha=0.06, edgecolor="#0ea5a5", lw=0.9, ls="--", zorder=1))

    # --- P3: trend model (drawn under the root swing) ------------------------
    segs, elected = _draw_trend_model(ax, df, base_off, win, cx, climax_price,
                                      direction, atr)

    # --- P2: the elected root swing (climax -> AR), the boldest line ---------
    cxx, arx = _x(cx), _x(ar0)
    if 0 <= cxx < win:
        ax.axvline(cxx, color=_ROOT_COLOR, ls="--", lw=0.9, alpha=0.4, zorder=3)
    seg_x, seg_y = [], []
    if 0 <= cxx < win:
        ax.scatter([cxx], [climax_price], marker="*", s=260, color=_ROOT_COLOR,
                   edgecolor="white", linewidth=0.8, zorder=7)
        seg_x.append(cxx); seg_y.append(climax_price)
    if 0 <= arx < win:
        seg_x.append(arx); seg_y.append(ar_price)
    if len(seg_x) == 2:
        ax.plot(seg_x, seg_y, color=_ROOT_COLOR, lw=2.4, alpha=0.95, zorder=6)

    # --- P4: the automatic reaction the engine actually reads -----------------
    # Was a raw-vs-first-reaction PAIR until 2026-09-08, when the operator ruled
    # AR_FIRST_REACTION_ENABLED deleted; there is one AR now, so one dot.
    ovs = _overlay(df, atr)
    if ovs is not None:
        arb = int(ovs[1])
        axx = _x(arb)
        if 0 <= axx < win:
            ax.scatter([axx], [lows[arb] if bc else highs[arb]], marker="o", s=95,
                       facecolor="none", edgecolor=_AR_OFF,
                       linewidth=1.6, zorder=8)

    # --- P5: spring (Phase C) -------------------------------------------------
    if s.spring is not None:
        tb = int(s.spring.tip_bar)
        tbx = _x(tb)
        if 0 <= tbx < win:
            ax.scatter([tbx], [lows[tb]], marker="v", s=90, color="#8b5cf6",
                       edgecolor="white", linewidth=0.6, zorder=7)
            rb = _x(int(s.spring.recovery_bar))
            if 0 <= rb < win:
                ax.plot([tbx, rb], [lows[tb], s.S], color="#8b5cf6", lw=1.4,
                        alpha=0.7, zorder=5)
            ax.annotate(f"spring {s.spring.undercut_atr:.1f}atr", (tbx, lows[tb]),
                        textcoords="offset points", xytext=(0, -10), ha="center",
                        fontsize=7, color="#8b5cf6", va="top", fontweight="bold")

    # --- P6: LPS (Phase D) + trigger -----------------------------------------
    lb = _x(int(s.lps.start_bar))
    le = _x(int(s.lps.end_bar))
    ax.add_patch(Rectangle((lb - 0.4, s.lps.low), (le - lb + 0.8),
                           max(s.lps.high - s.lps.low, 1e-9), facecolor="#0ea5a5",
                           alpha=0.12, edgecolor="none", zorder=1))
    lowx = _x(int(s.lps.low_bar))
    if 0 <= lowx < win:
        ax.scatter([lowx], [s.lps.low], marker="D", s=45, color="#0ea5a5",
                   edgecolor="white", linewidth=0.5, zorder=7)
    ax.hlines([s.lps.trigger], lb, last_x, colors="#0ea5a5", ls=":", lw=1.1,
              alpha=0.85, zorder=3)

    # --- P7: Phase-D divider --------------------------------------------------
    pdx = _x(int(s.phase_d_start_bar))
    if 0 <= pdx < win:
        ax.axvline(pdx, color="#0ea5a5", ls="-.", lw=1.0, alpha=0.5, zorder=2)
        ax.annotate(f"Phase D ({s.phase_d_source})", (pdx, s.R),
                    textcoords="offset points", xytext=(2, -12), fontsize=6.5,
                    color="#0ea5a5", va="top")

    # --- P8: L2 event zones (context) ----------------------------------------
    if show_events:
        for e in read_box_events(df, s.box, atr):
            t = e["type"]
            if t in _ZONE_SKIP:
                continue
            col = _ZONE_STYLE.get(t, _RANGE)
            zs = _x(int(s.box.start_bar) + int(e["zone_start"]))
            ze = _x(int(s.box.start_bar) + int(e["zone_end"]))
            ax.axvspan(zs - 0.4, ze + 0.4, color=col, alpha=0.08, zorder=0)

    # --- P9: macro bridge (optional) -----------------------------------------
    if show_macro:
        from engine_alpha.structure.phases.phase_a import macro_bridge_zigzag
        zz = macro_bridge_zigzag(df["High"].values.astype(float),
                                 df["Low"].values.astype(float))
        if len(zz) >= 2:
            xs = [_x(int(b)) for (b, _k, _p) in zz]
            ys = [float(p) for (_b, _k, p) in zz]
            ax.plot(xs, ys, color="#b45309", lw=1.0, ls=":", alpha=0.6, zorder=4)

    # --- axes / ticks ---------------------------------------------------------
    ax.set_xlim(-1, win)
    ax.margins(y=0.08)
    ax.grid(True, alpha=0.12)
    step = max(1, win // 9)
    ticks = list(range(0, win, step))
    ax.set_xticks(ticks)
    ax.set_xticklabels([str(df.index[base_off + t])[:10] for t in ticks],
                       rotation=35, ha="right", fontsize=7)
    live = "ON" if settings.AR_FIRST_REACTION_ENABLED else "OFF"
    ax.set_title(f"{ticker}   root swing cx{cx}->AR{int(s.ar_bar)}   "
                 f"S={s.S:.2f} R={s.R:.2f}   base_len={s.box.base_len}   "
                 f"AR flag live: {live}", fontsize=11, fontweight="bold", loc="left")

    # --- legend + text panel --------------------------------------------------
    handles = [
        Line2D([0], [0], color=_ROOT_COLOR, lw=2.4, marker="*", markersize=11,
               label="root swing (elected Phase A)"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor="none",
               markeredgecolor=_AR_OFF, markersize=9, label="automatic reaction"),
        Line2D([0], [0], color=_UP, lw=2, label="up trend seg / HH·HL"),
        Line2D([0], [0], color=_DOWN, lw=2, label="down trend seg / LH·LL"),
        Patch(facecolor="#8b5cf6", alpha=0.2, label="equilibrium box"),
        Patch(facecolor="#0ea5a5", alpha=0.2, label="inner / LPS"),
    ]
    ax.legend(handles=handles, loc="upper left", fontsize=7.5, framealpha=0.9, ncol=2)

    tax.axis("off")
    tax.text(0.0, 1.0, _panel_text(ticker, s, ovs, segs, elected, _winning_rec(trace)),
             family="monospace", fontsize=7.2, va="top", ha="left",
             transform=tax.transAxes)
    return s


def render(tickers, *, window, out_dir, show_events, show_macro, cache):
    refuse_sealed_output(out_dir)   # pre-flight: fail before the cache load (EC-14)
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    if cache:
        settings.CACHE_FILENAME = cache
    d = pd.read_parquet(settings.CACHE_FILENAME, engine=settings.PARQUET_ENGINE)
    level0 = set(d.columns.get_level_values(0))
    os.makedirs(out_dir, exist_ok=True)

    written = []
    for t in tickers:
        t = t.upper()
        if t not in level0:
            print(f"  [skip {t}] not in cache")
            continue
        df, atr = _prep_live(d[t].dropna())
        if df is None:
            print(f"  [skip {t}] {atr}")           # atr carries the reason string
            continue
        fig, (ax, tax) = plt.subplots(
            1, 2, figsize=(19, 8), gridspec_kw={"width_ratios": [4.3, 1]})
        try:
            _render_one(fig, ax, tax, t, df, atr, window=window,
                        show_events=show_events, show_macro=show_macro)
        except Exception as exc:                    # never let one ticker kill the batch
            print(f"  [error {t}] {type(exc).__name__}: {exc}")
            plt.close(fig)
            continue
        fig.suptitle(f"{t}  —  full structural package (faithful live 2y frame)",
                     fontsize=13, fontweight="bold")
        fig.tight_layout(rect=(0, 0, 1, 0.97))
        out = os.path.join(out_dir, f"{t}.png")
        fig.savefig(out, dpi=125)
        plt.close(fig)
        written.append(out)
        print(f"  rendered {t} -> {out}")
    return written


def main():
    ap = argparse.ArgumentParser(
        description="Render the complete structural read (box + root swing + trend "
                    "model + raw/first-reaction AR + spring/LPS/Phase-D + L2 events) "
                    "of a ticker on the faithful live 2y frame.")
    ap.add_argument("tickers", nargs="+", help="tickers to render")
    ap.add_argument("--window", type=int, default=280,
                    help="bars to show (default 280, widened to keep the climax "
                         "visible; 0 = whole 2y frame)")
    ap.add_argument("--out", default=_OUT_DIR, help="output dir for PNGs")
    ap.add_argument("--no-events", action="store_true",
                    help="drop the low-alpha L2 event-zone context layer")
    ap.add_argument("--macro", action="store_true",
                    help="overlay the macro-bridge zigzag (Phase-A provenance)")
    ap.add_argument("--cache", default=None,
                    help="path to the market_data_cache_5y.parquet (default: "
                         "settings.CACHE_FILENAME in cwd)")
    a = ap.parse_args()
    render([t.upper() for t in a.tickers], window=a.window, out_dir=a.out,
           show_events=not a.no_events, show_macro=a.macro, cache=a.cache)


if __name__ == "__main__":
    main()
