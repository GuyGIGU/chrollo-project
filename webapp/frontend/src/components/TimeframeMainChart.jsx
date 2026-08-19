import { LineSeries } from 'lightweight-charts';
import CandleChart from './CandleChart';
import { buildFullLevelData, CHART_FRAMING, colorTimeframeCandles, finiteNumber } from './chartGeometry';
import { baseChartOptions, RAIL_STYLE } from './chartTheme';

// The big, interactive weekly/monthly chart — behind the Screener modal's
// D/W/M interval tabs AND the Watchlist page's stacked M/W panes. It's the
// SAME Trend+Box read the daily engine does, one and two timeframes up ("all
// relative and derivative"): candles are resampled on the backend (the shared
// core/pipeline/candles builders) from the full daily history; the blue rails
// are the higher-timeframe consolidation box when one is in view (absent on a
// clean candles-only payload); the caption is the plain-language structural
// read. Styled to match the daily chart (useDailyStructureChart) so switching
// timeframes feels like one TradingView pane.

const chartOptions = (width, height, interactive) => {
  const base = baseChartOptions('modal', width, height);
  const margins = interactive
    ? { top: 0.06, bottom: 0.16 }
    : CHART_FRAMING.htfPreview.scaleMargins;
  return {
    ...base,
    crosshair: interactive ? { mode: 1 } : { horzLine: { visible: false }, vertLine: { visible: false } },
    rightPriceScale: { ...base.rightPriceScale, scaleMargins: margins, autoScale: true },
    timeScale: { ...base.timeScale, timeVisible: true, fixLeftEdge: false, fixRightEdge: false },
    handleScroll: interactive,
    handleScale: interactive,
  };
};

// interactive=false is the mini-widget mode (TimeframeMiniRow): same read, same
// rails, same bounded window — scroll/scale/crosshair off so the pane is a
// static preview the wrapping control can own clicks for.
export default function TimeframeMainChart({ candles, volumes, box, label, interactive = true }) {
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
      chart.addSeries(LineSeries, RAIL_STYLE.rail).setData(buildFullLevelData(railBars, r));
      chart.addSeries(LineSeries, RAIL_STYLE.rail).setData(buildFullLevelData(railBars, s));
      chart.addSeries(LineSeries, RAIL_STYLE.mid).setData(buildFullLevelData(railBars, (r + s) / 2));
    }

    // Bounded recent window keeps weekly/monthly bars at a faithful per-bar
    // width (fitContent on a long resampled series stretches few bars across the
    // wide pane — the most distorted path). Fall back to fitContent when the box
    // origin predates the recent window, so the rails never start off-screen-left.
    // The preview cubes take a much shallower budget (CHART_FRAMING.htfPreview)
    // and NEVER fitContent — in a ~360px pane that fallback smears the whole
    // history into unreadable slivers; a rail whose origin predates the preview
    // window just spans it edge-to-edge, and the full-pane tab tells the rest.
    const n = cand.length;
    const show = interactive
      ? (label === 'WEEKLY' ? 160 : 120)
      : (label === 'WEEKLY' ? CHART_FRAMING.htfPreview.weeklyBars : CHART_FRAMING.htfPreview.monthlyBars);
    const viewFrom = Math.max(0, n - show);
    if (interactive && boxStart) {
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
    <div className={interactive ? 'screener-modal-chart' : undefined} style={{ height: '100%', minHeight: 0, position: 'relative' }}>
      <CandleChart
        spec={{
          chartOptions: (container) =>
            chartOptions(container.clientWidth || 600, container.clientHeight || 360, interactive),
          candles: coloredCandles,
          volumes,
          showVolume: !!volumes?.length,
          volumeScaleTop: interactive ? 0.84 : CHART_FRAMING.htfPreview.volumeScaleTop,
          showSma: true,
          onReady,
          onResize: (chart, container) =>
            chart.applyOptions({ width: container.clientWidth, height: container.clientHeight }),
          resizeDelayMs: 100,
          onError: (err) => console.error('[TimeframeMainChart] init failed:', err),
          deps: [candles, volumes, boxR, boxS, boxStart, limbStart, limbEnd, lpsStart, lpsEnd, interactive],
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
