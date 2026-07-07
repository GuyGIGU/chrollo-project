import CandleChart from '../CandleChart';
import usePositionChartData from '../../hooks/usePositionChartData';
import { isOptionSymbol, optionUnderlyingSymbol } from '../../utils/tradeUtils';
import { fmtMoney } from '../../utils/tradeTableUtils';
import { tradeVisibleLogicalRange } from '../chartGeometry';
import { baseChartOptions, CHART_COLORS } from '../chartTheme';

const chartOptions = (width, height) => {
  const base = baseChartOptions('trade', width, height);
  return {
    ...base,
    rightPriceScale: { ...base.rightPriceScale, scaleMargins: { top: 0.08, bottom: 0.25 } },
    timeScale: { ...base.timeScale, timeVisible: false, fixLeftEdge: true, fixRightEdge: true },
  };
};

export default function TradeSetupChart({ derived, trade }) {
  const rawSymbol = String(trade?.ticker || '').trim();
  const optionSymbol = isOptionSymbol(rawSymbol);
  const symbol = optionSymbol ? optionUnderlyingSymbol(rawSymbol) : rawSymbol;
  const { loading, error, data } = usePositionChartData(symbol);

  const candles = data?.candles;

  const onReady = (chart, candleSeries) => {
    if (!optionSymbol) {
      addPriceLine(candleSeries, trade?.entry_price, CHART_COLORS.goldMuted, 'Entry');
      addPriceLine(candleSeries, derived?.stopVal ?? trade?.stop_loss, CHART_COLORS.danger, 'Stop');
      addPriceLine(candleSeries, derived?.currentExit, CHART_COLORS.candle, 'Live');
      (derived?.targetLadder || []).forEach((target) => {
        addPriceLine(candleSeries, target.price, target.hit ? CHART_COLORS.success : CHART_COLORS.accent, target.label);
      });
    }

    const visible = tradeVisibleLogicalRange(candles, trade?.opening_date);
    if (visible) chart.timeScale().setVisibleLogicalRange(visible);
    else chart.timeScale().fitContent();
  };

  return (
    <section className="instrument-tile" style={sectionStyle}>
      <div style={sectionHeaderStyle}>
        <div>
          <div style={eyebrowStyle}>Setup Chart</div>
          <strong style={sectionTitleStyle}>{symbol || '-'}</strong>
        </div>
        <span style={sourceStyle}>{optionSymbol ? 'Underlying daily' : 'Daily'}</span>
      </div>
      <div className="instrument-well" style={chartShellStyle}>
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
