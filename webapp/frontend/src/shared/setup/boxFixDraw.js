import { LineSeries, createSeriesMarkers } from 'lightweight-charts';
import { EVENT_TAG } from './boxFixEvents.js';

// Draws one layer of a box fix on the live daily chart (Fri 17 and Sat 18/10/2026): his two lines
// from their day to the chart's edge, and his events, each as a short line over its days at its
// price (a mini as its two lines) with the event's letter as a marker on its first day. Every
// series is returned so the caller can remove the layer without rebuilding the chart (a click
// must never cost his zoom). The in-flight draft wears the calibration red; a SAVED fix wears the
// operator colour (CHART_COLORS.operator, the committed-marks hue), over the reader's read and
// never in its place.
const lineOptions = (color, lineWidth) => ({
  color, lineWidth, lineStyle: 0, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false,
});

const fromDay = (candles, day, price) => {
  const from = candles.findIndex((candle) => candle.time >= day);
  return from < 0 ? [] : candles.slice(from).map((candle) => ({ time: candle.time, value: price }));
};

const overDays = (candles, first, last, price) =>
  candles.filter((candle) => candle.time >= first && candle.time <= last).map((candle) => ({ time: candle.time, value: price }));

const add = (chart, options, points, out) => {
  if (!points.length) return null;
  try {
    const series = chart.addSeries(LineSeries, options);
    series.setData(points);
    out.push(series);
    return series;
  } catch {
    return null;   // a line is decoration: never let it cost the chart
  }
};

// `fix` is { r, rDay, s, sDay, events }: the rails may be absent (an event placed before a line),
// the events empty. Returns the series drawn.
export function drawFixLayer(chart, candles, fix, color, { lastValueVisible = false } = {}) {
  const out = [];
  if (!chart || !candles?.length || !fix) return out;
  for (const [day, price] of [[fix.rDay, fix.r], [fix.sDay, fix.s]]) {
    if (price == null || !day) continue;
    add(chart, { ...lineOptions(color, 2), lastValueVisible }, fromDay(candles, day, price), out);
  }
  for (const event of fix.events || []) {
    const prices = event.kind === 'mini' ? [event.band_high, event.band_low] : [event.price];
    let carrier = null;
    for (const price of prices) {
      if (price == null) continue;
      const series = add(chart, lineOptions(color, 2), overDays(candles, event.first_day, event.last_day, price), out);
      carrier = carrier ?? series;
    }
    if (!carrier) continue;
    try {
      createSeriesMarkers(carrier, [{
        time: event.first_day, position: event.kind === 'upthrust' ? 'aboveBar' : 'belowBar', shape: 'circle', color,
        text: EVENT_TAG[event.kind] ?? '?',
      }]);
    } catch { /* the letter is decoration */ }
  }
  return out;
}

export function removeLayer(chart, series) {
  for (const one of series || []) {
    try { chart?.removeSeries(one); } catch { /* the chart may already be gone */ }
  }
}
