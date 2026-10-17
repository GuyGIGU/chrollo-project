// The lens charts' zoom (Fri 17/10/2026, his "the charts need to be interactable, not just drag
// but also zoom in, out, reset and adjust data to fit on screen"): pure math over
// lightweight-charts' logical range, so the + / − buttons and Ctrl+wheel agree and a node test can
// pin them. The RIGHT edge stays where it is: the newest bars are what he zooms around, as the
// time-axis drag does. Pure literals, no lightweight-charts import.

export const MIN_SPAN_BARS = 12;
export const ZOOM_IN = 0.8;
export const ZOOM_OUT = 1.25;

// One wheel notch is a gentler step than a button press, so a flick of the wheel reads as a nudge.
export const wheelFactor = (deltaY) => (deltaY > 0 ? 1.12 : 1 / 1.12);

export const zoomedRange = (range, factor, minSpan = MIN_SPAN_BARS) => {
  if (!range || !Number.isFinite(range.from) || !Number.isFinite(range.to)) return null;
  const span = Math.max(minSpan, (range.to - range.from) * factor);
  return { from: range.to - span, to: range.to };
};
