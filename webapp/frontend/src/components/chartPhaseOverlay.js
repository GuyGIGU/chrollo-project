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

const xForIndex = (chart, index) => {
  if (!Number.isFinite(index) || !chart.timeScale().logicalToCoordinate) return null;
  const x = chart.timeScale().logicalToCoordinate(index);
  return Number.isFinite(x) ? x : null;
};

const clamp = (value, min, max) => Math.max(min, Math.min(max, value));

const appendDiv = (parent, className, style = {}, title = '') => {
  const element = document.createElement('div');
  element.className = className;
  if (title) element.title = title;
  Object.assign(element.style, style);
  parent.appendChild(element);
  return element;
};

const clearOverlay = (overlay) => {
  while (overlay.firstChild) overlay.removeChild(overlay.firstChild);
};

const phaseData = (data, candles) => {
  const phaseAStart = firstIndexOnOrAfter(candles, data?._phase_a_start_date);
  const phaseBStart = firstIndexOnOrAfter(candles, data?._phase_b_start_date);
  const phaseDStart = firstIndexOnOrAfter(candles, data?._phase_d_start_date);
  const phaseCEvent = firstIndexOnOrAfter(candles, data?._phase_c_event_date);
  const lpsZoneStart = firstIndexOnOrAfter(candles, data?._lps_zone_start_date);
  const lpsZoneEnd = firstIndexOnOrAfter(candles, data?._lps_zone_end_date);

  return {
    phaseAStart,
    phaseBStart,
    phaseDStart,
    phaseCEvent,
    lpsZoneEnd,
    lpsZoneStart,
    lpsLow: finiteNumber(data?._lps_zone_low),
    lpsHigh: finiteNumber(data?._lps_zone_high),
  };
};

const renderVerticalBand = (overlay, chart, startIndex, endIndex, className, title) => {
  const width = overlay.clientWidth;
  const x1 = xForIndex(chart, startIndex);
  const x2 = xForIndex(chart, endIndex);
  if (x1 == null || x2 == null) return false;

  const left = clamp(Math.min(x1, x2), 0, width);
  const right = clamp(Math.max(x1, x2), 0, width);
  if (right <= 0 || left >= width || right - left < 1) return false;

  appendDiv(overlay, className, {
    bottom: '0',
    left: `${left}px`,
    top: '0',
    width: `${Math.max(2, right - left)}px`,
  }, title);
  return true;
};

const renderLpsZone = (overlay, chart, candleSeries, startIndex, endIndex, low, high) => {
  if (low == null || high == null || startIndex == null || endIndex == null) return;
  const yLow = candleSeries.priceToCoordinate(Math.min(low, high));
  const yHigh = candleSeries.priceToCoordinate(Math.max(low, high));
  const x1 = xForIndex(chart, startIndex);
  const x2 = xForIndex(chart, endIndex);
  if (yLow == null || yHigh == null || x1 == null || x2 == null) return;

  const width = overlay.clientWidth;
  const height = overlay.clientHeight;
  const left = clamp(Math.min(x1, x2), 0, width);
  const right = clamp(Math.max(x1, x2), 0, width);
  const top = clamp(Math.min(yLow, yHigh), 0, height);
  const bottom = clamp(Math.max(yLow, yHigh), 0, height);
  if (right - left < 1 || bottom - top < 1) return;

  appendDiv(overlay, 'chart-phase-lps-zone', {
    height: `${Math.max(2, bottom - top)}px`,
    left: `${left}px`,
    top: `${top}px`,
    width: `${Math.max(2, right - left)}px`,
  }, 'LPS support zone');
};

const renderPhaseCMarker = (overlay, chart, candleSeries, candles, index) => {
  if (index == null) return;
  const x = xForIndex(chart, index);
  if (x == null || x < 0 || x > overlay.clientWidth) return;

  const candle = candles[index];
  const price = finiteNumber(candle?.low) ?? finiteNumber(candle?.close);
  const priceY = price == null ? null : candleSeries.priceToCoordinate(price);
  const y = priceY == null ? overlay.clientHeight * 0.58 : clamp(priceY, 10, overlay.clientHeight - 10);

  appendDiv(overlay, 'chart-phase-c-line', {
    left: `${x}px`,
  }, 'Phase C spring/shakeout');
  appendDiv(overlay, 'chart-phase-c-marker', {
    left: `${x}px`,
    top: `${y}px`,
  }, 'Phase C spring/shakeout');
};

const renderLegend = (overlay) => {
  const legend = appendDiv(overlay, 'chart-phase-legend');
  legend.innerHTML = `
    <span><i class="phase-a"></i>A</span>
    <span><i class="phase-b"></i>B</span>
    <span><i class="phase-d"></i>D</span>
    <span><i class="lps-zone"></i>LPS</span>
  `;
};

export const attachPhaseOverlay = ({ candleSeries, chart, compact = false, container, data }) => {
  const candles = data?.candles || [];
  if (!container || !chart || !candleSeries || candles.length === 0) return () => {};

  const overlay = appendDiv(container, 'chart-phase-overlay');
  const phases = phaseData(data, candles);
  const lastIndex = candles.length - 1;
  let animationFrame = null;

  const update = () => {
    clearOverlay(overlay);
    const phaseA = phases.phaseAStart != null && phases.phaseBStart != null
      ? renderVerticalBand(overlay, chart, phases.phaseAStart, phases.phaseBStart, 'chart-phase-band chart-phase-a', 'Phase A')
      : false;
    const phaseB = phases.phaseBStart != null && phases.phaseDStart != null
      ? renderVerticalBand(overlay, chart, phases.phaseBStart, phases.phaseDStart, 'chart-phase-band chart-phase-b', 'Phase B')
      : false;
    const phaseD = phases.phaseDStart != null
      ? renderVerticalBand(overlay, chart, phases.phaseDStart, lastIndex + 0.7, 'chart-phase-band chart-phase-d', 'Phase D')
      : false;

    if (phaseD && phases.lpsZoneStart != null && phases.lpsZoneEnd != null) {
      renderLpsZone(overlay, chart, candleSeries, phases.lpsZoneStart, phases.lpsZoneEnd + 0.7, phases.lpsLow, phases.lpsHigh);
    }
    renderPhaseCMarker(overlay, chart, candleSeries, candles, phases.phaseCEvent);
    if (!compact && (phaseA || phaseB || phaseD)) renderLegend(overlay);
  };

  const scheduleUpdate = () => {
    if (animationFrame != null) cancelAnimationFrame(animationFrame);
    animationFrame = requestAnimationFrame(update);
  };

  scheduleUpdate();
  const timeScale = chart.timeScale();
  timeScale.subscribeVisibleLogicalRangeChange?.(scheduleUpdate);
  timeScale.subscribeVisibleTimeRangeChange?.(scheduleUpdate);

  const resizeObserver = new ResizeObserver(scheduleUpdate);
  resizeObserver.observe(container);

  return () => {
    if (animationFrame != null) cancelAnimationFrame(animationFrame);
    timeScale.unsubscribeVisibleLogicalRangeChange?.(scheduleUpdate);
    timeScale.unsubscribeVisibleTimeRangeChange?.(scheduleUpdate);
    resizeObserver.disconnect();
    overlay.remove();
  };
};
