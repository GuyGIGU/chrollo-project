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
// One reference time scale, price-scale margins and volume-band top travel
// together per surface: they jointly decide what fraction of the pane a base
// occupies, which IS the honest-proportion question. They used to live scattered
// (budgets as component defaults, margins inline in two option builders,
// volumeScaleTop per hook call), so retuning proportion meant a synchronized
// multi-file edit and one missed site left a surface reading dishonestly.
//
// PROPORTION (re-ruled 2026-09-02). The 2026-08-09 design chased a VERTICAL
// target (minBaseHeightFrac) with a HORIZONTAL knob — deleting the oldest bars
// until the box owned 40% of the visible price range. Measured over the live
// 230: it fired on 179 cards and on 140 of those burned a median 35 context
// bars and STILL finished below its own target (the "return ceiling" escape
// hatch trimmed maximally AFTER proving the target unreachable). It succeeded
// on 39. Its price was a 56-bar collapse on 99/230 cards, a base owning a
// median 51% of card WIDTH, and 8.8% of card pairs rendering the LONGER base
// NARROWER than a shorter one — the operator's "wide choppy setups read as
// cute tight ones". RETIRED; vertical proportion is now a consequence of an
// honest window plus a taller well, never a target.
// THE MODEL (revised 2026-09-02, same day): the CONSOLIDATION sets the scale.
// The window is whatever shows the rest at baseWidthCap of the pane — "focusing
// on the consolidation area and then some room behind it for added context
// before the consolidation" — floored at minWindowBars so a very short rest
// still gets context, and capped at legibilityCeilingBars so bars never get
// too thin to read. The first cut used a FIXED 140-day slab for every setup;
// the operator ruled that "way way too much" on a 24-day rest, and he is right:
// a fixed span makes the window a property of the surface instead of a property
// of the setup, which is the same mistake in the other direction. Now a 24-day
// rest gets 83 days and a 33-day rest gets 109.
// The ceiling YIELDS to a base it cannot frame (monster zoom-out), and every
// bound yields to the never-crop rule (2026-08-09: the box is the datum). The
// 2026-07 sprawl failure — "~48 bars at ~10px/bar let a tight base sprawl
// edge-to-edge and read tighter than it is" — is held off by the cap.
export const CHART_FRAMING = {
  mini: {
    minWindowBars: 55,           // the FLOOR, not a span: a very short rest still needs room
                                 // behind it. Inert on the live 230 (the shortest rest already
                                 // earns 60+ days through the cap) — it exists so a 5-day rest
                                 // cannot produce a 43-day window.
    legibilityCeilingBars: 220,  // 435px plot / 220 = 1.98 px/bar at the very bottom — a hard
                                 // stop, not a target. It has to sit HIGH: a low ceiling makes
                                 // the window stop growing while the rest keeps growing, so a
                                 // longer rest starts drawing NARROWER than a shorter one. At
                                 // 110 that lie returns on rests as short as 37 days and the
                                 // order-inversion rate goes to 9.7% — worse than the 8.8% this
                                 // whole program exists to remove. At 220 it is 0.0% (6 pairs of
                                 // 25,904, all rests of 130+ days). Measured 2026-09-02.
    ceilingYieldShare: 0.75,     // ...and it yields to a rest it cannot frame (operator
                                 // 2026-09-02, "for monster bases simply zoom out the base").
    baseWidthCap: 0.35,          // the base + its right pad may never own more than 35% of
                                 // the pane; the leg is therefore always >= 1.86x the base.
                                 // Crossover is base_len ~44, so it is a TAIL rule (62% of
                                 // setups never touch it). Measured knee: 0.30 buys nothing
                                 // (median unchanged), 0.40 puts p90 back at 0.47.
    minContextBars: 18,          // UNCHANGED — the 2026-08-09 approach-leg ruling.
    scaleMargins: { top: 0.06, bottom: 0.14 },
    volumeScaleTop: 0.86,
  },
  modal: {
    minWindowBars: 252,          // ONE TRADING YEAR — here the floor IS the span, because the
                                 // modal's job is the stock, not the rest. 1050px plot / 252 =
                                 // 4.17 px/bar, in band.
                                 // The payload already carries a median 300 candles, so this
                                 // costs nothing and is the literal fix for "I always got to
                                 // zoom out to see the real stock" (operator 2026-09-02).
    legibilityCeilingBars: 300,  // the whole carried history; 3.50 px/bar at the floor.
    ceilingYieldShare: 0.6,      // inert here — the ceiling already IS the whole history — but
                                 // declared so every box-framed profile answers the same question.
    baseWidthCap: 0.35,          // DELIBERATELY IDENTICAL to mini — the card and the modal
                                 // can never disagree about how much pane the base owns.
    minContextBars: 25,
    scaleMargins: { top: 0.06, bottom: 0.16 },
    volumeScaleTop: 0.84,
  },
  market: {                      // UNTOUCHED — already a fixed-history window, no box to cap.
    visibleBars: 100,
    smaWarmupBars: 200,
    scaleMargins: { top: 0.08, bottom: 0.22 },
    volumeScaleTop: 0.82,
  },
  // The hover-glance glass (~380x250, ~330px plot). It shows a shallower span
  // than the card because its pane is half the width — at the card's 140-day
  // reference it would render 2.4px/bar, under the band and near the 2.3px/bar
  // the operator called indecipherable (2026-08-12).
  popover: {
    minWindowBars: 55,           // same floor as the card; the cap does the work.
    legibilityCeilingBars: 105,  // 330/105 = 3.14 px/bar, the same density floor as the card.
    ceilingYieldShare: 1,        // NOT the card's 0.6 — measured 2026-09-02. Against a 105-bar
                                 // ceiling that number is not a tail rule: it trips at base 59
                                 // and fires on 66 of 230 setups (29%), dropping 66 glances to
                                 // 1.1-1.8 px per trading day. At 1 the glance yields only when
                                 // the rest does not FIT the pane at all, which costs nothing
                                 // (20 glances under 3 px/day, the same as no yield at all,
                                 // and those are the never-crop clamp's doing) and still pulls
                                 // bases owning over 60% of the pane from 63 down to 48.
                                 // The glance is a RECOGNITION surface (ruled 2026-09-02), and
                                 // 1.1 px/day serves recognition worse than a wide base does.
    baseWidthCap: 0.35,          // same cap — the glance and the card agree on base share
                                 // even though they show different spans.
    minContextBars: 14,
    scaleMargins: { top: 0.07, bottom: 0.16 },
    volumeScaleTop: 0.88,
  },
  // The W/M preview cubes beside the modal's daily chart. The full-pane W/M
  // tabs keep their deep windows (160/120 bars); a ~360px preview showing that
  // many bars is ~2.3px/bar — indecipherable (operator 2026-08-12). The preview
  // exists to show the RECENT higher-timeframe posture, so it gets its own
  // shallow budget at a readable per-bar width. UNTOUCHED — fixed W/M windows,
  // never framed around a box.
  htfPreview: {
    weeklyBars: 64,
    monthlyBars: 48,
    scaleMargins: { top: 0.06, bottom: 0.16 },
    volumeScaleTop: 0.84,
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

// The window the consolidation earns: wide enough that the rest owns no more
// than baseWidthCap of the pane, floored at minWindowBars so a very short rest
// still gets room behind it, capped at legibilityCeilingBars so the bars stay
// readable. This is the whole model — the window is a property of the SETUP, not
// of the surface (operator 2026-09-02: "dynamic scaling based on the found
// consolidation ... focusing on the consolidation area and then some room behind
// it for added context").
//
// The ceiling then YIELDS to a base it cannot frame ("for monster bases simply
// zoom out the base"): a rest so long it would still own more than
// ceilingYieldShare of the pane AT the ceiling is not made readable by holding
// bars wide, so the window opens as far as the cap wants and history allows.
// Deliberately a TAIL rule, not a raised ceiling — raising the ceiling instead
// costs every medium-base card its legibility, measured 2026-09-02.
//
// `available` is how far back the payload actually goes; without it the window
// would ask for history that does not exist and the never-crop clause would be
// the only thing stopping it. Both bounds still yield to that clause.
const baseCappedWindow = (profile, visibleBase, rightPadding, available) => {
  const capWindow = Math.ceil((visibleBase + rightPadding) / profile.baseWidthCap);
  const ceiling = profile.legibilityCeilingBars;
  const framed = Math.max(profile.minWindowBars, Math.min(ceiling, capWindow));
  if (capWindow <= ceiling) return framed;
  // The ceiling could not satisfy the cap. Does the base still swamp the pane?
  const shareAtCeiling = (visibleBase + rightPadding) / framed;
  if (shareAtCeiling <= profile.ceilingYieldShare) return framed;
  return Math.max(framed, Math.min(capWindow, available));
};

// The focused logical range for the mini-chart (pure computation; the caller
// applies it via chart.timeScale().setVisibleLogicalRange).
//
// ONE reference time scale for every setup, so two cards side by side are at the
// SAME zoom and the consolidation's share of the pane is proportional to how
// long it actually lasted. A base long enough to cross baseWidthCap stretches
// the window (never shrinks it), bounded by legibilityCeilingBars — and both
// bounds yield to the box: neither may crop it or its approach leg.
//
// TOTAL by contract: the only null is "no candles". A payload with no finite
// base_len (a boxless candle array — the hover popover and the index panes reuse
// this same math) falls back to the plain reference window rather than returning
// {from: NaN}, so an unboxed chart renders at the SAME density as a boxed one.
export const miniFocusLogicalRange = (data, profile = CHART_FRAMING.mini) => {
  const candles = data?.candles || [];
  if (!candles.length) return null;

  const lastIndex = candles.length - 1;
  const baseLen = barCount(data.base_len);
  if (baseLen == null || baseLen <= 0) {
    // No consolidation to frame (the Watchlist's clean charts, the index panes):
    // show the widest window that is still legible on this surface.
    return { from: Math.max(0, lastIndex - profile.legibilityCeilingBars + 1), to: lastIndex };
  }

  const forwardBars = barCount(data.forward_bars) ?? 0;
  const baseEnd = Math.max(0, lastIndex - forwardBars);
  const baseStart = Math.max(0, baseEnd - baseLen + 1);
  const rightPadding = Math.max(5, Math.min(9, forwardBars + 5));
  const rightEdge = Math.min(lastIndex, baseEnd + rightPadding);

  // baseEnd - baseStart + 1, not base_len: a base longer than the carried
  // history clamps at index 0 and only its visible part can own pane.
  const window = baseCappedWindow(profile, baseEnd - baseStart + 1, rightPadding, candles.length);

  // The never-crop clause OUTRANKS everything, including the ceiling (ruling
  // 2026-08-09 — a box whose open is off-pane misreports where the base began,
  // and a box with no leg in front of it can't be judged at all).
  //
  // HONEST NOTE (2026-09-02): since the ceiling learned to yield, this clamp is
  // REDUNDANT — swept over every base length x forward count x history depth on
  // all three box-framed profiles, it never once binds, because a base long
  // enough to threaten its own leg now earns a window ~2.9x its own width. It is
  // kept as a one-token backstop, not as a live guard: raise ceilingYieldShare
  // above 1 (i.e. turn the yield off) and it goes load-bearing again in the same
  // edit. Do not read its test as proof that it fires — the invariant is proved
  // by sweep instead (chartGeometry.test.js, "the box's open is NEVER cropped").
  const contextFloor = Math.max(0, baseStart - profile.minContextBars);
  return { from: Math.min(Math.max(0, rightEdge - window + 1), contextFloor), to: rightEdge };
};

// The modal's focused window, in the SAME logical-index units as the mini card's
// (it was hand-rolled inside the modal hook, untested, re-deriving baseEnd
// instead of reusing this module's index math).
//
// The modal opens on ONE TRADING YEAR because its job is the stock, not the
// base's tightness: the operator was zooming out on every single chart to see
// what he was actually looking at (2026-09-02). It shares the card's
// baseWidthCap by construction, so the two surfaces can never disagree about
// how much pane the base owns; it differs only in reference span and in running
// to the last candle (the modal shows the forward tape). The card's old
// proportion trim deliberately does NOT run here — it does not run anywhere.
export const modalFocusLogicalRange = (data, profile = CHART_FRAMING.modal) => {
  const candles = data?.candles || [];
  if (!candles.length) return null;

  const lastIndex = candles.length - 1;
  const baseLen = barCount(data.base_len);
  if (baseLen == null || baseLen <= 0) {
    return { from: Math.max(0, lastIndex - profile.legibilityCeilingBars + 1), to: lastIndex };
  }

  const forwardBars = barCount(data.forward_bars) ?? 0;
  const baseEnd = Math.max(0, lastIndex - forwardBars);
  const baseStart = Math.max(0, baseEnd - baseLen + 1);
  const rightPadding = Math.max(5, Math.min(9, forwardBars + 5));

  const window = baseCappedWindow(profile, baseEnd - baseStart + 1, rightPadding, candles.length);
  const contextFloor = Math.max(0, baseStart - profile.minContextBars);
  return { from: Math.min(Math.max(0, lastIndex - window + 1), contextFloor), to: lastIndex };
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
  // A candles-only payload (the Watchlist page's clean chart) carries no box:
  // without this guard the parent trio ships value=undefined and mid=NaN into
  // the rail drawer — the never-exercised degrade path every scan row masked.
  const specs = [];
  // Ship the COERCED values the guard validated (the inner-box branch's
  // discipline) — guarding on finiteNumber but pushing the raw field would
  // send a numeric-string R/S into the rail drawer beside a numeric mid.
  const parentR = finiteNumber(data.R);
  const parentS = finiteNumber(data.S);
  if (parentR != null && parentS != null) {
    specs.push(
      { kind: 'rail', startIndex: baseStart, value: parentR },
      { kind: 'rail', startIndex: baseStart, value: parentS },
      { kind: 'mid', startIndex: baseStart, value: (parentR + parentS) / 2 },
    );
  }

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
