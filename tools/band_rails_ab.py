"""Band-rails A/B render — the flip instrument for ``BAND_RAILS_ENABLED``.

For every mark in ``docs/phase_c_marks_2026-07.json`` (the deep Phase-C
calibration set, deliberately OUTSIDE the sealed corpus) this draws ONE chart
on the faithful point-in-time frame at the drawn box's last day:

  * the OHLC bars, with the operator's DRAWN rails (gold) across his drawn
    span and his ruled Phase-C region (purple shading + tip marker),
  * the engine's flag-OFF read (blue) and flag-ON read (green) — rails, box
    start, LPS low — captured by toggling the flag around ``read_structure``
    and restoring it,
  * the engine's qualified deep events on the flag-ON pair (dotted purple
    span edges via ``qualify_pair_events`` — the same pure judgment the pool
    uses),
  * the DIVERGENCE EXHIBIT: closes inside the drawn span that sit BELOW the
    drawn S (red dots). On the frozen BODI frame the January action closes
    9.4-10.9 under the drawn 10.15 for stretches — the single Dec->Apr box
    does not exist as a clean chronological pair on this data, and that
    disagreement is the operator's to adjudicate, not a threshold's.

Faithfulness: corpus tickers render on the FROZEN marks-corpus fixture frames
(the same data every recorded finding used); non-corpus tickers (KLAC) fall
back to the live 5y parquet cache. Prep is the live twin's
``_prepare_eval_frame``. Read-only: restores the flag after every capture,
writes PNGs to tools/fidelity/band_rails_ab/, nothing live imports it.

    python -m tools.band_rails_ab                 # all calibration marks
    python -m tools.band_rails_ab BODI            # just one ticker
"""
from __future__ import annotations

try:
    from tools._bootstrap import configure_path
except ModuleNotFoundError:
    from _bootstrap import configure_path

configure_path()

import argparse
import json
import os

import pandas as pd

from core.structure.band_rails import qualify_pair_events
from tools.replay import load_sealed_fixture, resolve_frame, snapped_election

_THIS = os.path.dirname(os.path.abspath(__file__))
_MARKS = os.path.join(_THIS, "..", "docs", "phase_c_marks_2026-07.json")
_OUT_DIR = os.path.join(_THIS, "fidelity", "band_rails_ab")

_DRAWN = "#e0a030"     # operator ground truth — gold
_OFF = "#5b8aff"       # engine flag-OFF — the live read
_ON = "#16a34a"        # engine flag-ON — the band pool's read
_C_ZONE = "#8b5cf6"    # Phase C — same purple as every sibling tool


def _bar(df: pd.DataFrame, date_str: str) -> int:
    return min(int(df.index.searchsorted(pd.Timestamp(date_str))), len(df) - 1)


# The two rule variants this A/B compares, captured via the shared
# self-restoring toggle (tools.replay.flag_capture).
_VARIANTS = [{"BAND_RAILS_ENABLED": False}, {"BAND_RAILS_ENABLED": True}]


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


def _draw_engine(ax, s, label, color, base_off, last_x, atr):
    """One engine read: rails + box start + LPS low; returns the summary line."""
    if s is None:
        return f"{label}: NONE"
    bx = int(s.box.start_bar) - base_off
    ax.hlines([s.R, s.S], max(bx, 0), last_x, colors=color, ls="--", lw=1.3,
              alpha=0.9, zorder=4)
    if bx >= 0:
        ax.axvline(bx, color=color, ls=":", lw=0.9, alpha=0.5, zorder=2)
    lowx = int(s.lps.low_bar) - base_off
    if 0 <= lowx <= last_x:
        ax.scatter([lowx], [s.lps.low], marker="D", s=45, color=color,
                   edgecolor="white", linewidth=0.5, zorder=7)
    width = (s.R - s.S) / s.S
    return f"{label}: R={s.R:.2f} S={s.S:.2f} w={width:.3f}"


def _draw_on_events(ax, df, s_on, atr, base_off):
    """The flag-ON pair's qualified deep events, re-derived through the same
    pure judgment the pool used (display only — nothing is re-decided)."""
    if s_on is None:
        return
    start = int(s_on.box.start_bar)
    read = qualify_pair_events(df.iloc[start:], s_on.S, s_on.R, atr)
    if read is None:
        return
    for e in read["excursions"]:
        zs = start + e["start"] - base_off
        ze = start + e["end"] - base_off
        ax.axvspan(zs - 0.4, ze - 0.6, color=_C_ZONE, alpha=0.10, zorder=0)
        for x in (zs - 0.4, ze - 0.6):
            ax.axvline(x, color=_C_ZONE, ls=":", lw=1.0, alpha=0.6, zorder=2)


def _render_mark(fig, ax, mark, df, atr, s_off, s_on, note):
    closes = df["Close"].values.astype(float)

    span_s = _bar(df, mark["box_span_drawn"][0])
    span_e = _bar(df, mark["box_span_drawn"][1])
    base_off = max(0, span_s - 30)
    last_x = len(df) - 1 - base_off

    sl = df.iloc[base_off:]
    _draw_bars(ax, sl.get("Open", sl["Close"]).values.astype(float),
               sl["High"].values.astype(float), sl["Low"].values.astype(float),
               sl["Close"].values.astype(float))

    # Operator ground truth: drawn rails across the drawn span + Phase C.
    dR, dS = float(mark["rails_drawn"]["R"]), float(mark["rails_drawn"]["S"])
    ax.hlines([dR, dS], span_s - base_off, span_e - base_off, colors=_DRAWN,
              lw=1.8, alpha=0.95, zorder=5)
    for lvl, tag in ((dR, " R drawn"), (dS, " S drawn")):
        ax.text(span_e - base_off, lvl, tag, color=_DRAWN, va="center",
                fontsize=8, fontweight="bold")
    pc = mark["phase_c"]
    cs, ce, ct = _bar(df, pc["start"]), _bar(df, pc["end"]), _bar(df, pc["tip"])
    ax.axvspan(cs - base_off - 0.4, ce - base_off + 0.4, color=_C_ZONE,
               alpha=0.08, zorder=0)
    ax.scatter([ct - base_off], [float(pc["tip_low"])], marker="v", s=110,
               color=_C_ZONE, edgecolor="white", linewidth=0.6, zorder=7)
    ax.annotate("C (ruled)", (ct - base_off, float(pc["tip_low"])),
                textcoords="offset points", xytext=(0, -11), ha="center",
                fontsize=7.5, color=_C_ZONE, va="top", fontweight="bold")

    # Divergence exhibit: closes inside the drawn span below the drawn S.
    div = [i for i in range(span_s, span_e + 1) if closes[i] < dS]
    if div:
        ax.scatter([i - base_off for i in div], [closes[i] for i in div],
                   marker=".", s=26, color="#dc2626", alpha=0.9, zorder=6)

    # Engine A/B (captured by the caller at the snapped eval date).
    line_off = _draw_engine(ax, s_off, "flag-OFF", _OFF, base_off, last_x, atr)
    same = (s_off is not None and s_on is not None
            and (s_off.R, s_off.S, s_off.box.start_bar)
            == (s_on.R, s_on.S, s_on.box.start_bar))
    if same:
        line_on = "flag-ON: identical (band pool never consulted)"
    else:
        line_on = _draw_engine(ax, s_on, "flag-ON", _ON, base_off, last_x, atr)
        _draw_on_events(ax, df, s_on, atr, base_off)

    ax.set_xlim(-1, last_x + 1)
    ax.margins(y=0.08)
    ax.grid(True, alpha=0.12)
    step = max(1, (last_x + 1) // 9)
    ticks = list(range(0, last_x + 1, step))
    ax.set_xticks(ticks)
    ax.set_xticklabels([str(df.index[base_off + t])[:10] for t in ticks],
                       rotation=35, ha="right", fontsize=7)

    drawn_w = (dR - dS) / dS
    lines = [f"drawn: R={dR:.2f} S={dS:.2f} w={drawn_w:.3f}", line_off, line_on]
    if note:
        lines.append(note)
    if div:
        lines.append(f"{len(div)} closes < drawn S inside the drawn span (red dots)")
    ax.set_title(f"{mark['ticker']} @ {df.index[-1].date()}   " + "   |   ".join(lines[:3]),
                 fontsize=10, fontweight="bold", loc="left")
    ax.text(0.005, 0.02, "\n".join(lines), transform=ax.transAxes, fontsize=8,
            family="monospace", va="bottom",
            bbox=dict(facecolor="white", alpha=0.75, edgecolor="none"))

    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch
    ax.legend(handles=[
        Line2D([0], [0], color=_DRAWN, lw=1.8, label="drawn rails (operator)"),
        Line2D([0], [0], color=_OFF, lw=1.3, ls="--", label="engine flag-OFF"),
        Line2D([0], [0], color=_ON, lw=1.3, ls="--", label="engine flag-ON"),
        Patch(facecolor=_C_ZONE, alpha=0.2, label="Phase C (ruled / qualified)"),
        Line2D([0], [0], marker=".", color="w", markerfacecolor="#dc2626",
               markersize=9, label="close < drawn S"),
    ], loc="upper left", fontsize=7.5, framealpha=0.9)
    return lines


def _snapped_reads(raw, span_end):
    """The read at the drawn span's last day — or, when both flag modes read
    NONE there, the most recent prior session (within a few days) where either
    mode elects — via the shared day-snapped capture (tools.replay). The note
    wording stays render-owned."""
    snapped = snapped_election(raw, span_end, _VARIANTS)
    if snapped is None:
        return None
    (df, atr, (s_off, s_on)), ts, k = snapped
    last = raw.index[raw.index <= pd.Timestamp(span_end)][-1]
    note = "" if k == 0 else (f"snapped {k} session(s) back: no election "
                              f"either flag at {last.date()}")
    return (df, atr, s_off, s_on), ts, note


def render(tickers, *, marks_path, out_dir):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    with open(marks_path, "r", encoding="utf-8") as f:
        marks = json.load(f)["marks"]
    try:
        corpus_frames, _ = load_sealed_fixture()
    except FileNotFoundError:
        corpus_frames = {}
    os.makedirs(out_dir, exist_ok=True)

    written = []
    for mark in marks:
        t = mark["ticker"].upper()
        if tickers and t not in tickers:
            continue
        raw, src = resolve_frame(t, sealed=corpus_frames)
        if raw is None:
            print(f"  [skip {t}] {src}")
            continue
        snapped = _snapped_reads(raw, mark["box_span_drawn"][1])
        if snapped is None:
            print(f"  [skip {t}] _prepare_eval_frame -> None ({src})")
            continue
        (df, atr, s_off, s_on), as_of, note = snapped
        fig, ax = plt.subplots(figsize=(16, 7))
        try:
            lines = _render_mark(fig, ax, mark, df, atr, s_off, s_on, note)
        except Exception as exc:
            print(f"  [error {t}] {type(exc).__name__}: {exc}")
            plt.close(fig)
            continue
        fig.suptitle(f"{t} — band-rails A/B on the frozen frame "
                     f"({src}, as-of {as_of.date()})",
                     fontsize=12, fontweight="bold")
        fig.tight_layout(rect=(0, 0, 1, 0.96))
        out = os.path.join(out_dir, f"{t}.png")
        fig.savefig(out, dpi=125)
        plt.close(fig)
        written.append(out)
        print(f"  {t} ({src}): " + " | ".join(lines))
        print(f"    -> {out}")
    return written


def main():
    ap = argparse.ArgumentParser(
        description="Render engine flag-OFF vs flag-ON rails vs the operator's "
                    "drawn rails for the deep Phase-C calibration marks.")
    ap.add_argument("tickers", nargs="*", help="subset of marked tickers (default: all)")
    ap.add_argument("--marks", default=_MARKS, help="calibration marks JSON")
    ap.add_argument("--out", default=_OUT_DIR, help="output dir for PNGs")
    a = ap.parse_args()
    render({t.upper() for t in a.tickers}, marks_path=a.marks, out_dir=a.out)


if __name__ == "__main__":
    main()
