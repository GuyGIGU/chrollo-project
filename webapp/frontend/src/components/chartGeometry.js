// Pure chart-geometry helpers shared by the candle-chart sites.
//
// These are the bug-prone off-by-one transforms (Dodds Principle 4): they mirror
// the engine's own base/LPS/forward-bar boundary math and decide which candles
// get painted and where rails/ranges sit. They are pure (data in, data out, no
// chart state) and unit-tested in chartGeometry.test.js. Each function preserves
// the EXACT behavior of the site it was lifted from — sites that diverge keep
// distinct functions rather than a merged one.
//
// NOTE: the modal's structure-candle colorer stays in useScreenerModalChart
// because it is modal-specific coloring that consumes buildPhaseRegions output
// plus modal-only anchor/lps_offset fallbacks — not because of DOM coupling
// (buildPhaseRegions itself is pure). Keeping it out keeps this module a pure,
// Node-testable unit.

// null / '' -> null (NOT 0). Number(null) === 0 would draw a phantom rail at
// price 0 on any timeframe with no box. This is the canonical copy used by the
// chart sites; chartIndicators.js and chartPhaseOverlay.js keep their own
// private copies on purpose, so those two modules stay dependency-free.
export const finiteNumber = (value) => {
  if (value == null || value === '') return null;
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
};

// A horizontal level line: same value repeated from startIndex to the end. Used
// by the modal + mini charts (bounded rails anchored at the box start).
export const buildLevelData = (candles, startIndex, value) =>
  candles.slice(startIndex).map((candle) => ({ time: candle.time, value }));

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

// --- candle coloring ---

// ScreenerMiniChart coloring: base-limb swing grey, LPS test spans + the active
// LPS offset gold. Operates on a deep clone so the source payload is untouched.
export const colorMiniCandles = (data) => {
  const candles = JSON.parse(JSON.stringify(data.candles || []));
  if (data.base_len <= 0) return candles;

  const forwardBars = data.forward_bars || 0;
  const baseEnd = candles.length - 1 - forwardBars;
  const baseStart = baseEnd - data.base_len + 1;
  // baseStart in the min: the shared-rail back-extension can open the box
  // before the anchor pair; the grey base-limb must still mark its left edge.
  const limbStart = Math.min(baseStart + data.r_anchor, baseStart + data.s_anchor, baseStart);
  const limbEnd = Math.max(baseStart + data.r_anchor, baseStart + data.s_anchor);
  for (let index = limbStart; index <= limbEnd; index += 1) {
    if (index >= 0 && index < candles.length) candles[index].color = '#596070';
  }

  for (const test of data.lps_tests || []) {
    const start = indexOnOrAfter(candles, test.start_date);
    const end = indexOnOrAfter(candles, test.end_date);
    if (start == null || end == null) continue;
    for (let index = start; index <= end; index += 1) {
      if (index >= 0 && index < candles.length) candles[index].color = '#d4b85a';
    }
  }

  if (data.lps_len > 0 && data.lps_offset !== undefined) {
    const lpsEnd = baseEnd - data.lps_offset;
    const lpsStart = Math.max(0, lpsEnd - data.lps_len + 1);
    for (let index = lpsStart; index <= lpsEnd; index += 1) {
      if (index >= 0 && index < candles.length) candles[index].color = '#d4b85a';
    }
  }

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
  paint(limbStart, limbEnd, '#5d6474');
  paint(lpsStart, lpsEnd, '#e3b341');
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
