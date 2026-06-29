import { LineSeries } from 'lightweight-charts';
import CandleChart from './CandleChart';
import { buildFullLevelData, colorTimeframeCandles, finiteNumber } from './chartGeometry';

// The big, interactive weekly/monthly chart behind the modal's D/W/M interval
// tabs. It's the SAME Trend+Box read the daily engine does, one and two
// timeframes up ("all relative and derivative"): candles are resampled on the
// backend (output/dashboard.py) from the full daily history; the blue rails are
// the higher-timeframe consolidation box when one is in view; the caption is the
// plain-language structural read. Styled to match the daily chart
// (useScreenerModalChart) so switching timeframes feels like one TradingView pane.

const chartOptions = (width, height) => ({
  width,
  height,
  layout: {
    background: { type: 'solid', color: '#171922' },
    textColor: '#8b949e',
    fontFamily: "'JetBrains Mono', monospace",
    fontSize: 12,
  },
  grid: {
    vertLines: { color: 'rgba(70, 77, 98, 0.18)' },
    horzLines: { color: 'rgba(70, 77, 98, 0.18)' },
  },
  crosshair: { mode: 1 },
  rightPriceScale: { borderColor: '#2f3447', scaleMargins: { top: 0.06, bottom: 0.16 }, autoScale: true },
  timeScale: { borderColor: '#2f3447', timeVisible: true, fixLeftEdge: false, fixRightEdge: false },
  handleScroll: true,
  handleScale: true,
});

const levelOptions = {
  color: '#2457b8',
  lineWidth: 2,
  crosshairMarkerVisible: false,
  lastValueVisible: false,
  priceLineVisible: false,
};

export default function TimeframeMainChart({ candles, volumes, box, label }) {
  const boxR = box?.r;
  const boxS = box?.s;
  const boxStart = box?.start_date;
  const limbStart = box?.limb_start_date;
  const limbEnd = box?.limb_end_date;
  const lpsStart = box?.lps_start_date;
  const lpsEnd = box?.lps_end_date;

  // Colour the structure candles exactly like the daily chart: base-limb swing
  // grey, the right-side LPS span gold. Dates come from htf.chart_box; bars
  // outside both spans keep the default bar colour.
  const coloredCandles = colorTimeframeCandles(candles || [], { limbStart, limbEnd, lpsStart, lpsEnd });

  const onReady = (chart) => {
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
      chart.addSeries(LineSeries, levelOptions).setData(buildFullLevelData(railBars, r));
      chart.addSeries(LineSeries, levelOptions).setData(buildFullLevelData(railBars, s));
      chart.addSeries(LineSeries, {
        ...levelOptions,
        color: 'rgba(139, 148, 158, 0.45)',
        lineWidth: 1,
        lineStyle: 2,
      }).setData(buildFullLevelData(railBars, (r + s) / 2));
    }

    // Bounded recent window keeps weekly/monthly bars at a faithful per-bar
    // width (fitContent on a long resampled series stretches few bars across the
    // wide pane — the most distorted path). Fall back to fitContent when the box
    // origin predates the recent window, so the rails never start off-screen-left.
    const n = cand.length;
    const show = label === 'WEEKLY' ? 160 : 120;
    const viewFrom = Math.max(0, n - show);
    if (boxStart) {
      const anchor = cand.findIndex((candle) => candle.time >= boxStart);
      if (anchor >= 0 && anchor < viewFrom) {
        chart.timeScale().fitContent();
        return;
      }
    }
    chart.timeScale().setVisibleLogicalRange({ from: viewFrom, to: n - 1 });
  };

  if (!candles?.length) {
    return (
      <div style={{ alignItems: 'center', color: 'var(--text-faint)', display: 'flex', fontSize: 12, height: '100%', justifyContent: 'center' }}>
        No {label?.toLowerCase()} data yet (needs more history)
      </div>
    );
  }

  return (
    <div className="screener-modal-chart" style={{ height: '100%', minHeight: 0, position: 'relative' }}>
      <CandleChart
        spec={{
          chartOptions: (container) =>
            chartOptions(container.clientWidth || 600, container.clientHeight || 360),
          candles: coloredCandles,
          volumes,
          showVolume: !!volumes?.length,
          volumeScaleTop: 0.84,
          showSma: true,
          onReady,
          onResize: (chart, container) =>
            chart.applyOptions({ width: container.clientWidth, height: container.clientHeight }),
          resizeDelayMs: 100,
          onError: (err) => console.error('[TimeframeMainChart] init failed:', err),
          deps: [candles, volumes, boxR, boxS, boxStart, limbStart, limbEnd, lpsStart, lpsEnd],
        }}
        candles={candles}
        style={{ height: '100%', position: 'relative' }}
        errorFallback={(
          <div style={{ alignItems: 'center', color: 'var(--text-muted)', display: 'flex', fontSize: 12, height: '100%', justifyContent: 'center' }}>
            Chart unavailable
          </div>
        )}
      />
    </div>
  );
}
