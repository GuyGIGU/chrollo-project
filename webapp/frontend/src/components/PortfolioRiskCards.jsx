import React from 'react';
import { fmtMoney, fmtPct, summaryCurrency, summaryValue } from './portfolioFormat';

const cardStyle = (active) => ({
  background: active ? 'rgba(88, 166, 255, 0.12)' : 'var(--bg-panel)',
  border: `1px solid ${active ? 'var(--accent-blue)' : 'var(--border-color)'}`,
  borderRadius: 8,
  padding: '13px 15px',
  cursor: 'pointer',
  minHeight: 96,
});

const positionQty = (position) => Number(position?.position ?? position?.quantity ?? 0);

const absMarketValue = (position) => Math.abs(Number(position?.market_value) || 0);

const symbolLabel = (position) => position?.symbol || '-';

const pickBiggestPosition = (positions) =>
  positions.reduce((best, item) => (absMarketValue(item) > absMarketValue(best) ? item : best), null);

const pickBiggestLoser = (positions) =>
  positions.reduce((best, item) => {
    const value = Number(item.unrealized_pnl);
    if (!Number.isFinite(value)) return best;
    if (!best || value < Number(best.unrealized_pnl)) return item;
    return best;
  }, null);

const pickLargestShort = (positions) =>
  positions.reduce((best, item) => {
    const value = Number(item.market_value);
    if (!Number.isFinite(value) || value >= 0) return best;
    if (!best || Math.abs(value) > Math.abs(Number(best.market_value))) return item;
    return best;
  }, null);

const marginPressure = (position, excessLiquidity) => {
  if (!position || excessLiquidity <= 0) return null;
  return (absMarketValue(position) / excessLiquidity) * 100;
};

const RiskCard = ({ label, position, value, subValue, title, selectedSymbol, onSelectSymbol, tone }) => {
  const symbol = symbolLabel(position);
  const active = selectedSymbol && selectedSymbol === symbol;
  const color = tone === 'danger' ? 'var(--danger)' : tone === 'warning' ? 'var(--warning)' : 'var(--text-main)';

  return (
    <button
      type="button"
      onClick={() => position?.symbol && onSelectSymbol(position.symbol)}
      style={{ ...cardStyle(active), textAlign: 'left' }}
      title={title}
    >
      <div style={{ color: 'var(--text-muted)', fontSize: 10, fontWeight: 800, textTransform: 'uppercase', marginBottom: 8 }}>
        {label}
      </div>
      <div style={{ color: 'var(--accent-blue)', fontSize: 20, fontWeight: 850 }}>{symbol}</div>
      <div style={{ color, fontSize: 14, fontWeight: 800, marginTop: 5 }}>{value}</div>
      <div style={{ color: 'var(--text-muted)', fontSize: 11, marginTop: 5 }}>{subValue}</div>
    </button>
  );
};

const PortfolioRiskCards = ({ positions, summary, selectedSymbol, onSelectSymbol }) => {
  const rows = positions || [];
  const currency = summaryCurrency(summary, 'NetLiquidation');
  const excessLiquidity = Number(summaryValue(summary, 'ExcessLiquidity')) || 0;
  const biggest = pickBiggestPosition(rows);
  const loser = pickBiggestLoser(rows);
  const short = pickLargestShort(rows);
  const pressure = pickBiggestPosition(rows);
  const pressurePct = marginPressure(pressure, excessLiquidity);

  return (
    <section style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))', gap: 12, marginBottom: 18 }}>
      <RiskCard
        label="Biggest Position"
        position={biggest}
        value={fmtMoney(absMarketValue(biggest), currency)}
        subValue={`Qty ${positionQty(biggest).toLocaleString('en-US')}`}
        selectedSymbol={selectedSymbol}
        onSelectSymbol={onSelectSymbol}
        title="Largest open position by absolute market value. Click to load its chart."
      />
      <RiskCard
        label="Biggest Loser"
        position={loser}
        value={fmtMoney(loser?.unrealized_pnl, currency)}
        subValue="Current unrealized P&L"
        tone="danger"
        selectedSymbol={selectedSymbol}
        onSelectSymbol={onSelectSymbol}
        title="Open position with the lowest unrealized P&L. Click to load its chart."
      />
      <RiskCard
        label="Largest Short"
        position={short}
        value={short ? fmtMoney(Math.abs(Number(short.market_value)), currency) : '-'}
        subValue={short ? `Qty ${positionQty(short).toLocaleString('en-US')}` : 'No short exposure'}
        tone="warning"
        selectedSymbol={selectedSymbol}
        onSelectSymbol={onSelectSymbol}
        title="Largest short exposure by absolute market value. Click to load its chart."
      />
      <RiskCard
        label="Margin Pressure"
        position={pressure}
        value={fmtPct(pressurePct)}
        subValue={`Position / excess liquidity`}
        tone={pressurePct > 75 ? 'danger' : 'warning'}
        selectedSymbol={selectedSymbol}
        onSelectSymbol={onSelectSymbol}
        title="Simple pressure estimate: position size divided by excess liquidity. Broker margin by symbol can differ."
      />
    </section>
  );
};

export default PortfolioRiskCards;
