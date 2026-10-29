import CandleChart from './CandleChart';
import { addBoxRails } from './chartRails';
import { baseChartOptions, CHART_COLORS } from './chartTheme';
import { CHART_FRAMING, colorMiniCandles, miniFocusLogicalRange } from './chartGeometry';

// The CONSOLIDATION sets the window: wide enough that the rest owns up to ~40%
// of the pane, with real room behind it for the move that led in, held between
// 80 and 130 trading days since Wed 28/10/2026 (his pick on the design canvas: a
// 24-day rest gets 80 days, a 40-day rest 113, at ~3-5px per day in the ~460px
// four-up card at 1920). This replaces the 2026-08-09 vertical
// proportion trim, which bought box height by deleting old bars and so re-caused
// the 2026-07 failure it was written to prevent — a base sprawling edge-to-edge
// reads tighter than it is (operator 2026-09-02). The whole model lives in the
// shared CHART_FRAMING profile so proportion is retuned in ONE place; `profile`
// stays overridable so the narrower hover glance can frame at its own span.
const MINI = CHART_FRAMING.mini;

// lightweight-charts' tick kinds: 0 a new year, 1 a new month, 2 a day of the month. A daily bar's time
// reaches the formatter as 'YYYY-MM-DD' or as { year, month, day }.
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const monthTick = (time, kind) => {
  if (kind > 1) return '';
  const year = typeof time === 'string' ? Number(time.slice(0, 4)) : time?.year;
  const month = typeof time === 'string' ? Number(time.slice(5, 7)) : time?.month;
  if (!year || !month) return '';
  return kind === 0 ? `'${String(year).slice(2)}` : MONTHS[month - 1];
};

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
    // fills the pane and a real consolidation reads at its true height, not flattened
    // (the card's price band is 88% of the well since 2026-10-02 — CHART_FRAMING.mini).
    rightPriceScale: { ...base.rightPriceScale, scaleMargins: profile.scaleMargins, autoScale: true },
    // The month axis along the bottom, as on a Finviz chart (Thu 29/10/2026; hidden
    // from 2026-09 to give its ~20px to the bars): month names, the year where it
    // turns, no day numbers. lockVisibleTimeRangeOnResize: when the card changes
    // width without a rebuild (the window dragged to the other monitor, the UI scale
    // stepped), keep the FRAMED trading days and re-space the bars — the default
    // keeps the bar spacing, so a wider card would quietly show more history than
    // the setup's window and the close-up would drift (2026-10-02).
    timeScale: { ...base.timeScale, timeVisible: false, visible: true, fixLeftEdge: true, fixRightEdge: true,
                 lockVisibleTimeRangeOnResize: true, tickMarkFormatter: monthTick },
    handleScroll: false,
    handleScale: false,
  };
};

// `profile` is the whole CHART_FRAMING entry this surface frames by — the card
// keeps `mini`, the hover glance passes `popover`. Before it existed, the bar
// budget was overridable but the margins and volume band were not, so a smaller
// surface silently framed itself with card proportions.
const ScreenerMiniChart = ({ ticker, data, profile = MINI }) => {
  const candles = data.candles;
  const coloredCandles = colorMiniCandles(data);

  const onReady = (chart) => {
    // The SAME rail drawer the modal uses — card and modal cannot diverge.
    addBoxRails(chart, data);

    // A boxless payload takes the SAME path (the reference window), so there is
    // no second, never-exercised framing leg to drift.
    const range = miniFocusLogicalRange(data, profile);
    if (range) chart.timeScale().setVisibleLogicalRange(range);
    else chart.timeScale().fitContent();
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
      // minWidth AND minHeight both 0, and they travel together: this is a ROW
      // flex item (the card's well is display:flex), and lightweight-charts
      // stamps an inline px width on its own container, which becomes this
      // item's min-content width. Without minWidth:0 the chart can therefore
      // GROW with the card but never shrink back — step the Scale knob up and
      // down across a column boundary and every card keeps the wide canvas,
      // silently clipped by .screener-card's overflow:hidden, taking the right
      // price scale and the newest bars with it until a reload. Found in the
      // 2026-09-02 branch review; pre-existing, reachable on main too.
      style={{ flex: 1, minWidth: 0, minHeight: 0, position: 'relative', pointerEvents: 'none' }}
      errorFallback={(
        <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)', fontSize: '11px' }}>
          Chart failed to load
        </div>
      )}
    />
  );
};

export default ScreenerMiniChart;
