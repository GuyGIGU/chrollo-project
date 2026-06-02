import React from 'react';
import { fmtMoney, fmtNum, fmtPct, pnlColor, summaryCurrency, summaryValue } from './portfolioFormat';

const tileBase = {
  background: 'linear-gradient(180deg, rgba(255,255,255,0.025), rgba(255,255,255,0)), var(--bg-panel)',
  border: '1px solid var(--border-color)',
  borderRadius: '8px',
  padding: '14px 16px',
  minHeight: 82,
};

const MetricTile = ({ label, value, subValue, color, tone = 'default', title }) => {
  const accent = tone === 'risk' ? 'var(--warning)' : tone === 'good' ? 'var(--success)' : 'var(--accent-blue)';
  return (
    <div style={{ ...tileBase, borderTop: `2px solid ${accent}`, cursor: title ? 'help' : 'default' }} title={title}>
      <div style={{ color: 'var(--text-muted)', fontSize: 10, fontWeight: 700, textTransform: 'uppercase', marginBottom: 8 }}>
        {label}
      </div>
      <div style={{ color: color || 'var(--text-main)', fontSize: 20, fontWeight: 800, lineHeight: 1.1 }}>
        {value}
      </div>
      {subValue && (
        <div style={{ color: 'var(--text-muted)', fontSize: 11, marginTop: 6 }}>
          {subValue}
        </div>
      )}
    </div>
  );
};

const exposureMetrics = (summary, positions) => {
  const netLiq = Number(summaryValue(summary, 'NetLiquidation')) || 0;
  const gross = Number(summaryValue(summary, 'GrossPositionValue')) || 0;
  const maint = Number(summaryValue(summary, 'MaintMarginReq')) || 0;
  const excess = Number(summaryValue(summary, 'ExcessLiquidity')) || 0;
  const cushion = Number(summaryValue(summary, 'Cushion'));
  const leverage = Number(summaryValue(summary, 'Leverage-S'));

  const longValue = positions.reduce((sum, item) => {
    const value = Number(item.market_value);
    return value > 0 ? sum + value : sum;
  }, 0);
  const shortValue = positions.reduce((sum, item) => {
    const value = Number(item.market_value);
    return value < 0 ? sum + Math.abs(value) : sum;
  }, 0);

  return {
    cushionPct: Number.isFinite(cushion) ? cushion * 100 : null,
    grossPct: netLiq > 0 ? (gross / netLiq) * 100 : null,
    marginUsePct: maint + excess > 0 ? (maint / (maint + excess)) * 100 : null,
    leverage: Number.isFinite(leverage) ? leverage : null,
    longValue,
    shortValue,
  };
};

const AccountSummaryCard = ({ summary, positions }) => {
  const metrics = exposureMetrics(summary, positions || []);
  const netCurrency = summaryCurrency(summary, 'NetLiquidation');

  return (
    <section style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(190px, 1fr))', gap: 12, marginBottom: 18 }}>
      <MetricTile
        label="Net Liquidation"
        value={fmtMoney(summaryValue(summary, 'NetLiquidation'), netCurrency)}
        subValue={`Cash ${fmtMoney(summaryValue(summary, 'TotalCashValue'), summaryCurrency(summary, 'TotalCashValue'))}`}
        tone="good"
        title="Estimated account value if positions were closed at current market prices."
      />
      <MetricTile
        label="Buying Power"
        value={fmtMoney(summaryValue(summary, 'BuyingPower'), summaryCurrency(summary, 'BuyingPower'))}
        subValue={`Available ${fmtMoney(summaryValue(summary, 'AvailableFunds'), summaryCurrency(summary, 'AvailableFunds'))}`}
        title="Broker-reported funds available for new trades, before any additional risk rules you apply."
      />
      <MetricTile
        label="Unrealized P&L"
        value={fmtMoney(summaryValue(summary, 'UnrealizedPnL'), summaryCurrency(summary, 'UnrealizedPnL'))}
        subValue={`Realized ${fmtMoney(summaryValue(summary, 'RealizedPnL'), summaryCurrency(summary, 'RealizedPnL'))}`}
        color={pnlColor(summaryValue(summary, 'UnrealizedPnL'))}
        title="Open position P&L, with realized P&L shown underneath from the IBKR account summary."
      />
      <MetricTile
        label="Margin Cushion"
        value={fmtPct(metrics.cushionPct)}
        subValue={`Excess ${fmtMoney(summaryValue(summary, 'ExcessLiquidity'), summaryCurrency(summary, 'ExcessLiquidity'))}`}
        tone={metrics.cushionPct != null && metrics.cushionPct < 25 ? 'risk' : 'good'}
        title="IBKR cushion converted to percent. Lower cushion means less room before margin stress."
      />
      <MetricTile
        label="Exposure"
        value={fmtPct(metrics.grossPct)}
        subValue={`Long ${fmtMoney(metrics.longValue, netCurrency)} / Short ${fmtMoney(metrics.shortValue, netCurrency)}`}
        title="Gross position value as a percent of net liquidation, split into long and short exposure."
      />
      <MetricTile
        label="Margin Use"
        value={fmtPct(metrics.marginUsePct)}
        subValue={`Leverage ${metrics.leverage == null ? '-' : fmtNum(metrics.leverage, 2)}`}
        tone={metrics.marginUsePct != null && metrics.marginUsePct > 70 ? 'risk' : 'default'}
        title="Maintenance margin divided by maintenance margin plus excess liquidity."
      />
    </section>
  );
};

export default AccountSummaryCard;
