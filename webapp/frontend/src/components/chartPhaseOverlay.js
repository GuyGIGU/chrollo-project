import { PHASE_NAMES } from './wireVocabulary';

const TOKEN_FALLBACKS = {
  '--accent-blue': '#5B8AFF',
  '--accent-pink': '#E07AA0',
  '--accent-purple': '#9B70F7',
  '--accent-yellow': '#D4B85A',
  '--border-strong': '#3B4159',
  '--text-faint': '#6C7488',
};

const REGION_DEFS = {
  a: { label: 'A', name: PHASE_NAMES.a, detail: 'Initial swing setting support/resistance', token: '--text-faint' },
  b: { label: 'B', name: PHASE_NAMES.b, detail: 'Two-sided range work', token: '--accent-purple' },
  c: { label: 'C', name: PHASE_NAMES.c, detail: 'Support shakeout or test', token: '--accent-pink' },
  d: { label: 'D', name: PHASE_NAMES.d, detail: 'Right-side tightening range', token: '--accent-blue' },
  lps: { label: 'LPS', name: PHASE_NAMES.lps, detail: 'Last support-test zone', token: '--accent-yellow' },
};

const PHASE_A_MAX_BARS = 16;
const LPS_OLDEST_COLOR = '#8A6A22';
const LPS_LATEST_COLOR = '#F6D86B';

const dateKey = (value) => (typeof value === 'string' ? value.slice(0, 10) : null);

const finiteNumber = (value) => {
  if (value == null || value === '') return null;
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

const indexOnOrAfter = (candles, rawDate) => {
  const target = dateKey(rawDate);
  if (!target) return null;
  const firstDate = candleDate(candles[0]);
  const lastDate = candleDate(candles[candles.length - 1]);
  if (!firstDate || !lastDate || target < firstDate || target > lastDate) return null;

  const index = candles.findIndex((candle) => candleDate(candle) >= target);
  return index >= 0 ? index : null;
};

const clamp = (value, min, max) => Math.max(min, Math.min(max, value));

const setupEndIndex = (data, candles) => {
  const forwardBars = Math.max(0, Math.trunc(finiteNumber(data?.forward_bars) ?? 0));
  return clamp(candles.length - 1 - forwardBars, 0, candles.length - 1);
};

const setupBoxRange = (data) => {
  const support = finiteNumber(data?.S ?? data?._S);
  const resistance = finiteNumber(data?.R ?? data?._R);
  if (support == null || resistance == null) return null;
  return {
    high: Math.max(support, resistance),
    low: Math.min(support, resistance),
  };
};

const parsePhaseDEvidence = (data) => {
  const raw = data?.phase_d_evidence_json ?? data?.phase_d_evidence;
  if (!raw) return null;
  if (typeof raw === 'object') return raw;
  if (typeof raw !== 'string') return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
};

const PHASE_D_SOURCE_DETAILS = {
  support_tests: 'Support-test cluster',
  sos_reclaim: 'Sign-of-strength reclaim',
  rising_support: 'Rising support',
  inner_box: 'Inner tightening range',
  v_tip: 'Recovered late-base low',
  lps: 'LPS support shelf',
};

const phaseDSourceDetail = (source) => (
  PHASE_D_SOURCE_DETAILS[source] || 'Right-side tightening range'
);

const phaseDSignalLabels = (signals) => {
  if (!Array.isArray(signals)) return [];
  const seen = new Set();
  const labels = [];
  for (const signal of signals) {
    const source = signal?.source;
    if (!source || seen.has(source)) continue;
    seen.add(source);
    labels.push(phaseDSourceDetail(source));
  }
  return labels;
};

const phaseDMetadata = (data) => {
  // The spring recovery only FLOORS Phase D (it ends Phase C); the boundary
  // source is the earliest right-side evidence after it, with the LPS as the
  // mandatory fallback/gate. There is no 'spring' source.
  const evidence = parsePhaseDEvidence(data);
  const source = evidence?.selected?.source || data?.bin_d_boundary_source;
  const signalLabels = phaseDSignalLabels(evidence?.signals);
  return {
    detail: phaseDSourceDetail(source),
    evidenceSignals: signalLabels,
    evidenceSource: source || null,
    evidenceSummary: signalLabels.length ? signalLabels.join(', ') : null,
  };
};

const phaseCDetail = (data) => {
  if (data?.bin_c_type === 'SPRING') return 'Undercut and recovery';
  return 'Support shakeout or test';
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

const priceRangeForRegion = (data, candles, region) => {
  if (region.low != null && region.high != null) {
    return {
      high: Math.max(region.low, region.high),
      low: Math.min(region.low, region.high),
    };
  }

  if (region.range === 'setupBox') {
    return setupBoxRange(data) ?? priceRangeForBars(candles, region.startIndex, region.endIndex);
  }

  return priceRangeForBars(candles, region.startIndex, region.endIndex);
};

const phaseIndexes = (data, candles) => ({
  phaseAStart: indexOnOrAfter(candles, data?._phase_a_start_date),
  phaseAEnd: indexOnOrAfter(candles, data?._phase_a_end_date),
  phaseBStart: indexOnOrAfter(candles, data?._phase_b_start_date),
  phaseDStart: indexOnOrAfter(candles, data?._phase_d_start_date),
  lpsZoneEnd: indexOnOrAfter(candles, data?._lps_zone_end_date),
  lpsZoneStart: indexOnOrAfter(candles, data?._lps_zone_start_date),
});

const buildRegion = (key, candles, startIndex, endIndex, extra = {}) => {
  if (startIndex == null || endIndex == null) return null;
  const lastIndex = candles.length - 1;
  const start = clamp(startIndex, 0, lastIndex);
  const end = clamp(endIndex, 0, lastIndex);
  if (end < start) return null;

  const def = REGION_DEFS[key];
  const id = extra.id || key;
  return {
    ...def,
    ...extra,
    endIndex: end,
    id,
    key,
    startIndex: start,
  };
};

// LPS regions dedupe by TIME OVERLAP, not exact bounds. The live screener's
// "active" LPS zone is almost always the most-recent support test re-emitted
// with very slightly different rounded prices, so an exact-key check let the
// same physical zone draw twice ("LPS shows twice on one zone"). Any LPS whose
// bar-span intersects one already added is the same zone — skip it.
const addLpsRegion = (regions, candles, spans, startDate, endDate, lowValue, highValue, extra = {}) => {
  const startIndex = indexOnOrAfter(candles, startDate);
  const endIndex = indexOnOrAfter(candles, endDate);
  const low = finiteNumber(lowValue);
  const high = finiteNumber(highValue);
  if (startIndex == null || endIndex == null || low == null || high == null) return;

  const lo = Math.min(startIndex, endIndex);
  const hi = Math.max(startIndex, endIndex);
  for (const [spanLo, spanHi] of spans) {
    if (lo <= spanHi && hi >= spanLo) return;
  }
  spans.push([lo, hi]);

  const region = buildRegion('lps', candles, startIndex, endIndex, {
    high,
    low,
    ...extra,
  });
  if (region) regions.push(region);
};

export const buildPhaseRegions = (data) => {
  const candles = data?.candles || [];
  if (candles.length === 0) return [];

  const indexes = phaseIndexes(data, candles);
  const baseEnd = setupEndIndex(data, candles);
  const regions = [];

  // Phase A — the range's own root-swing pair: the bars that establish R and S
  // (r_anchor / s_anchor — the boundary-responsible bars the screener already
  // identifies and colors on the card). This fuses the vertical bin layer with
  // the box's boundary detection: Phase A IS the swing that worked the rails.
  // Falls back to the backend climax→reaction dates only if the anchors are
  // missing.
  const baseLen = Math.max(0, Math.trunc(finiteNumber(data?.base_len) ?? 0));
  const rAnchor = finiteNumber(data?.r_anchor);
  const sAnchor = finiteNumber(data?.s_anchor);
  if (rAnchor != null && sAnchor != null && baseLen > 0) {
    const baseStart = baseEnd - baseLen + 1;
    const rBar = baseStart + rAnchor;
    const sBar = baseStart + sAnchor;
    // Left edge pinned to the box start: with the engine's shared-rail
    // back-extension the box can open BEFORE the anchor pair, and the A band
    // must keep leading into Phase B rather than float inside it. (Without the
    // extension min(rBar, sBar) === baseStart, so this changes nothing.)
    const region = buildRegion('a', candles, Math.min(rBar, sBar, baseStart), Math.max(rBar, sBar));
    if (region) regions.push(region);
  } else if (indexes.phaseAStart != null) {
    const fallbackEnd = indexes.phaseBStart != null
      ? Math.min(indexes.phaseBStart - 1, indexes.phaseAStart + PHASE_A_MAX_BARS - 1)
      : indexes.phaseAStart + PHASE_A_MAX_BARS - 1;
    const phaseAEnd = indexes.phaseAEnd ?? fallbackEnd;
    const region = buildRegion('a', candles, indexes.phaseAStart, phaseAEnd);
    if (region) regions.push(region);
  }
  if (indexes.phaseBStart != null) {
    const region = buildRegion('b', candles, indexes.phaseBStart, baseEnd, { range: 'setupBox' });
    if (region) regions.push(region);
  }
  // Phase C — the measured spring. A spring is a 0-1 bar undercut-and-recover, so
  // a single-bar marker reads as "nothing happened". Draw a band from the spring
  // low up to support: the band's HEIGHT is the undercut depth, so the shakeout
  // stays legible even when it spans one bar. Driven by the bin_c measurement
  // (which carries the recovery span) rather than the bare scope marker.
  if (data?.bin_c_present && data?.bin_c_event_date) {
    const eventIndex = indexOnOrAfter(candles, data.bin_c_event_date);
    if (eventIndex != null) {
      const recoveryBars = Math.max(0, Math.trunc(finiteNumber(data.bin_c_recovery_bars) ?? 0));
      const endIndex = clamp(eventIndex + recoveryBars, eventIndex, candles.length - 1);
      const support = finiteNumber(data.S ?? data._S);
      const springRange = priceRangeForBars(candles, eventIndex, endIndex);
      const extra = { detail: phaseCDetail(data) };
      if (springRange && support != null && springRange.low < support) {
        extra.low = springRange.low;
        extra.high = support;
      }
      const region = buildRegion('c', candles, eventIndex, endIndex, extra);
      if (region) regions.push(region);
    }
  }
  if (indexes.phaseDStart != null) {
    const region = buildRegion('d', candles, indexes.phaseDStart, baseEnd, {
      ...phaseDMetadata(data),
      range: 'setupBox',
    });
    if (region) regions.push(region);
  }
  // One chip per physical LPS zone. Historical support tests carry the richer
  // labels, so add them first; the active zone is then skipped whenever it
  // overlaps one (it almost always does — it IS the most recent test).
  const lpsSpans = [];
  for (const [testIndex, test] of (data?.lps_tests || []).entries()) {
    addLpsRegion(
      regions,
      candles,
      lpsSpans,
      test.start_date,
      test.end_date,
      test.low,
      test.high,
      {
        detail: test.zone_type === 'UNDERCUT_S' ? 'Support undercut and test' : 'Support test',
        id: `lps:${test.start_date || test.start_index}:${test.end_date || test.end_index}:${testIndex}`,
      },
    );
  }
  addLpsRegion(
    regions,
    candles,
    lpsSpans,
    data?._lps_zone_start_date,
    data?._lps_zone_end_date,
    data?._lps_zone_low,
    data?._lps_zone_high,
    { detail: 'Active support-test zone', id: 'lps:active' },
  );
  applyLpsSequenceColors(regions);

  return regions;
};

// Paint LPS candles from the SAME phase-region read the overlay uses, so every
// surface (screener mini card + modal) colors LPS zones with the identical
// chronological gradient (oldest brown -> latest gold) instead of one flat tone.
// `fallbackColor` is the flat tint used ONLY when no LPS *region* resolves (dense
// mini cards pass a muted gold, the modal passes full gold): it then falls back to
// the lps_offset window, preserving the pre-unification behavior. Mutates the
// passed candle array in place (callers pass a clone).
export const colorLpsCandles = (candles, data, fallbackColor) => {
  let colored = false;
  const lpsRegions = buildPhaseRegions(data).filter((region) => region.key === 'lps');
  for (const region of lpsRegions) {
    for (let index = region.startIndex; index <= region.endIndex; index += 1) {
      if (index >= 0 && index < candles.length) {
        candles[index].color = region.color || fallbackColor;
        colored = true;
      }
    }
  }
  if (colored) return candles;

  // No resolved LPS region (e.g. tests missing price bounds) — flat-paint the
  // active lps_offset window, the same last-resort both sites used before.
  if (!(data?.lps_len > 0) || data?.lps_offset === undefined) return candles;
  const baseEnd = setupEndIndex(data, candles);
  const lpsEnd = baseEnd - data.lps_offset;
  const lpsStart = Math.max(0, lpsEnd - data.lps_len + 1);
  for (let index = lpsStart; index <= lpsEnd; index += 1) {
    if (index >= 0 && index < candles.length) candles[index].color = fallbackColor;
  }
  return candles;
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

const interpolateHexColor = (from, to, ratio) => {
  const fromHex = from.replace('#', '');
  const toHex = to.replace('#', '');
  const t = clamp(ratio, 0, 1);
  const channel = (offset) => {
    const start = parseInt(fromHex.slice(offset, offset + 2), 16);
    const end = parseInt(toHex.slice(offset, offset + 2), 16);
    return Math.round(start + (end - start) * t).toString(16).padStart(2, '0');
  };
  return `#${channel(0)}${channel(2)}${channel(4)}`;
};

const applyLpsSequenceColors = (regions) => {
  const lpsRegions = regions
    .filter((region) => region.key === 'lps')
    .sort((a, b) => a.startIndex - b.startIndex || a.endIndex - b.endIndex);

  const last = lpsRegions.length - 1;
  lpsRegions.forEach((region, index) => {
    const ratio = last <= 0 ? 1 : index / last;
    region.color = interpolateHexColor(LPS_OLDEST_COLOR, LPS_LATEST_COLOR, ratio);
    region.detail = index === last ? 'Latest support-test zone' : `Earlier support-test zone ${index + 1}`;
    region.lpsSequenceIndex = index;
    region.lpsSequenceCount = lpsRegions.length;
  });
};

const styledRegions = (data, container) =>
  buildPhaseRegions(data).map((region) => {
    const color = region.color || tokenColor(container, region.token);
    return {
      ...region,
      fillStyle: colorToRgba(color, region.key === 'lps' ? 0.08 : 0.045),
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
      context.save();
      for (const region of this.drawData) {
        const { height, left, strokeStyle, top, width, fillStyle } = region;
        context.fillStyle = fillStyle;
        context.strokeStyle = strokeStyle;
        context.lineWidth = 1;
        context.fillRect(left, top, width, height);
        context.strokeRect(left + 0.5, top + 0.5, Math.max(1, width - 1), Math.max(1, height - 1));
      }
      context.restore();
    });
  }
}

class PhaseRegionPaneView {
  constructor(source) {
    this.drawData = null;
    this.source = source;
  }

  update() {
    this.drawData = this.source.calculateDrawData();
  }

  zOrder() {
    return 'bottom';
  }

  renderer() {
    return this.drawData ? new PhaseRegionRenderer(this.drawData) : null;
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
    this.handleTimeScaleChange = () => {
      this.updateAllViews();
      this.requestUpdate?.();
    };
  }

  attached({ chart, requestUpdate, series }) {
    this.chart = chart;
    this.requestUpdate = requestUpdate;
    this.series = series;
    this.chart.timeScale().subscribeVisibleLogicalRangeChange(this.handleTimeScaleChange);
    this.updateAllViews();
  }

  detached() {
    this.chart?.timeScale().unsubscribeVisibleLogicalRangeChange(this.handleTimeScaleChange);
  }

  updateAllViews() {
    this.view.update();
  }

  paneViews() {
    return this.views;
  }

  setActiveRegion(activeRegion) {
    this.activeRegion = activeRegion;
    this.updateAllViews();
    this.requestUpdate?.();
  }

  barWidth(index) {
    const timeScale = this.chart.timeScale();
    const current = timeScale.logicalToCoordinate(index);
    const next = timeScale.logicalToCoordinate(index + 1);
    if (current != null && next != null) return Math.max(2, Math.abs(next - current));

    const previous = timeScale.logicalToCoordinate(index - 1);
    if (current != null && previous != null) return Math.max(2, Math.abs(current - previous));

    return 6;
  }

  xForBar(index) {
    const candle = this.data?.candles?.[index];
    const timeCoordinate = candle ? this.chart.timeScale().timeToCoordinate(candle.time) : null;
    return timeCoordinate ?? this.chart.timeScale().logicalToCoordinate(index);
  }

  calculateDrawData() {
    if (!this.activeRegion || !this.chart || !this.series) return null;

    const candles = this.data?.candles || [];
    const paneWidth = this.chart.timeScale().width();
    const paneHeight = Math.max(0, this.container?.clientHeight ?? 0);
    const drawRegions = this.regions
      .filter((item) => item.id === this.activeRegion || item.key === this.activeRegion)
      .map((region) => {
        const priceRange = priceRangeForRegion(this.data, candles, region);
        if (!priceRange) return null;

        const spacing = this.barWidth(region.startIndex);
        const x1 = this.xForBar(region.startIndex);
        const x2 = this.xForBar(region.endIndex);
        const yLow = this.series.priceToCoordinate(priceRange.low);
        const yHigh = this.series.priceToCoordinate(priceRange.high);
        if (x1 == null || x2 == null || yLow == null || yHigh == null) return null;

        const left = Math.round(clamp(Math.min(x1, x2) - spacing * 0.45, 0, paneWidth));
        const right = Math.round(clamp(Math.max(x1, x2) + spacing * 0.45, 0, paneWidth));
        const top = Math.round(clamp(Math.min(yLow, yHigh), 0, paneHeight));
        const bottom = Math.round(clamp(Math.max(yLow, yHigh), 0, paneHeight));
        if (right - left < 2 || bottom - top < 2) return null;

        return {
          fillStyle: region.fillStyle,
          height: bottom - top,
          left,
          strokeStyle: region.strokeStyle,
          top,
          width: right - left,
        };
      })
      .filter(Boolean);

    return drawRegions.length ? drawRegions : null;
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
