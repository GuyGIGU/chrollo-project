import React from 'react';
import { fmtMoney, fmtNum, fmtPct, pnlColor, summaryCurrency, summaryValue } from './portfolioFormat';
import { explainTip } from './tooltipText';

const tileBase = {
  background: 'var(--bg-panel)',
  border: '1px solid var(--border-color)',
  borderRadius: '8px',
  padding: '14px 16px',
  minHeight: 82,
};

const MetricTile = ({ label, value, subValue, color, tone = 'default', title }) => {
  // A risk tone (low margin cushion / high margin use) still signals — but through
  // the VALUE color, not a decorative top-border stripe. Signal in the data, quiet chrome.
  const valueColor = color || (tone === 'risk' ? 'var(--warning)' : 'var(--text-main)');
  return (
    <div style={{ ...tileBase, cursor: title ? 'help' : 'default' }} title={title}>
      <div style={{ color: 'var(--text-muted)', fontSize: 10, fontWeight: 700, textTransform: 'uppercase', marginBottom: 8 }}>
        {label}
      </div>
      <div style={{ color: valueColor, fontSize: 20, fontWeight: 800, lineHeight: 1.1 }}>
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
        title={explainTip({
          what: 'Broker-reported account value with assets marked to current market prices.',
          why: 'It is the main denominator for exposure, buying power, and risk context.',
          use: 'Use it to size portfolio risk; remember it moves with open positions and market prices.',
        })}
      />
      <MetricTile
        label="Buying Power"
        value={fmtMoney(summaryValue(summary, 'BuyingPower'), summaryCurrency(summary, 'BuyingPower'))}
        subValue={`Available ${fmtMoney(summaryValue(summary, 'AvailableFunds'), summaryCurrency(summary, 'AvailableFunds'))}`}
        title={explainTip({
          what: 'Broker-reported capacity available for new trades, including account equity and applicable margin.',
          why: 'It shows what the broker may allow, not what the trading plan should use.',
          use: 'Treat it as a hard availability check, then apply your own risk limits before any manual trade.',
        })}
      />
      <MetricTile
        label="Unrealized P&L"
        value={fmtMoney(summaryValue(summary, 'UnrealizedPnL'), summaryCurrency(summary, 'UnrealizedPnL'))}
        subValue={`Realized ${fmtMoney(summaryValue(summary, 'RealizedPnL'), summaryCurrency(summary, 'RealizedPnL'))}`}
        color={pnlColor(summaryValue(summary, 'UnrealizedPnL'))}
        title={explainTip({
          what: 'Profit or loss on open positions, with realized P&L shown underneath.',
          why: 'It separates live mark-to-market movement from closed trade results.',
          use: 'Use it to understand current portfolio pressure; do not treat it as a reason to ignore the trade plan.',
        })}
      />
      <MetricTile
        label="Margin Cushion"
        value={fmtPct(metrics.cushionPct)}
        subValue={`Excess ${fmtMoney(summaryValue(summary, 'ExcessLiquidity'), summaryCurrency(summary, 'ExcessLiquidity'))}`}
        tone={metrics.cushionPct != null && metrics.cushionPct < 25 ? 'risk' : 'good'}
        title={explainTip({
          what: 'IBKR excess liquidity shown as a percent cushion against net liquidation value.',
          why: 'Lower cushion means less room before margin stress or broker liquidation risk.',
          use: 'Keep extra buffer in volatile markets and avoid adding exposure when cushion is tightening.',
        })}
      />
      <MetricTile
        label="Exposure"
        value={fmtPct(metrics.grossPct)}
        subValue={`Long ${fmtMoney(metrics.longValue, netCurrency)} / Short ${fmtMoney(metrics.shortValue, netCurrency)}`}
        title={explainTip({
          what: 'Gross position value as a percent of net liquidation, split into long and short exposure.',
          why: 'It shows how much market exposure the portfolio carries relative to account size.',
          use: 'Use it to avoid stacking too much risk, especially when many positions point in the same direction.',
        })}
      />
      <MetricTile
        label="Margin Use"
        value={fmtPct(metrics.marginUsePct)}
        subValue={`Leverage ${metrics.leverage == null ? '-' : fmtNum(metrics.leverage, 2)}`}
        tone={metrics.marginUsePct != null && metrics.marginUsePct > 70 ? 'risk' : 'default'}
        title={explainTip({
          what: 'Maintenance margin divided by maintenance margin plus excess liquidity.',
          why: 'It estimates how much of the account margin buffer is already being used.',
          use: 'Treat high margin use as a risk warning and reduce appetite for new manual trades.',
        })}
      />
    </section>
  );
};

export default AccountSummaryCard;
