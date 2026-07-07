import { LineSeries } from 'lightweight-charts';
import CandleChart from './CandleChart';
import Modal from './ui/Modal';
import usePositionChartData from '../hooks/usePositionChartData';
import { buildPositiveLevel } from './chartGeometry';
import { baseChartOptions, CHART_COLORS } from './chartTheme';
import { fmtMoney, fmtNum, pnlColor } from './portfolioFormat';
import PortfolioPositionInsights from './PortfolioPositionInsights';
import { explainTip } from './tooltipText';

const chartOptions = (width, height) => {
  const base = baseChartOptions('position', width, height);
  return {
    ...base,
    rightPriceScale: { ...base.rightPriceScale, scaleMargins: { top: 0.08, bottom: 0.24 } },
    timeScale: { ...base.timeScale, timeVisible: false, fixLeftEdge: true, fixRightEdge: true },
  };
};
const overlayStyle = {
  position: 'fixed',
  inset: 0,
  zIndex: 2000,
  background: 'rgba(10, 12, 18, 0.78)',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  padding: 18,
};
const chartShellStyle = {
  width: 'min(1120px, 96vw)',
  maxHeight: '88vh',
  border: '1px solid var(--border-color)',
  borderRadius: 8,
  background: 'var(--bg-panel)',
  overflowY: 'auto',
  boxShadow: '0 24px 70px rgba(0,0,0,0.42)',
};

const PositionChartCanvas = ({ symbol, data, position }) => {
  const candles = data?.candles;

  const onReady = (chart) => {
    const avgLine = chart.addSeries(LineSeries, {
      color: CHART_COLORS.goldMuted,
      lineWidth: 1,
      lineStyle: 2,
      lastValueVisible: false,
      priceLineVisible: false,
      crosshairMarkerVisible: false,
    });
    avgLine.setData(buildPositiveLevel(candles, position?.avg_cost ?? position?.average_cost));

    chart.timeScale().fitContent();
  };

  return (
    <CandleChart
      spec={{
        chartOptions: (container) =>
          chartOptions(container.clientWidth || 760, container.clientHeight || 310),
        candles,
        volumes: data?.volumes,
        showVolume: true,
        onReady,
        onResize: (chart, container) =>
          chart.applyOptions({ width: container.clientWidth || 760 }),
        deps: [symbol, data, position],
      }}
      candles={candles}
      className="instrument-well"
      style={{ height: 310, minHeight: 260, position: 'relative' }}
    />
  );
};

const PositionChartHeader = ({ symbol, position, onClose }) => {
  const qty = Number(position?.position ?? position?.quantity ?? 0);
  const value = Number(position?.market_value);
  const unrealized = Number(position?.unrealized_pnl);
  const price = Number(position?.market_price);

  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 12, padding: '13px 15px', borderBottom: '1px solid var(--border-color)' }}>
      <div>
        <div style={{ color: 'var(--text-muted)', fontSize: 10, fontWeight: 800, textTransform: 'uppercase' }}>Position Chart</div>
        <div style={{ color: 'var(--accent-blue)', fontSize: 22, fontWeight: 850 }}>{symbol || '—'}</div>
      </div>
      <div style={{ color: 'var(--text-muted)', fontSize: 11 }}>Qty {fmtNum(qty, 0)}</div>
      <div style={{ color: 'var(--text-muted)', fontSize: 11 }}>Market {Number.isFinite(price) ? fmtMoney(price) : '—'}</div>
      <div style={{ color: 'var(--text-muted)', fontSize: 11 }}>Value {Number.isFinite(value) ? fmtMoney(value) : '—'}</div>
      <div style={{ color: pnlColor(unrealized), fontSize: 11, fontWeight: 800 }}>Open P&L {Number.isFinite(unrealized) ? fmtMoney(unrealized) : '—'}</div>
      <button
        type="button"
        onClick={onClose}
        title="Close chart"
        style={{
          marginLeft: 'auto',
          width: 30,
          height: 30,
          borderRadius: 6,
          border: '1px solid var(--border-color)',
          background: 'transparent',
          color: 'var(--text-muted)',
          cursor: 'pointer',
          fontWeight: 900,
        }}
      >
        x
      </button>
    </div>
  );
};

const PortfolioPositionChart = ({ selectedSymbol, position, positions, summary, open, onClose }) => {
  const { loading, error, data } = usePositionChartData(open ? selectedSymbol : '');

  if (!open) return null;

  return (
    <Modal
      onClose={onClose}
      overlayStyle={overlayStyle}
      contentStyle={chartShellStyle}
      contentProps={{
        title: explainTip({
          what: 'A daily OHLCV chart for the selected open position, using the local market-data endpoint.',
          why: 'It lets us compare the broker position with the actual price and volume path.',
          use: 'Use the chart to review behavior around average cost, support, and planned exit levels.',
        }),
      }}
    >
      <PositionChartHeader symbol={selectedSymbol} position={position} onClose={onClose} />
      {!selectedSymbol && <div style={{ padding: 28, color: 'var(--text-muted)', textAlign: 'center' }}>Select a position to load its chart.</div>}
      {selectedSymbol && loading && <div style={{ padding: 28, color: 'var(--text-muted)', textAlign: 'center' }}>Loading chart data...</div>}
      {selectedSymbol && error && <div style={{ padding: 28, color: 'var(--text-muted)', textAlign: 'center' }}>{error}</div>}
      {selectedSymbol && data && <PositionChartCanvas symbol={selectedSymbol} data={data} position={position} />}
      <PortfolioPositionInsights position={position} positions={positions} summary={summary} />
    </Modal>
  );
};

export default PortfolioPositionChart;
