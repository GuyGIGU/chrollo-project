// The lens charts' zoom buttons (Fri 17/10/2026, his "the charts need to be interactable, not just
// drag but also zoom in, out, reset and adjust data to fit on screen"): pure math over
// lightweight-charts' logical range, so a node test can pin it. The RIGHT edge stays where it is:
// the newest bars are what he zooms around, as the time-axis drag does. (The wheel over a pane
// zooms through the chart's own handleScale, around the pointer, as on TradingView.) Pure
// literals, no lightweight-charts import.

export const MIN_SPAN_BARS = 12;
export const ZOOM_IN = 0.8;
export const ZOOM_OUT = 1.25;

export const zoomedRange = (range, factor, minSpan = MIN_SPAN_BARS) => {
  if (!range || !Number.isFinite(range.from) || !Number.isFinite(range.to)) return null;
  const span = Math.max(minSpan, (range.to - range.from) * factor);
  return { from: range.to - span, to: range.to };
};
