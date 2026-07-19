// Pure chart-geometry helpers shared by the candle-chart sites.
//
// These are the bug-prone off-by-one transforms (Dodds Principle 4): they mirror
// the engine's own base/LPS/forward-bar boundary math and decide which candles
// get painted and where rails/ranges sit. They are pure (data in, data out, no
// chart state) and unit-tested in chartGeometry.test.js. Each function preserves
// the EXACT behavior of the site it was lifted from — sites that diverge keep
// distinct functions rather than a merged one.
//
// NOTE: root-swing coloring AND LPS coloring are both SHARED with the modal via
// chartPhaseOverlay (`rootSwingRange` for the grey root swing — the r/s anchor pair
// the box's rails are drawn from, `colorLpsCandles` for the chronological gold
// gradient), so the card and the modal colour the identical bars by construction.
// chartPhaseOverlay is import-free (no lightweight-charts, no DOM at load), so
// importing its pure helpers keeps this module Node-testable. Colors come from the
// chartTheme palette (also pure).

import { CHART_COLORS } from './chartTheme.js';
import { colorLpsCandles, rootSwingRange } from './chartPhaseOverlay.js';

// null / '' -> null (NOT 0). Number(null) === 0 would draw a phantom rail at
// price 0 on any timeframe with no box. This is the canonical copy used by the
// chart sites; chartIndicators.js and chartPhaseOverlay.js keep their own
// private copies on purpose, so those two modules stay dependency-free.
export const finiteNumber = (value) => {
  if (value == null || value === '') return null;
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
};

// A horizontal level line: same value repeated from startIndex to endIndex
// (inclusive). endIndex defaults to the last candle — the parent box rails run to
// the chart's right edge — but the inner mini-consolidation passes an explicit
// endIndex so its rails stop at the coil's last structurally-anchored bar.
export const buildLevelData = (candles, startIndex, value, endIndex = candles.length - 1) =>
  candles.slice(startIndex, endIndex + 1).map((candle) => ({ time: candle.time, value }));

// Full-width level line (every candle). Used by TimeframeMainChart, which slices
// the candle array itself before calling this.
export const buildFullLevelData = (candles, value) =>
  candles.map((candle) => ({ time: candle.time, value }));

// A guarded level for a single price: empty array if the price is non-finite or
// <= 0 (PortfolioPositionChart's avg-cost line — never draw a 0 rail).
export const buildPositiveLevel = (candles, value) => {
  const price = Number(value);
  if (!Number.isFinite(price) || price <= 0) return [];
  return candles.map((candle) => ({ time: candle.time, value: price }));
};

// --- date helpers (ScreenerMiniChart variant: no out-of-range bounds check) ---

export const candleDate = (candle) => {
  if (!candle?.time) return '';
  if (typeof candle.time === 'string') return candle.time.slice(0, 10);
  if (typeof candle.time === 'object') {
    const month = String(candle.time.month).padStart(2, '0');
    const day = String(candle.time.day).padStart(2, '0');
    return `${candle.time.year}-${month}-${day}`;
  }
  return '';
};

export const indexOnOrAfter = (candles, rawDate) => {
  const target = typeof rawDate === 'string' ? rawDate.slice(0, 10) : null;
  if (!target) return null;
  const index = candles.findIndex((candle) => candleDate(candle) >= target);
  return index >= 0 ? index : null;
};

// --- setup index math (ScreenerMiniChart) ---

export const setupIndexes = (data) => {
  const candles = data.candles || [];
  const forwardBars = data.forward_bars || 0;
  const baseEnd = Math.max(0, candles.length - 1 - forwardBars);
  const baseStart = Math.max(0, baseEnd - data.base_len + 1);
  return { baseEnd, baseStart, candles, forwardBars };
};

// The focused logical range for the mini-chart (pure computation; the caller
// applies it via chart.timeScale().setVisibleLogicalRange).
//
// Faithful-density window (Finviz-style): show the base WITH real pre-base
// trend context so it occupies a true FRACTION of the pane, never sprawling
// edge-to-edge (which flattens a tight base into looking even tighter). The
// window width is clamped to [minVisibleBars .. maxVisibleBars]: maxFrom caps
// huge bases to the budget; minFrom pads a tiny base out to the floor. With the
// default minVisibleBars=0 the floor is inert (old single-arg behavior).
export const miniFocusLogicalRange = (data, maxVisibleBars, minVisibleBars = 0) => {
  const { baseEnd, baseStart, candles, forwardBars } = setupIndexes(data);
  if (!candles.length) return null;

  const rightPadding = Math.max(5, Math.min(9, forwardBars + 5));
  const rightEdge = Math.min(candles.length - 1, baseEnd + rightPadding);

  const leftPadding = Math.max(40, Math.round(data.base_len));
  const desiredFrom = Math.max(0, baseStart - leftPadding);
  const maxFrom = Math.max(0, rightEdge - maxVisibleBars);
  const minFrom = Math.max(0, rightEdge - minVisibleBars);

  // Don't exceed the max budget (>= maxFrom), then ensure at least the min
  // window (<= minFrom). With min=0, minFrom===rightEdge so this is a no-op.
  let from = Math.max(desiredFrom, maxFrom);
  from = Math.min(from, minFrom);

  return { from, to: rightEdge };
};

// --- box rail geometry (shared by the mini card AND the modal) ---

// The full set of structure rails for a setup, as pure {kind, startIndex, value}
// specs. This is THE box-rail read: chartRails.addBoxRails maps these specs to
// line series for both the screener card and the modal, so the two surfaces are
// structurally incapable of drawing different rails for the same setup.
// R/S/mid are emitted unconditionally (matching both prior sites); the inner
// box only when all three inner fields are finite.
export const boxRailSpecs = (data) => {
  const candles = data.candles || [];
  const { baseStart } = setupIndexes(data);
  const specs = [
    { kind: 'rail', startIndex: baseStart, value: data.R },
    { kind: 'rail', startIndex: baseStart, value: data.S },
    { kind: 'mid', startIndex: baseStart, value: (Number(data.R) + Number(data.S)) / 2 },
  ];

  const innerR = finiteNumber(data.inner_R);
  const innerS = finiteNumber(data.inner_S);
  const innerStartBar = finiteNumber(data.inner_start_bar);
  if (innerR != null && innerS != null && innerStartBar != null) {
    const lastIndex = candles.length - 1;
    const innerStart = Math.max(0, Math.min(lastIndex, Math.trunc(innerStartBar)));
    // Bound the inner box to its last structurally-anchored bar (inner_end_bar) so
    // the mini-consolidation rails hug the coil and stop before the reserved
    // trigger/breakout bars — unlike the parent box, which runs to the edge. Older
    // payloads / the archive omit inner_end_bar → fall back to the right edge.
    const innerEndBar = finiteNumber(data.inner_end_bar);
    const innerEnd = innerEndBar != null
      ? Math.max(innerStart, Math.min(lastIndex, Math.trunc(innerEndBar)))
      : lastIndex;
    specs.push({ kind: 'inner', startIndex: innerStart, endIndex: innerEnd, value: innerR });
    specs.push({ kind: 'inner', startIndex: innerStart, endIndex: innerEnd, value: innerS });
  }
  return specs;
};

// --- candle coloring ---

// ScreenerMiniChart coloring: root-swing (the r/s anchor pair the box's rails are
// drawn from) grey, LPS zones painted by the shared chronological gold gradient (via
// colorLpsCandles). Operates on a deep clone so the source payload is untouched.
export const colorMiniCandles = (data) => {
  const candles = JSON.parse(JSON.stringify(data.candles || []));
  if (data.base_len <= 0) return candles;

  // Grey the ROOT SWING bars via the SAME shared span the modal uses, so the card and
  // the big chart colour identical bars.
  const rootSwing = rootSwingRange(data, candles);
  if (rootSwing) {
    for (let index = rootSwing.startIndex; index <= rootSwing.endIndex; index += 1) {
      if (index >= 0 && index < candles.length) candles[index].color = CHART_COLORS.baseLimb;
    }
  }

  // LPS coloring is delegated to the SHARED phase-region colorer so the mini card
  // and the modal paint the IDENTICAL chronological gold gradient (oldest brown ->
  // latest gold). goldMuted is the dense-card flat fallback, applied only when no
  // LPS region resolves (matching the pre-unification lps_offset last resort).
  colorLpsCandles(candles, data, CHART_COLORS.goldMuted);

  return candles;
};

// TimeframeMainChart coloring: base limb grey, LPS support test gold, both keyed
// by date span (htf.chart_box dates). Shallow clone matches the original.
export const colorTimeframeCandles = (candles, { limbStart, limbEnd, lpsStart, lpsEnd }) => {
  const out = candles.map((candle) => ({ ...candle }));
  const paint = (from, to, color) => {
    if (!from || !to) return;
    for (let i = 0; i < out.length; i += 1) {
      if (out[i].time >= from && out[i].time <= to) out[i].color = color;
    }
  };
  paint(limbStart, limbEnd, CHART_COLORS.baseLimb);
  paint(lpsStart, lpsEnd, CHART_COLORS.gold);
  return out;
};

// --- visible range (TradeSetupChart) ---

// Logical range centered on the trade's opening date (+/- 45 bars). Pure; the
// caller applies it or falls back to fitContent.
export const tradeVisibleLogicalRange = (candles, openingDate) => {
  if (!openingDate) return null;
  const entryIndex = candles.findIndex(
    (candle) => String(candle.time) >= String(openingDate).slice(0, 10),
  );
  if (entryIndex < 0) return null;
  return {
    from: Math.max(0, entryIndex - 45),
    to: Math.min(candles.length - 1, entryIndex + 45),
  };
};
