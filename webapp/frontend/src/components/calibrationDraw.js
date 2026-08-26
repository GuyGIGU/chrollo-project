import { LineSeries, createSeriesMarkers } from 'lightweight-charts';
import { CHART_COLORS } from './chartTheme';

// Annotation drawer for the calibration chart — the ONE owner of everything
// drawn over the bars, deliberately SEPARATE from chartRails.addBoxRails
// (that module draws the screener's elected structure once per chart build;
// this one is RETAINED — attached once in onReady, then updated per state
// change without rebuilding, so zoom and pan survive every placement click).
//
// Three layers, color doctrine (Task 13 + operator feedback 2026-07-11):
//   draft  — the in-flight mark: mythril while fresh, the reserved operator
//            hue when a SAVED mark is loaded for correction.
//   saved  — every banked mark on THIS frame, always in the operator hue.
//            Before this layer existed, saving and starting the next mark
//            visually erased everything ("my drawings got removed").
//   engine — the engine's read through the agreement-harness lens, in the
//            ENGINE rail color (dashed) — never the operator hue, so ground
//            truth and machine opinion cannot be confused.
//
// Rails are drawn BOUNDED to the box they belong to (operator feedback
// 2026-07-21): a boundary that stretches edge-to-edge past where the box lives
// reads as noise. A rail with a known span is a 2-point LineSeries across
// [start, end] (same convention as chartRails.buildLevelData); a rail placed
// before its span exists yet — a lone draft rail mid-drawing — falls back to a
// full-width price line so the operator still sees what they just clicked.
const EVENT_TAG = { phase_c: 'C', lps: 'L', spring_test: 'T',
                    sos: 'S', mini_consolidation: 'M' };

// An event carrying a price band (the mini-consolidation) draws as a small box:
// its two levels, bounded to its own span — the same primitive the mark's own
// rails use, so a nested box reads exactly like the box it sits inside.
const eventBand = (drawRail, candles, ev, opts) => {
  if (ev.band_high == null || ev.band_low == null) return;
  drawRail(candles, ev.start_date, ev.end_date, ev.band_high, '', opts);
  drawRail(candles, ev.start_date, ev.end_date, ev.band_low, '', opts);
};

const railOptions = (color, lineStyle = 0) => ({
  color, lineWidth: 1, lineStyle,
  priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false,
});

// The candle slice a bounded rail spans. ISO date strings compare
// lexicographically, so a plain range filter is correct and cheap. Returns null
// when the span isn't drawable yet (no dates, or no candles inside it).
const boundedSegment = (candles, startDate, endDate, value) => {
  if (!startDate || !endDate) return null;
  const seg = candles
    .filter((c) => c.time >= startDate && c.time <= endDate)
    .map((c) => ({ time: c.time, value }));
  return seg.length ? seg : null;
};

export function attachCalibrationDraw(chart, series) {
  let priceLines = [];
  let railSeries = [];
  const markers = createSeriesMarkers(series, []);

  const priceLine = (price, title, options) => {
    priceLines.push(series.createPriceLine({
      price, title, lineWidth: 1, lineStyle: 0, axisLabelVisible: true, ...options,
    }));
  };

  // A rail bounded to [startDate, endDate] when the span is known, else a
  // full-width price line (a rail placed before its span exists still shows).
  const rail = (candles, startDate, endDate, price, title,
                { color, lineStyle = 0, axisLabelVisible = true }) => {
    const seg = boundedSegment(candles, startDate, endDate, price);
    if (seg) {
      const line = chart.addSeries(LineSeries, railOptions(color, lineStyle));
      line.setData(seg);
      railSeries.push(line);
    } else {
      priceLine(price, title, { color, lineStyle, axisLabelVisible });
    }
  };

  const clearDrawn = () => {
    for (const line of priceLines) series.removePriceLine(line);
    priceLines = [];
    for (const line of railSeries) chart.removeSeries(line);
    railSeries = [];
  };

  const update = ({ draft, draftSpan = null, spanAnchor, committed = false,
                    saved = [], engine = null, candles = [] }) => {
    const DRAWING = committed ? CHART_COLORS.operator : CHART_COLORS.marking;
    clearDrawn();
    const marks = [];

    // Saved marks on this frame: geometry stays visible for the whole sitting;
    // rails bounded to each mark's own span, no axis labels (the draft owns the
    // price axis).
    for (const mark of saved) {
      const opts = { color: CHART_COLORS.operator, axisLabelVisible: false };
      if (mark.resistance != null) {
        rail(candles, mark.box_start_date, mark.box_end_date, mark.resistance, '', opts);
      }
      if (mark.support != null) {
        rail(candles, mark.box_start_date, mark.box_end_date, mark.support, '', opts);
      }
      if (mark.box_start_date) {
        marks.push({ time: mark.box_start_date, position: 'belowBar',
                     shape: 'arrowUp', color: CHART_COLORS.operator, text: '[' });
      }
      if (mark.box_end_date) {
        marks.push({ time: mark.box_end_date, position: 'belowBar',
                     shape: 'arrowUp', color: CHART_COLORS.operator, text: ']' });
      }
      for (const ev of mark.events ?? []) {
        const tag = EVENT_TAG[ev.event_type] ?? '?';
        marks.push({ time: ev.start_date, position: 'aboveBar',
                     shape: 'circle', color: CHART_COLORS.operator, text: tag });
        if (ev.end_date !== ev.start_date) {
          marks.push({ time: ev.end_date, position: 'aboveBar',
                       shape: 'circle', color: CHART_COLORS.operator, text: tag });
        }
        eventBand(rail, candles, ev, opts);
      }
      // The Trigger (buy) — a single 'B' flag in its warm token, never the
      // operator hue: it is the entry, not another ground-truth rail. Just the
      // flag, no full-width buy line (operator: the line stretching the whole
      // screen is clutter). Above the bar, so it points DOWN at it.
      if (mark.trigger_date != null && mark.trigger_price != null) {
        marks.push({ time: mark.trigger_date, position: 'aboveBar',
                     shape: 'arrowDown', color: CHART_COLORS.trigger, text: 'B' });
      }
    }

    // The engine's read (explicit toggle; harness projection verbatim). Its
    // box_end_date is the frame end by construction, so the rail runs from the
    // box start to the last bar, and only the start is marked.
    if (engine?.elected) {
      const lastTime = candles.length ? candles[candles.length - 1].time : null;
      const opts = { color: CHART_COLORS.rail, lineStyle: 2 };
      rail(candles, engine.box_start_date, lastTime, engine.R, 'eR', opts);
      rail(candles, engine.box_start_date, lastTime, engine.S, 'eS', opts);
      if (engine.box_start_date) {
        marks.push({ time: engine.box_start_date, position: 'belowBar',
                     shape: 'arrowUp', color: CHART_COLORS.rail, text: 'E[' });
      }
    }

    // The in-flight draft, drawn last (its rails ride over the others). Bounded
    // to the effective span the mark will save; until both rails exist the span
    // is unknown and each lone rail shows as a transient full-width line.
    const dStart = draftSpan?.start ?? null;
    const dEnd = draftSpan?.end ?? null;
    const railStyle = { color: DRAWING };
    if (draft.resistance != null) rail(candles, dStart, dEnd, draft.resistance, 'R', railStyle);
    if (draft.support != null) rail(candles, dStart, dEnd, draft.support, 'S', railStyle);
    // The swing bars each rail was anchored on — the root-swing intent the
    // mark carries (span derives from these unless x-drawn).
    if (draft.rAnchorDate) {
      marks.push({ time: draft.rAnchorDate, position: 'aboveBar',
                   shape: 'arrowDown', color: DRAWING, text: 'R' });
    }
    if (draft.sAnchorDate) {
      marks.push({ time: draft.sAnchorDate, position: 'belowBar',
                   shape: 'arrowUp', color: DRAWING, text: 'S' });
    }
    if (draft.boxStartDate) {
      marks.push({ time: draft.boxStartDate, position: 'belowBar',
                   shape: 'arrowUp', color: DRAWING, text: '[' });
    }
    if (draft.boxEndDate) {
      marks.push({ time: draft.boxEndDate, position: 'belowBar',
                   shape: 'arrowUp', color: DRAWING, text: ']' });
    }
    if (spanAnchor) {
      marks.push({ time: spanAnchor, position: 'belowBar',
                   shape: 'arrowUp', color: DRAWING, text: '·' });
    }
    for (const ev of draft.events) {
      const tag = EVENT_TAG[ev.event_type] ?? '?';
      marks.push({ time: ev.start_date, position: 'aboveBar',
                   shape: 'circle', color: DRAWING, text: tag });
      if (ev.end_date !== ev.start_date) {
        marks.push({ time: ev.end_date, position: 'aboveBar',
                     shape: 'circle', color: DRAWING, text: tag });
      }
      eventBand(rail, candles, ev, railStyle);
    }
    // The draft Trigger — the same 'B' flag, warm token, above the bar pointing
    // down at it (no full-width buy line).
    if (draft.triggerDate != null && draft.triggerPrice != null) {
      marks.push({ time: draft.triggerDate, position: 'aboveBar',
                   shape: 'arrowDown', color: CHART_COLORS.trigger, text: 'B' });
    }

    // lightweight-charts requires ascending marker times.
    marks.sort((a, b) => (a.time < b.time ? -1 : a.time > b.time ? 1 : 0));
    markers.setMarkers(marks);
  };

  const detach = () => {
    clearDrawn();
    markers.setMarkers([]);
  };

  return { update, detach };
}
