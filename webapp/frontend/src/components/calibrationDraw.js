import { createSeriesMarkers } from 'lightweight-charts';
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
const EVENT_TAG = { phase_c: 'C', lps: 'L', spring_test: 'T' };

export function attachCalibrationDraw(series) {
  let priceLines = [];
  const markers = createSeriesMarkers(series, []);

  const rail = (price, title, options) => {
    priceLines.push(series.createPriceLine({
      price, title, lineWidth: 1, lineStyle: 0, axisLabelVisible: true, ...options,
    }));
  };

  const update = ({ draft, spanAnchor, committed = false, saved = [], engine = null }) => {
    const DRAWING = committed ? CHART_COLORS.operator : CHART_COLORS.marking;
    for (const line of priceLines) series.removePriceLine(line);
    priceLines = [];
    const marks = [];

    // Saved marks on this frame: geometry stays visible for the whole
    // sitting; no axis labels — the draft owns the price axis.
    for (const mark of saved) {
      const opts = { color: CHART_COLORS.operator, axisLabelVisible: false };
      if (mark.resistance != null) rail(mark.resistance, '', opts);
      if (mark.support != null) rail(mark.support, '', opts);
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
      }
      // The Trigger (buy) — its own warm token, never the operator hue: it is a
      // distinct concept (the entry), not another ground-truth rail.
      if (mark.trigger_date != null && mark.trigger_price != null) {
        rail(mark.trigger_price, '', { color: CHART_COLORS.trigger, axisLabelVisible: false });
        marks.push({ time: mark.trigger_date, position: 'aboveBar',
                     shape: 'arrowUp', color: CHART_COLORS.trigger, text: 'B' });
      }
    }

    // The engine's read (explicit toggle; harness projection verbatim). Its
    // box_end_date is the frame end by construction, so only the start is
    // marked — a right-edge marker would be a constant, not information.
    if (engine?.elected) {
      const opts = { color: CHART_COLORS.rail, lineStyle: 2 };
      rail(engine.R, 'eR', opts);
      rail(engine.S, 'eS', opts);
      if (engine.box_start_date) {
        marks.push({ time: engine.box_start_date, position: 'belowBar',
                     shape: 'arrowUp', color: CHART_COLORS.rail, text: 'E[' });
      }
    }

    // The in-flight draft, drawn last (its rails ride over the others).
    const railStyle = { color: DRAWING };
    if (draft.resistance != null) rail(draft.resistance, 'R', railStyle);
    if (draft.support != null) rail(draft.support, 'S', railStyle);
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
    }
    // The draft Trigger — always the warm trigger token (not DRAWING): the buy
    // is its own concept, distinct from the rails whether fresh or committed.
    if (draft.triggerDate != null && draft.triggerPrice != null) {
      rail(draft.triggerPrice, 'Buy', { color: CHART_COLORS.trigger });
      marks.push({ time: draft.triggerDate, position: 'aboveBar',
                   shape: 'arrowUp', color: CHART_COLORS.trigger, text: 'B' });
    }

    // lightweight-charts requires ascending marker times.
    marks.sort((a, b) => (a.time < b.time ? -1 : a.time > b.time ? 1 : 0));
    markers.setMarkers(marks);
  };

  const detach = () => {
    for (const line of priceLines) series.removePriceLine(line);
    priceLines = [];
    markers.setMarkers([]);
  };

  return { update, detach };
}
