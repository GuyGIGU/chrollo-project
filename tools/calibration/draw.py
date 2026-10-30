"""The one bar drawer every board's page uses: OHLC bars, never candles (his standing rule).

It came out of the fidelity renderer (``tools/research/full_package_render.py``, retired with the old engine
on 31/10/2026). One copy, so no board's bars can drift from another's.
"""
from __future__ import annotations


def _draw_bars(ax, o, h, low, c):
    """OHLC bars, up teal / down red."""
    n = len(c)
    tick = 0.34
    lw = 1.0 if n > 90 else 1.3
    for i in range(n):
        up = c[i] >= o[i]
        col = "#1f9d8b" if up else "#e04848"
        ax.plot([i, i], [low[i], h[i]], color=col, lw=lw, alpha=0.55, zorder=2)
        ax.plot([i - tick, i], [o[i], o[i]], color=col, lw=lw, alpha=0.55, zorder=2)
        ax.plot([i, i + tick], [c[i], c[i]], color=col, lw=lw, alpha=0.55, zorder=2)
