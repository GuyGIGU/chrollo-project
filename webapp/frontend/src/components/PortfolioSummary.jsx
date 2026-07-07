import React from 'react';
import { fmtMoney, fmtNum, fmtPct, pnlColor, summaryCurrency, summaryValue } from './portfolioFormat';
import { explainTip } from './tooltipText';
import MetricTile from './ui/MetricTile';

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
        size="lg"
        label="Net Liquidation"
        value={fmtMoney(summaryValue(summary, 'NetLiquidation'), netCurrency)}
        sub={`Cash ${fmtMoney(summaryValue(summary, 'TotalCashValue'), summaryCurrency(summary, 'TotalCashValue'))}`}
        tone="good"
        title={explainTip({
          what: 'Broker-reported account value with assets marked to current market prices.',
          why: 'It is the main denominator for exposure, buying power, and risk context.',
          use: 'Use it to size portfolio risk; remember it moves with open positions and market prices.',
        })}
      />
      <MetricTile
        size="lg"
        label="Buying Power"
        value={fmtMoney(summaryValue(summary, 'BuyingPower'), summaryCurrency(summary, 'BuyingPower'))}
        sub={`Available ${fmtMoney(summaryValue(summary, 'AvailableFunds'), summaryCurrency(summary, 'AvailableFunds'))}`}
        title={explainTip({
          what: 'Broker-reported capacity available for new trades, including account equity and applicable margin.',
          why: 'It shows what the broker may allow, not what the trading plan should use.',
          use: 'Treat it as a hard availability check, then apply your own risk limits before any manual trade.',
        })}
      />
      <MetricTile
        size="lg"
        label="Unrealized P&L"
        value={fmtMoney(summaryValue(summary, 'UnrealizedPnL'), summaryCurrency(summary, 'UnrealizedPnL'))}
        sub={`Realized ${fmtMoney(summaryValue(summary, 'RealizedPnL'), summaryCurrency(summary, 'RealizedPnL'))}`}
        color={pnlColor(summaryValue(summary, 'UnrealizedPnL'))}
        title={explainTip({
          what: 'Profit or loss on open positions, with realized P&L shown underneath.',
          why: 'It separates live mark-to-market movement from closed trade results.',
          use: 'Use it to understand current portfolio pressure; do not treat it as a reason to ignore the trade plan.',
        })}
      />
      <MetricTile
        size="lg"
        label="Margin Cushion"
        value={fmtPct(metrics.cushionPct)}
        sub={`Excess ${fmtMoney(summaryValue(summary, 'ExcessLiquidity'), summaryCurrency(summary, 'ExcessLiquidity'))}`}
        tone={metrics.cushionPct != null && metrics.cushionPct < 25 ? 'risk' : 'good'}
        title={explainTip({
          what: 'IBKR excess liquidity shown as a percent cushion against net liquidation value.',
          why: 'Lower cushion means less room before margin stress or broker liquidation risk.',
          use: 'Keep extra buffer in volatile markets and avoid adding exposure when cushion is tightening.',
        })}
      />
      <MetricTile
        size="lg"
        label="Exposure"
        value={fmtPct(metrics.grossPct)}
        sub={`Long ${fmtMoney(metrics.longValue, netCurrency)} / Short ${fmtMoney(metrics.shortValue, netCurrency)}`}
        title={explainTip({
          what: 'Gross position value as a percent of net liquidation, split into long and short exposure.',
          why: 'It shows how much market exposure the portfolio carries relative to account size.',
          use: 'Use it to avoid stacking too much risk, especially when many positions point in the same direction.',
        })}
      />
      <MetricTile
        size="lg"
        label="Margin Use"
        value={fmtPct(metrics.marginUsePct)}
        sub={`Leverage ${metrics.leverage == null ? '-' : fmtNum(metrics.leverage, 2)}`}
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
