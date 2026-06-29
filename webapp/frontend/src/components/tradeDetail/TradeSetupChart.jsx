import CandleChart from '../CandleChart';
import usePositionChartData from '../../hooks/usePositionChartData';
import { isOptionSymbol, optionUnderlyingSymbol } from '../../utils/tradeUtils';
import { fmtMoney } from '../../utils/tradeTableUtils';
import { tradeVisibleLogicalRange } from '../chartGeometry';

const chartOptions = (width, height) => ({
  width,
  height,
  layout: {
    background: { type: 'solid', color: '#171a24' },
    textColor: '#8c94a8',
    fontFamily: "'JetBrains Mono', monospace",
    fontSize: 11,
  },
  grid: {
    vertLines: { color: 'rgba(65, 72, 96, 0.26)' },
    horzLines: { color: 'rgba(65, 72, 96, 0.26)' },
  },
  rightPriceScale: {
    borderColor: '#2f3447',
    scaleMargins: { top: 0.08, bottom: 0.25 },
  },
  timeScale: {
    borderColor: '#2f3447',
    fixLeftEdge: true,
    fixRightEdge: true,
    timeVisible: false,
  },
});

export default function TradeSetupChart({ derived, trade }) {
  const rawSymbol = String(trade?.ticker || '').trim();
  const optionSymbol = isOptionSymbol(rawSymbol);
  const symbol = optionSymbol ? optionUnderlyingSymbol(rawSymbol) : rawSymbol;
  const { loading, error, data } = usePositionChartData(symbol);

  const candles = data?.candles;

  const onReady = (chart, candleSeries) => {
    if (!optionSymbol) {
      addPriceLine(candleSeries, trade?.entry_price, '#d5b85b', 'Entry');
      addPriceLine(candleSeries, derived?.stopVal ?? trade?.stop_loss, '#f26770', 'Stop');
      addPriceLine(candleSeries, derived?.currentExit, '#d8dbe5', 'Live');
      (derived?.targetLadder || []).forEach((target) => {
        addPriceLine(candleSeries, target.price, target.hit ? '#3dd37a' : '#5b8aff', target.label);
      });
    }

    const visible = tradeVisibleLogicalRange(candles, trade?.opening_date);
    if (visible) chart.timeScale().setVisibleLogicalRange(visible);
    else chart.timeScale().fitContent();
  };

  return (
    <section style={sectionStyle}>
      <div style={sectionHeaderStyle}>
        <div>
          <div style={eyebrowStyle}>Setup Chart</div>
          <strong style={sectionTitleStyle}>{symbol || '-'}</strong>
        </div>
        <span style={sourceStyle}>{optionSymbol ? 'Underlying daily' : 'Daily'}</span>
      </div>
      <div style={chartShellStyle}>
        {loading && <div style={messageStyle}>Loading chart...</div>}
        {error && !loading && <div style={messageStyle}>{error}</div>}
        {!symbol && !loading && !error && <div style={messageStyle}>Chart unavailable.</div>}
        {symbol && !loading && !error && (
          <CandleChart
            spec={{
              chartOptions: (container) =>
                chartOptions(container.clientWidth || 720, container.clientHeight || 300),
              candles,
              volumes: data?.volumes,
              showVolume: !!data?.volumes?.length,
              volumeScaleTop: 0.82,
              onReady,
              onResize: (chart, container) =>
                chart.applyOptions({ width: container.clientWidth || 720 }),
              deps: [data, derived, optionSymbol, trade],
            }}
            candles={candles}
            style={canvasStyle}
          />
        )}
      </div>
    </section>
  );
}

const addPriceLine = (series, value, color, title) => {
  const price = Number(value);
  if (!Number.isFinite(price) || price <= 0) return;
  series.createPriceLine({
    price,
    color,
    lineWidth: 1,
    lineStyle: 0,
    axisLabelVisible: true,
    title: `${title} ${fmtMoney(price)}`,
  });
};

const sectionStyle = {
  background: 'rgba(255,255,255,0.025)',
  border: '1px solid var(--border-color)',
  borderRadius: 8,
  padding: 14,
};

const sectionHeaderStyle = {
  alignItems: 'center',
  display: 'flex',
  justifyContent: 'space-between',
  gap: 12,
  marginBottom: 10,
};

const eyebrowStyle = {
  color: 'var(--text-muted)',
  fontSize: 10,
  fontWeight: 800,
  letterSpacing: '0.08em',
  textTransform: 'uppercase',
};

const sectionTitleStyle = {
  color: 'var(--text-main)',
  display: 'block',
  fontSize: 15,
  marginTop: 3,
};

const sourceStyle = {
  color: 'var(--text-muted)',
  fontSize: 11,
  fontWeight: 700,
};

const chartShellStyle = {
  minHeight: 300,
  position: 'relative',
};

const canvasStyle = {
  height: 300,
  minHeight: 260,
};

const messageStyle = {
  alignItems: 'center',
  color: 'var(--text-muted)',
  display: 'flex',
  fontSize: 12,
  height: 300,
  justifyContent: 'center',
  textAlign: 'center',
};
