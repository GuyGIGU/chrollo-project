import { createSeriesMarkers } from 'lightweight-charts';
import { CHART_COLORS } from './chartTheme';

// Draft renderer for the calibration marking layer (Task 11) — deliberately
// SEPARATE from chartRails.addBoxRails: that module draws the ENGINE's
// elected structure once per chart build; this one draws the OPERATOR's
// in-progress draft and is RETAINED — attached once in onReady, then updated
// per draft edit without rebuilding the chart (zoom and pan survive every
// placement click).
//
// Color doctrine (Task 13): a FRESH draft renders in mythril (the ACTIVE
// color — "you are acting on this"); a COMMITTED mark loaded for correction
// renders in the reserved operator hue, so the eye always knows whether it
// is looking at saved ground truth or work in flight.
const EVENT_TAG = { phase_c: 'C', lps: 'L', spring_test: 'T' };

export function attachCalibrationDraw(series) {
  let priceLines = [];
  const markers = createSeriesMarkers(series, []);

  const update = (draft, spanAnchor, committed = false) => {
    const DRAWING = committed ? CHART_COLORS.operator : CHART_COLORS.marking;
    for (const line of priceLines) series.removePriceLine(line);
    priceLines = [];
    const railStyle = {
      color: DRAWING, lineWidth: 1, lineStyle: 0, axisLabelVisible: true,
    };
    if (draft.resistance != null) {
      priceLines.push(series.createPriceLine(
        { ...railStyle, price: draft.resistance, title: 'R' }));
    }
    if (draft.support != null) {
      priceLines.push(series.createPriceLine(
        { ...railStyle, price: draft.support, title: 'S' }));
    }

    const marks = [];
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
