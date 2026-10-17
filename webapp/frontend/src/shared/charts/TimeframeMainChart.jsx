import { useRef } from 'react';
import { LineSeries } from 'lightweight-charts';
import CandleChart from './CandleChart';
import ChartZoomControls from './ChartZoomControls';
import { buildFullLevelData, colorTimeframeCandles, finiteNumber } from './chartGeometry';
import { baseChartOptions, lensBarOptions, lensSmaOptions, RAIL_STYLE } from './chartTheme';

// The interactive weekly/monthly chart — the lens's three-pane grid (big or in
// the side column) AND the Watchlist page's stacked M/W panes. It's the SAME
// Trend+Box read the daily engine does, one and two timeframes up ("all
// relative and derivative"): candles are resampled on the backend (the shared
// core/pipeline/market_data/candles builders) from the full daily history; the blue rails
// are the higher-timeframe consolidation box when one is in view (absent on a
// clean candles-only payload). Styled to match the daily chart
// (useDailyStructureChart) so the three panes read as one TradingView layout.
// The preview mode (interactive=false, the W/M cubes) retired Fri 17/10/2026
// with the cubes: every pane is a real chart now, with the zoom cluster.

const chartOptions = (width, height, container) => {
  const base = baseChartOptions('modal', width, height, container);
  return {
    ...base,
    // Container-sized and range-locked, like the daily pane beside it: a UI-scale
    // change or a monitor move re-fits the pane and keeps its framed bars
    // (review 2026-10-02).
    autoSize: true,
    crosshair: { mode: 1 },
    rightPriceScale: { ...base.rightPriceScale, scaleMargins: { top: 0.06, bottom: 0.16 }, autoScale: true },
    timeScale: { ...base.timeScale, timeVisible: true, fixLeftEdge: false, fixRightEdge: false,
                 lockVisibleTimeRangeOnResize: true },
    // The wheel over the pane zooms it, as on TradingView (Fri 17/10/2026); the zoom cluster
    // (ChartZoomControls) and the axis drags scale too; the lens page scrolls from outside the panes.
    handleScroll: { mouseWheel: true, pressedMouseMove: true, horzTouchDrag: true, vertTouchDrag: false },
    handleScale: { mouseWheel: true, pinch: true, axisPressedMouseMove: true, axisDoubleClickReset: true },
  };
};

// The opening window: the newest `show` bars at a faithful per-bar width (fitContent on a long
// resampled series stretches few bars across a wide pane — the most distorted path), unless the
// box was born before that window: then the whole history, so the rails never start off-screen-left.
const DEFAULT_BARS = { WEEKLY: 160, MONTHLY: 120 };
const homeView = (chart, candles, boxStart, show) => {
  const n = candles.length;
  const viewFrom = Math.max(0, n - show);
  if (boxStart) {
    const anchor = candles.findIndex((candle) => candle.time >= boxStart);
    if (anchor >= 0 && anchor < viewFrom) {
      chart.timeScale().fitContent();
      return;
    }
  }
  chart.timeScale().setVisibleLogicalRange({ from: viewFrom, to: n - 1 });
};

// `bars` overrides the opening window (the lens's side column shows fewer, Fri 17/10/2026).
export default function TimeframeMainChart({ candles, volumes, box, label, bars = null }) {
  const chartRef = useRef(null);
  const boxR = box?.r;
  const boxS = box?.s;
  const boxStart = box?.start_date;
  const limbStart = box?.limb_start_date;
  const limbEnd = box?.limb_end_date;
  const lpsStart = box?.lps_start_date;
  const lpsEnd = box?.lps_end_date;
  const show = bars ?? DEFAULT_BARS[label] ?? DEFAULT_BARS.WEEKLY;

  // Colour the structure candles exactly like the daily chart: base-limb swing
  // grey, the right-side LPS span gold. Dates come from htf.chart_box; bars
  // outside both spans keep the default bar colour.
  const coloredCandles = colorTimeframeCandles(candles || [], { limbStart, limbEnd, lpsStart, lpsEnd });

  const onReady = (chart) => {
    chartRef.current = chart;
    const cand = candles || [];
    const r = finiteNumber(boxR);
    const s = finiteNumber(boxS);
    if (cand.length && r != null && s != null) {
      // Anchor the rails to the bars the box is born from (boxStart) — a bounded
      // line exactly like the daily chart, not a full-width rail.
      let from = 0;
      if (boxStart) {
        const found = cand.findIndex((candle) => candle.time >= boxStart);
        from = found < 0 ? 0 : found;
      }
      const railBars = cand.slice(from);
      chart.addSeries(LineSeries, RAIL_STYLE.rail).setData(buildFullLevelData(railBars, r));
      chart.addSeries(LineSeries, RAIL_STYLE.rail).setData(buildFullLevelData(railBars, s));
      chart.addSeries(LineSeries, RAIL_STYLE.mid).setData(buildFullLevelData(railBars, (r + s) / 2));
    }
    homeView(chart, cand, boxStart, show);
    return () => { if (chartRef.current === chart) chartRef.current = null; };
  };

  if (!candles?.length) {
    return (
      <div style={{ alignItems: 'center', color: 'var(--text-faint)', display: 'flex', fontSize: 12, height: '100%', justifyContent: 'center' }}>
        No {label?.toLowerCase()} data yet (needs more history)
      </div>
    );
  }

  return (
    <div style={{ height: '100%', minHeight: 0, position: 'relative' }}>
      <CandleChart
        spec={{
          chartOptions: (container) =>
            chartOptions(container.clientWidth || 600, container.clientHeight || 360, container),
          candles: coloredCandles,
          barOptions: lensBarOptions,
          smaOptions: lensSmaOptions,
          volumes,
          showVolume: !!volumes?.length,
          volumeScaleTop: 0.84,
          showSma: true,
          onReady,
          onError: (err) => console.error('[TimeframeMainChart] init failed:', err),
          deps: [candles, volumes, boxR, boxS, boxStart, limbStart, limbEnd, lpsStart, lpsEnd, show],
        }}
        candles={candles}
        style={{ height: '100%', position: 'relative' }}
        errorFallback={(
          <div style={{ alignItems: 'center', color: 'var(--text-muted)', display: 'flex', fontSize: 12, height: '100%', justifyContent: 'center' }}>
            Chart unavailable
          </div>
        )}
      />
      <ChartZoomControls
        chartRef={chartRef}
        onHome={() => { if (chartRef.current) homeView(chartRef.current, candles, boxStart, show); }}
      />
    </div>
  );
}
