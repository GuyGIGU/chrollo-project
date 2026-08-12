import CandleChart from './CandleChart';
import { addBoxRails } from './chartRails';
import { baseChartOptions, CHART_COLORS } from './chartTheme';
import { CHART_FRAMING, colorMiniCandles, miniFocusLogicalRange } from './chartGeometry';

// Faithful daily density: ~90-130 bars in a ~480px screener card ≈ 3.7-5.3px/bar
// (Finviz-like), vs the old ~48 bars ≈ 10px/bar that let a tight base sprawl
// edge-to-edge and read tighter than it is. The budget + margins live in the
// shared CHART_FRAMING profile so proportion is retuned in ONE place; the props
// stay overridable so the small Home tiles (~165px) can pass a lower budget
// instead of cramming 90 bars into a sliver.
const MINI = CHART_FRAMING.mini;

const chartOptions = (width, height, profile) => {
  const base = baseChartOptions('mini', width, height);
  return {
    ...base,
    // ResizeObserver-backed: keeps the chart matched to the card's real width so
    // the right price scale can't overflow and get clipped when the responsive
    // grid sizes cards differently across monitors.
    autoSize: true,
    crosshair: { mode: 0 },
    // Tight vertical fit (Finviz pillar #2): small margins so the visible high-low
    // fills the pane and a real consolidation reads at its true height, not flattened.
    rightPriceScale: { ...base.rightPriceScale, scaleMargins: profile.scaleMargins, autoScale: true },
    timeScale: { ...base.timeScale, timeVisible: false, fixLeftEdge: true, fixRightEdge: true },
    handleScroll: false,
    handleScale: false,
  };
};

// `profile` is the whole CHART_FRAMING entry this surface frames by — the card
// keeps `mini`, the hover glance passes `popover`. Before it existed, the bar
// budget was overridable but the margins, volume band and TRIM floor were not,
// so a smaller surface silently framed itself with card proportions.
const ScreenerMiniChart = ({
  ticker,
  data,
  profile = MINI,
  maxBars = profile.maxVisibleBars,
  minBars = profile.minVisibleBars,
}) => {
  const candles = data.candles;
  const coloredCandles = colorMiniCandles(data);

  const onReady = (chart) => {
    // The SAME rail drawer the modal uses — card and modal cannot diverge.
    addBoxRails(chart, data);

    if (data.base_len > 0 && data.candles?.length > 0) {
      const range = miniFocusLogicalRange(data, maxBars, minBars, profile);
      if (range) chart.timeScale().setVisibleLogicalRange(range);
    } else {
      chart.timeScale().fitContent();
    }
  };

  return (
    <CandleChart
      spec={{
        chartOptions: (container) =>
          chartOptions(container.clientWidth || 380, container.clientHeight || 240, profile),
        candles: coloredCandles,
        barOptions: {
          upColor: CHART_COLORS.candle,
          downColor: CHART_COLORS.candle,
          lastValueVisible: false,
          priceLineVisible: false,
          thinBars: false,
        },
        volumes: data.volumes,
        showVolume: true,
        volumeScaleTop: profile.volumeScaleTop,
        onReady,
        onError: (err) => console.error(`[ScreenerMiniChart] Chart init failed for ${ticker}:`, err),
        deps: [ticker, data],
      }}
      candles={candles}
      style={{ flex: 1, minHeight: 0, position: 'relative', pointerEvents: 'none' }}
      errorFallback={(
        <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)', fontSize: '11px' }}>
          Chart failed to load
        </div>
      )}
    />
  );
};

export default ScreenerMiniChart;
