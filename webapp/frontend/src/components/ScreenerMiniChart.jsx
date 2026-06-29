import { LineSeries } from 'lightweight-charts';
import CandleChart from './CandleChart';
import {
  buildLevelData,
  colorMiniCandles,
  finiteNumber,
  miniFocusLogicalRange,
  setupIndexes,
} from './chartGeometry';

// Faithful daily density: ~90-130 bars in a ~480px screener card ≈ 3.7-5.3px/bar
// (Finviz-like), vs the old ~48 bars ≈ 10px/bar that let a tight base sprawl
// edge-to-edge and read tighter than it is. Overridable so the small Home tiles
// (~165px) can pass a lower budget instead of cramming 90 bars into a sliver.
const DEFAULT_MAX_BARS = 130;
const DEFAULT_MIN_BARS = 90;

const chartOptions = (width, height) => ({
  width,
  height,
  // ResizeObserver-backed: keeps the chart matched to the card's real width so
  // the right price scale can't overflow and get clipped when the responsive
  // grid sizes cards differently across monitors.
  autoSize: true,
  layout: {
    background: { type: 'solid', color: '#141721' },
    textColor: '#747c8f',
    fontFamily: "'JetBrains Mono', monospace",
    fontSize: 10,
  },
  grid: {
    vertLines: { color: 'rgba(47, 52, 71, 0.13)' },
    horzLines: { color: 'rgba(47, 52, 71, 0.13)' },
  },
  crosshair: { mode: 0 },
  // Tight vertical fit (Finviz pillar #2): small margins so the visible high-low
  // fills the pane and a real consolidation reads at its true height, not flattened.
  rightPriceScale: { borderColor: 'rgba(47, 52, 71, 0.56)', scaleMargins: { top: 0.06, bottom: 0.14 }, autoScale: true },
  timeScale: {
    borderColor: 'rgba(47, 52, 71, 0.56)',
    timeVisible: false,
    fixLeftEdge: true,
    fixRightEdge: true,
  },
  handleScroll: false,
  handleScale: false,
});

const ScreenerMiniChart = ({ ticker, data, maxBars = DEFAULT_MAX_BARS, minBars = DEFAULT_MIN_BARS }) => {
  const candles = data.candles;
  const coloredCandles = colorMiniCandles(data);

  const onReady = (chart) => {
    const levelOptions = {
      color: '#2457b8',
      lineWidth: 2,
      crosshairMarkerVisible: false,
      lastValueVisible: false,
      priceLineVisible: false,
    };
    const rSeries = chart.addSeries(LineSeries, levelOptions);
    const sSeries = chart.addSeries(LineSeries, levelOptions);
    const midSeries = chart.addSeries(LineSeries, {
      ...levelOptions,
      color: 'rgba(154, 161, 178, 0.42)',
      lineWidth: 1,
      lineStyle: 2,
    });

    const { baseStart } = setupIndexes(data);
    const midValue = (data.R + data.S) / 2;
    rSeries.setData(buildLevelData(data.candles || [], baseStart, data.R));
    sSeries.setData(buildLevelData(data.candles || [], baseStart, data.S));
    midSeries.setData(buildLevelData(data.candles || [], baseStart, midValue));

    const innerR = finiteNumber(data.inner_R);
    const innerS = finiteNumber(data.inner_S);
    const innerStartBar = finiteNumber(data.inner_start_bar);
    if (innerR != null && innerS != null && innerStartBar != null) {
      const innerStart = Math.max(0, Math.min((data.candles || []).length - 1, Math.trunc(innerStartBar)));
      const innerOptions = {
        ...levelOptions,
        color: '#5f8fe6',
        lineWidth: 2,
      };
      chart.addSeries(LineSeries, innerOptions).setData(buildLevelData(data.candles || [], innerStart, innerR));
      chart.addSeries(LineSeries, innerOptions).setData(buildLevelData(data.candles || [], innerStart, innerS));
    }

    if (data.base_len > 0 && data.candles?.length > 0) {
      const range = miniFocusLogicalRange(data, maxBars, minBars);
      if (range) chart.timeScale().setVisibleLogicalRange(range);
    } else {
      chart.timeScale().fitContent();
    }
  };

  return (
    <CandleChart
      spec={{
        chartOptions: (container) =>
          chartOptions(container.clientWidth || 380, container.clientHeight || 240),
        candles: coloredCandles,
        barOptions: {
          upColor: '#d7dae4',
          downColor: '#d7dae4',
          lastValueVisible: false,
          priceLineVisible: false,
          thinBars: false,
        },
        volumes: data.volumes,
        showVolume: true,
        volumeScaleTop: 0.86,
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
