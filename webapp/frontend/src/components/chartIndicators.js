export const hl2Sma20Options = {
  color: 'rgba(45, 212, 191, 0.72)',
  crosshairMarkerVisible: false,
  lastValueVisible: false,
  lineWidth: 1,
  priceLineVisible: false,
};

const finiteNumber = (value) => {
  if (value == null || value === '') return null;
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
};

// Close-based simple moving average for overlay lines (Finviz-style SMA 50/200).
// Mirrors buildHl2SmaData's NaN-safe rolling window, but on close instead of hl2.
export const buildCloseSma = (candles, window = 50) => {
  if (!Array.isArray(candles) || candles.length < window || window <= 0) return [];

  const out = [];
  const queue = [];
  let sum = 0;
  let invalid = 0;

  for (const candle of candles) {
    const close = finiteNumber(candle?.close);
    queue.push(close);
    if (close == null) invalid += 1; else sum += close;

    if (queue.length > window) {
      const removed = queue.shift();
      if (removed == null) invalid -= 1; else sum -= removed;
    }

    if (queue.length === window && invalid === 0 && candle?.time) {
      out.push({ time: candle.time, value: sum / window });
    }
  }

  return out;
};

export const buildHl2SmaData = (candles, window = 20) => {
  if (!Array.isArray(candles) || candles.length < window || window <= 0) return [];

  const out = [];
  const queue = [];
  let sum = 0;
  let invalid = 0;

  for (const candle of candles) {
    const high = finiteNumber(candle?.high);
    const low = finiteNumber(candle?.low);
    const midpoint = high != null && low != null ? (high + low) / 2 : null;

    queue.push(midpoint);
    if (midpoint == null) {
      invalid += 1;
    } else {
      sum += midpoint;
    }

    if (queue.length > window) {
      const removed = queue.shift();
      if (removed == null) {
        invalid -= 1;
      } else {
        sum -= removed;
      }
    }

    if (queue.length === window && invalid === 0 && candle?.time) {
      out.push({ time: candle.time, value: sum / window });
    }
  }

  return out;
};
