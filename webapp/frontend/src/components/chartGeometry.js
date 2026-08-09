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

// A bar COUNT from a payload field: non-finite or negative -> null, so a
// malformed/boxless payload takes a defined fallback path instead of poisoning
// the window arithmetic (Math.max(40, NaN) is NaN, and {from: NaN} renders an
// arbitrary window with no error).
const barCount = (value) => {
  const number = Number(value);
  return Number.isFinite(number) && number >= 0 ? Math.trunc(number) : null;
};

// --- framing profiles ---
//
// Visible-bar budget, price-scale margins and volume-band top travel together
// per surface: they jointly decide what fraction of the pane a base occupies,
// which IS the honest-proportion question. They used to live scattered (budgets
// as component defaults, margins inline in two option builders, volumeScaleTop
// per hook call), so retuning proportion meant a synchronized multi-file edit
// and one missed site left a surface reading dishonestly. One table instead.
// PROPORTION (the honest-fit rule, measured 2026-08-09): the shipped window was
// chosen by bar COUNT alone, blind to the price RANGE those context bars drag
// in — so a tall pre-base leg made autoscale compress the base into a sliver.
// Measured over the live artifact's top 20 setups, the box owned a median 24.7%
// of the visible price range (16/20 below the 33% floor) while density sat at
// the 5.33px/bar ceiling: bars could not get wider, so the base could only get
// its height back by dropping the OLDEST context bars. minBaseHeightFrac is the
// target; trimFloorBars bounds how far that trim may go, so a base can never
// sprawl edge-to-edge and read tighter than it is (the 2026-07 failure).
export const CHART_FRAMING = {
  mini: {
    maxVisibleBars: 130,
    minVisibleBars: 90,
    trimFloorBars: 55,
    minContextBars: 18,
    minBaseHeightFrac: 0.4,
    scaleMargins: { top: 0.06, bottom: 0.14 },
    volumeScaleTop: 0.86,
  },
  modal: {
    contextBars: 90,
    minVisibleBars: 120,
    trimFloorBars: 80,
    minContextBars: 25,
    minBaseHeightFrac: 0.4,
    scaleMargins: { top: 0.06, bottom: 0.16 },
    volumeScaleTop: 0.84,
  },
  market: {
    visibleBars: 100,
    smaWarmupBars: 200,
    scaleMargins: { top: 0.08, bottom: 0.22 },
    volumeScaleTop: 0.82,
  },
};

// ~252 trading sessions per 365 calendar days. Used only to size a fetch window.
const TRADING_DAYS_PER_CALENDAR_DAY = 252 / 365;

// Calendar days to request so that `visibleBars` bars are ALL covered by a
// `warmupBars`-period average. SMA200 consumes 199 bars before its first point,
// so a fetch sized to the visible window alone leaves the overlay starting
// mid-pane — which reads as a data bug, not a warm-up. Derived, never guessed:
// the two constants can no longer drift apart in separate edits.
export const marketFetchDays = (visibleBars, warmupBars) => {
  const bars = (barCount(visibleBars) ?? 0) + (barCount(warmupBars) ?? 0);
  if (bars <= 0) return 0;
  return Math.ceil((bars / TRADING_DAYS_PER_CALENDAR_DAY) / 10) * 10;
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

// Trim the OLDEST context bars until the box owns at least minBaseHeightFrac of
// the visible price range. This is the ONLY legal lever for the vertical ratio:
// bars are never widened past the faithful-density band and the price scale is
// never clamped — we simply stop showing the tall pre-base leg that was eating
// the pane. Dropping old bars can only shrink the visible range, so the ratio is
// monotone in `from`; the leftmost index that still satisfies the target is the
// one that keeps the MOST context. `trimFloor` is the rightmost `from` allowed
// (callers bound it by the box's own start, so a trim can never crop the base).
export const proportionTrimmedFrom = (candles, from, to, boxHeight, trimFloor, minFrac) => {
  const ceiling = Math.min(trimFloor, to);
  if (!(boxHeight > 0) || !(minFrac > 0) || ceiling <= from) return from;

  let high = -Infinity;
  let low = Infinity;
  const widen = (index) => {
    const candle = candles[index];
    if (!candle) return;
    const candleHigh = Number(candle.high);
    const candleLow = Number(candle.low);
    if (Number.isFinite(candleHigh) && candleHigh > high) high = candleHigh;
    if (Number.isFinite(candleLow) && candleLow < low) low = candleLow;
  };

  for (let index = ceiling; index <= to; index += 1) widen(index);
  if (!(high > low)) return from;
  // Even the most-trimmed window can't reach the target (a genuinely tiny box on
  // a volatile chart) — take the best available rather than pretending.
  if (boxHeight / (high - low) < minFrac) return ceiling;

  let best = ceiling;
  for (let index = ceiling - 1; index >= from; index -= 1) {
    widen(index);
    if (boxHeight / (high - low) < minFrac) break;
    best = index;
  }
  return best;
};

// The focused logical range for the mini-chart (pure computation; the caller
// applies it via chart.timeScale().setVisibleLogicalRange).
//
// Show the base WITH real pre-base trend context so it occupies a true FRACTION
// of the pane and never sprawls edge-to-edge (which flattens a tight base into
// looking even tighter). The window is nominally clamped to
// [minVisibleBars .. maxVisibleBars], but BOTH bounds yield to the structure:
// neither may crop the box or its approach leg, so a base wider than the budget
// stretches the window instead of losing its left edge. The proportion trim then
// removes old context until the box owns its share of the visible price range.
//
// TOTAL by contract: the only null is "no candles". A payload with no finite
// base_len (a boxless candle array — the hover popover and the index panes reuse
// this same math) falls back to the last maxVisibleBars bars rather than
// returning {from: NaN}. The min <= max relationship is enforced HERE; it used
// to be call-site discipline, and an inverted pair silently blew the budget.
export const miniFocusLogicalRange = (data, maxVisibleBars, minVisibleBars = 0, profile = CHART_FRAMING.mini) => {
  const candles = data?.candles || [];
  if (!candles.length) return null;

  const lastIndex = candles.length - 1;
  const budget = barCount(maxVisibleBars);
  const floor = Math.min(barCount(minVisibleBars) ?? 0, budget ?? Infinity);
  const baseLen = barCount(data.base_len);
  const forwardBars = barCount(data.forward_bars) ?? 0;

  if (baseLen == null || baseLen <= 0) {
    return { from: budget == null ? 0 : Math.max(0, lastIndex - budget), to: lastIndex };
  }

  const baseEnd = Math.max(0, lastIndex - forwardBars);
  const baseStart = Math.max(0, baseEnd - baseLen + 1);

  const rightPadding = Math.max(5, Math.min(9, forwardBars + 5));
  const rightEdge = Math.min(lastIndex, baseEnd + rightPadding);

  const leftPadding = Math.max(40, baseLen);
  const desiredFrom = Math.max(0, baseStart - leftPadding);
  // The budget cap and the window floor both stop at the approach leg: a base
  // wider than the budget STRETCHES the window rather than having its left edge
  // cropped off-screen (ruling 2026-08-09 — the box is the datum; a box whose
  // open is off-pane misreports where the base began, and a box with no leg in
  // front of it can't be judged at all).
  const contextFloor = Math.max(0, baseStart - (profile?.minContextBars ?? 0));
  const maxFrom = Math.min(budget == null ? 0 : Math.max(0, rightEdge - budget), contextFloor);
  const minFrom = Math.min(Math.max(0, rightEdge - floor), contextFloor);

  // Don't exceed the max budget (>= maxFrom), then ensure at least the min
  // window (<= minFrom). With min=0, minFrom===rightEdge so this is a no-op.
  let from = Math.max(desiredFrom, maxFrom);
  from = Math.min(from, minFrom);

  // Then drop the oldest context bars until the box owns its share of the pane —
  // but always keep the approach leg on screen. A base only means something
  // relative to the move that led into it, so the trim stops minContextBars
  // before the box opens (measured: without this bound a ~110-bar base ate the
  // entire window and read as sprawl, the exact 2026-07 failure mode).
  const trimBars = Math.min(profile?.trimFloorBars ?? 0, floor || Infinity);
  const trimFloor = Math.min(contextFloor, Math.max(0, rightEdge - trimBars));
  const boxHeight = (finiteNumber(data.R) ?? 0) - (finiteNumber(data.S) ?? 0);
  from = proportionTrimmedFrom(candles, from, rightEdge, boxHeight, trimFloor, profile?.minBaseHeightFrac ?? 0);

  return { from, to: rightEdge };
};

// The modal's focused window, in the SAME logical-index units as the mini card's
// (it was hand-rolled inside the modal hook, untested, re-deriving baseEnd
// instead of reusing this module's index math). The modal shows the base with
// substantial pre-base trend context so it renders at a faithful daily density
// instead of a few dozen bars stretched wide, which flattened the base.
export const modalFocusLogicalRange = (data, profile = CHART_FRAMING.modal) => {
  const candles = data?.candles || [];
  if (!candles.length) return null;

  const lastIndex = candles.length - 1;
  const forwardBars = barCount(data.forward_bars) ?? 0;
  const baseLen = barCount(data.base_len) ?? 0;
  const baseEnd = lastIndex - forwardBars;
  const context = Math.max(baseLen + profile.contextBars, profile.minVisibleBars);
  const from = Math.max(0, baseEnd - context);

  // Same honest-proportion trim as the card, bounded by the box's own start so
  // the modal and the card cannot disagree about how much pane the base owns.
  const baseStart = Math.max(0, baseEnd - baseLen + 1);
  const contextFloor = Math.max(0, baseStart - (profile.minContextBars ?? 0));
  const trimFloor = Math.min(contextFloor, Math.max(0, baseEnd - (profile.trimFloorBars ?? 0)));
  const boxHeight = (finiteNumber(data.R) ?? 0) - (finiteNumber(data.S) ?? 0);

  return {
    from: proportionTrimmedFrom(candles, from, lastIndex, boxHeight, trimFloor, profile.minBaseHeightFrac ?? 0),
    to: lastIndex,
  };
};

// The index panes' window: the most recent visibleBars bars. null means "the
// history is shorter than the budget" — the caller fits the content instead.
export const marketFocusLogicalRange = (candles, visibleBars) => {
  const length = candles?.length || 0;
  const bars = barCount(visibleBars);
  if (!length || bars == null || bars <= 0 || length <= bars) return null;
  return { from: length - bars, to: length - 1 };
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
