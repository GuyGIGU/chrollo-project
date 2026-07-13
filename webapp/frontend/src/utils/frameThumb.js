// Pure geometry for the ledger frame thumbnail — maps a downsampled close
// series (+ the operator's box) to SVG coordinates. No React, no fetch;
// unit-tested in frameThumb.test.js. The backend pre-downsamples the series
// (frame_store.preview_series), so this only positions points — never a
// per-row read of full candles.

// First session at/after a date, else the last index (the box's right edge is
// the as-of session = the last bar). Series is ascending ISO dates, so a string
// compare is chronological.
export function indexForDate(series, date) {
  for (let i = 0; i < series.length; i += 1) {
    if (series[i].t >= date) return i;
  }
  return series.length - 1;
}

const round = (v) => Math.round(v * 10) / 10;

// preview: { series:[{t,c}], lo, hi }; box: { r, s, boxStart, boxEnd } | null.
// Returns { points, box } in a `width`x`height` viewBox, or null when there is
// nothing to draw. The y-range expands to include the drawn rails so the box
// always fits; x maps by SESSION index (not calendar), so the rails land on the
// bars they were drawn against.
export function thumbGeometry(preview, box, { width = 74, height = 34, pad = 3 } = {}) {
  const series = preview?.series ?? [];
  const n = series.length;
  if (!n) return null;
  let lo = preview.lo;
  let hi = preview.hi;
  if (!Number.isFinite(lo) || !Number.isFinite(hi)) return null;

  const hasBox = Boolean(box) && Number.isFinite(box.r) && Number.isFinite(box.s)
    && box.r > box.s && Boolean(box.boxStart) && Boolean(box.boxEnd);
  if (hasBox) { lo = Math.min(lo, box.s); hi = Math.max(hi, box.r); }

  const span = (hi - lo) || 1;
  lo -= span * 0.08;
  hi += span * 0.08;
  const range = (hi - lo) || 1;
  const iw = width - pad * 2;
  const ih = height - pad * 2;
  const xFor = (i) => pad + (n <= 1 ? iw / 2 : (iw * i) / (n - 1));
  const yFor = (v) => pad + ih * (1 - (v - lo) / range);

  const points = series.map((p, i) => `${round(xFor(i))},${round(yFor(p.c))}`).join(' ');

  let boxGeom = null;
  if (hasBox) {
    const right = width - pad;
    const x = xFor(indexForDate(series, box.boxStart));
    const ry = yFor(box.r);
    const sy = yFor(box.s);
    boxGeom = {
      x: round(x), width: round(right - x),
      ry: round(ry), sy: round(sy), right: round(right),
    };
  }
  return { points, box: boxGeom };
}
