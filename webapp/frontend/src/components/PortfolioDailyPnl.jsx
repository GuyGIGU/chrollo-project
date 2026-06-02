import React from 'react';
import { fmtMoney, fmtPct, pnlColor, summaryCurrency, summaryValue } from './portfolioFormat';

const tileStyle = {
  background: 'var(--bg-panel)',
  border: '1px solid var(--border-color)',
  borderRadius: 8,
  padding: '13px 15px',
  cursor: 'help',
};

const metricStyle = {
  fontSize: 22,
  fontWeight: 850,
  lineHeight: 1.05,
};

const DailyPnlTile = ({ label, value, subValue, color, title }) => (
  <div style={tileStyle} title={title}>
    <div style={{ color: 'var(--text-muted)', fontSize: 10, fontWeight: 800, textTransform: 'uppercase', marginBottom: 8 }}>
      {label}
    </div>
    <div style={{ ...metricStyle, color: color || 'var(--text-main)' }}>{value}</div>
    <div style={{ color: 'var(--text-muted)', fontSize: 11, marginTop: 6 }}>{subValue}</div>
  </div>
);

const PortfolioDailyPnl = ({ summary }) => {
  const netLiquidation = Number(summaryValue(summary, 'NetLiquidation')) || 0;
  const realized = Number(summaryValue(summary, 'RealizedPnL')) || 0;
  const unrealized = Number(summaryValue(summary, 'UnrealizedPnL')) || 0;
  const total = realized + unrealized;
  const currency = summaryCurrency(summary, 'RealizedPnL') || summaryCurrency(summary, 'UnrealizedPnL');
  const totalPct = netLiquidation > 0 ? (total / netLiquidation) * 100 : null;

  return (
    <section style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))', gap: 12, marginBottom: 18 }}>
      <DailyPnlTile
        label="Daily P&L"
        value={fmtMoney(total, currency)}
        subValue={`${fmtPct(totalPct)} of net liquidation`}
        color={pnlColor(total)}
        title="Broker-reported session P&L: realized plus current unrealized P&L from the IBKR account summary."
      />
      <DailyPnlTile
        label="Realized Today"
        value={fmtMoney(realized, currency)}
        subValue="Closed or partially closed P&L"
        color={pnlColor(realized)}
        title="Realized P&L reported by IBKR for the current account snapshot."
      />
      <DailyPnlTile
        label="Open P&L"
        value={fmtMoney(unrealized, currency)}
        subValue="Live unrealized movement"
        color={pnlColor(unrealized)}
        title="Unrealized P&L on currently open positions, reported by IBKR."
      />
    </section>
  );
};

export default PortfolioDailyPnl;
