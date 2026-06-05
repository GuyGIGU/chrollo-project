const TOKEN_FALLBACKS = {
  '--accent-blue': '#5B8AFF',
  '--accent-pink': '#E07AA0',
  '--accent-purple': '#9B70F7',
  '--accent-yellow': '#D4B85A',
  '--border-strong': '#3B4159',
  '--text-faint': '#6C7488',
};

const REGION_DEFS = {
  a: { label: 'A', name: 'Phase A', detail: 'Climax / automatic rally', token: '--text-faint' },
  b: { label: 'B', name: 'Phase B', detail: 'Equilibrium body', token: '--accent-purple' },
  c: { label: 'C', name: 'Phase C', detail: 'Spring / shakeout', token: '--accent-pink' },
  d: { label: 'D', name: 'Phase D', detail: 'Launchpad', token: '--accent-blue' },
  lps: { label: 'LPS', name: 'LPS', detail: 'Support zone', token: '--accent-yellow' },
};

const dateKey = (value) => (typeof value === 'string' ? value.slice(0, 10) : null);

const finiteNumber = (value) => {
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
};

const candleDate = (candle) => {
  if (!candle?.time) return '';
  if (typeof candle.time === 'string') return candle.time.slice(0, 10);
  if (typeof candle.time === 'object') {
    const month = String(candle.time.month).padStart(2, '0');
    const day = String(candle.time.day).padStart(2, '0');
    return `${candle.time.year}-${month}-${day}`;
  }
  return '';
};

const firstIndexOnOrAfter = (candles, rawDate) => {
  const target = dateKey(rawDate);
  if (!target) return null;
  const index = candles.findIndex((candle) => candleDate(candle) >= target);
  return index >= 0 ? index : null;
};

const clamp = (value, min, max) => Math.max(min, Math.min(max, value));

const setupEndIndex = (data, candles) => {
  const forwardBars = Math.max(0, Math.trunc(finiteNumber(data?.forward_bars) ?? 0));
  return clamp(candles.length - 1 - forwardBars, 0, candles.length - 1);
};

const priceRangeForBars = (candles, startIndex, endIndex) => {
  let low = null;
  let high = null;
  for (let index = startIndex; index <= endIndex; index += 1) {
    const candle = candles[index];
    const values = [
      finiteNumber(candle?.low),
      finiteNumber(candle?.high),
      finiteNumber(candle?.open),
      finiteNumber(candle?.close),
    ].filter((value) => value != null);
    for (const value of values) {
      low = low == null ? value : Math.min(low, value);
      high = high == null ? value : Math.max(high, value);
    }
  }
  return low == null || high == null ? null : { high, low };
};

const phaseIndexes = (data, candles) => ({
  phaseAStart: firstIndexOnOrAfter(candles, data?._phase_a_start_date),
  phaseBStart: firstIndexOnOrAfter(candles, data?._phase_b_start_date),
  phaseCEvent: firstIndexOnOrAfter(candles, data?._phase_c_event_date),
  phaseDStart: firstIndexOnOrAfter(candles, data?._phase_d_start_date),
  lpsZoneEnd: firstIndexOnOrAfter(candles, data?._lps_zone_end_date),
  lpsZoneStart: firstIndexOnOrAfter(candles, data?._lps_zone_start_date),
});

const buildRegion = (key, candles, startIndex, endIndex, extra = {}) => {
  if (startIndex == null || endIndex == null) return null;
  const lastIndex = candles.length - 1;
  const start = clamp(startIndex, 0, lastIndex);
  const end = clamp(endIndex, 0, lastIndex);
  if (end < start) return null;

  const def = REGION_DEFS[key];
  return {
    ...def,
    ...extra,
    endIndex: end,
    key,
    startIndex: start,
  };
};

export const buildPhaseRegions = (data) => {
  const candles = data?.candles || [];
  if (candles.length === 0) return [];

  const indexes = phaseIndexes(data, candles);
  const baseEnd = setupEndIndex(data, candles);
  const regions = [];

  if (indexes.phaseAStart != null && indexes.phaseBStart != null) {
    const region = buildRegion('a', candles, indexes.phaseAStart, indexes.phaseBStart - 1);
    if (region) regions.push(region);
  }
  if (indexes.phaseBStart != null) {
    const region = buildRegion('b', candles, indexes.phaseBStart, baseEnd);
    if (region) regions.push(region);
  }
  if (indexes.phaseCEvent != null) {
    const region = buildRegion('c', candles, indexes.phaseCEvent, indexes.phaseCEvent);
    if (region) regions.push(region);
  }
  if (indexes.phaseDStart != null) {
    const region = buildRegion('d', candles, indexes.phaseDStart, baseEnd);
    if (region) regions.push(region);
  }
  if (indexes.lpsZoneStart != null && indexes.lpsZoneEnd != null) {
    const low = finiteNumber(data?._lps_zone_low);
    const high = finiteNumber(data?._lps_zone_high);
    const region = buildRegion('lps', candles, indexes.lpsZoneStart, indexes.lpsZoneEnd, {
      high,
      low,
    });
    if (region) regions.push(region);
  }

  return regions;
};

const tokenColor = (container, token) => {
  const computed = container ? getComputedStyle(container).getPropertyValue(token).trim() : '';
  return computed || TOKEN_FALLBACKS[token] || TOKEN_FALLBACKS['--border-strong'];
};

const colorToRgba = (color, alpha) => {
  const hex = color.trim().match(/^#?([0-9a-f]{6})$/i)?.[1];
  if (hex) {
    const value = parseInt(hex, 16);
    return `rgba(${(value >> 16) & 255}, ${(value >> 8) & 255}, ${value & 255}, ${alpha})`;
  }

  const rgb = color.trim().match(/^rgba?\((\d+),\s*(\d+),\s*(\d+)/i);
  if (rgb) return `rgba(${rgb[1]}, ${rgb[2]}, ${rgb[3]}, ${alpha})`;
  return color;
};

const styledRegions = (data, container) =>
  buildPhaseRegions(data).map((region) => {
    const color = tokenColor(container, region.token);
    return {
      ...region,
      fillStyle: colorToRgba(color, region.key === 'lps' ? 0.10 : 0.08),
      strokeStyle: colorToRgba(color, region.key === 'd' ? 0.72 : 0.56),
    };
  });

class PhaseRegionRenderer {
  constructor(drawData) {
    this.drawData = drawData;
  }

  draw() {}

  drawBackground(target) {
    target.useMediaCoordinateSpace(({ context }) => {
      const { height, left, strokeStyle, top, width, fillStyle } = this.drawData;
      context.save();
      context.fillStyle = fillStyle;
      context.strokeStyle = strokeStyle;
      context.lineWidth = 1;
      context.fillRect(left, top, width, height);
      context.strokeRect(left + 0.5, top + 0.5, Math.max(1, width - 1), Math.max(1, height - 1));
      context.restore();
    });
  }
}

class PhaseRegionPaneView {
  constructor(source) {
    this.source = source;
  }

  zOrder() {
    return 'bottom';
  }

  renderer() {
    const drawData = this.source.drawData();
    return drawData ? new PhaseRegionRenderer(drawData) : null;
  }
}

class PhaseRegionPrimitive {
  constructor({ activeRegion, chart, container, data, series }) {
    this.activeRegion = activeRegion;
    this.chart = chart;
    this.container = container;
    this.data = data;
    this.regions = styledRegions(data, container);
    this.series = series;
    this.view = new PhaseRegionPaneView(this);
    this.views = [this.view];
  }

  attached({ chart, requestUpdate, series }) {
    this.chart = chart;
    this.requestUpdate = requestUpdate;
    this.series = series;
  }

  paneViews() {
    return this.views;
  }

  setActiveRegion(activeRegion) {
    this.activeRegion = activeRegion;
    this.requestUpdate?.();
  }

  drawData() {
    if (!this.activeRegion || !this.chart || !this.series) return null;

    const candles = this.data?.candles || [];
    const region = this.regions.find((item) => item.key === this.activeRegion);
    if (!region) return null;

    const barRange = priceRangeForBars(candles, region.startIndex, region.endIndex);
    const low = region.low ?? barRange?.low;
    const high = region.high ?? barRange?.high;
    if (low == null || high == null) return null;

    const x1 = this.chart.timeScale().logicalToCoordinate(region.startIndex);
    const x2 = this.chart.timeScale().logicalToCoordinate(region.endIndex + 0.7);
    const yLow = this.series.priceToCoordinate(Math.min(low, high));
    const yHigh = this.series.priceToCoordinate(Math.max(low, high));
    if (x1 == null || x2 == null || yLow == null || yHigh == null) return null;

    const left = Math.round(Math.min(x1, x2));
    const right = Math.round(Math.max(x1, x2));
    const top = Math.round(Math.min(yLow, yHigh));
    const bottom = Math.round(Math.max(yLow, yHigh));
    if (right - left < 2 || bottom - top < 2) return null;

    return {
      fillStyle: region.fillStyle,
      height: bottom - top,
      left,
      strokeStyle: region.strokeStyle,
      top,
      width: right - left,
    };
  }
}

export const attachPhaseOverlay = ({ activeRegion = null, candleSeries, chart, container, data }) => {
  if (!chart || !candleSeries || !data?.candles?.length) {
    return { remove: () => {}, setActiveRegion: () => {} };
  }

  const primitive = new PhaseRegionPrimitive({
    activeRegion,
    chart,
    container,
    data,
    series: candleSeries,
  });
  candleSeries.attachPrimitive(primitive);

  return {
    remove: () => candleSeries.detachPrimitive(primitive),
    setActiveRegion: (region) => primitive.setActiveRegion(region),
  };
};
