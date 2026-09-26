import React from 'react';
import { fmtMoney, fmtNum, fmtPct, pnlColor, summaryCurrency, summaryValue } from '../../../shared/formatting/portfolioFormat';
import { explainTip } from '../../../shared/formatting/tooltipText';
import MetricTile from './MetricTile';

const numberValue = (value) => {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : null;
};

const quantity = (position) => numberValue(position?.position ?? position?.quantity) || 0;

const marketValue = (position) => numberValue(position?.market_value);

const absoluteValue = (position) => Math.abs(marketValue(position) || 0);

const rankBy = (positions, target, valueFor, ascending = false) => {
  if (!target?.symbol) return null;
  const ranked = positions
    .filter((position) => Number.isFinite(valueFor(position)))
    .sort((a, b) => ascending ? valueFor(a) - valueFor(b) : valueFor(b) - valueFor(a));
  const index = ranked.findIndex((position) => position.symbol === target.symbol);
  return index >= 0 ? { rank: index + 1, count: ranked.length } : null;
};

const rankLabel = (rank) => (rank ? `Rank ${rank.rank} of ${rank.count}` : '-');

const buildInsights = (position, positions, summary) => {
  const rows = positions || [];
  const currency = summaryCurrency(summary, 'NetLiquidation');
  const netLiquidation = numberValue(summaryValue(summary, 'NetLiquidation')) || 0;
  const excessLiquidity = numberValue(summaryValue(summary, 'ExcessLiquidity')) || 0;
  const qty = quantity(position);
  const value = marketValue(position);
  const absValue = absoluteValue(position);
  const avgCost = numberValue(position?.avg_cost ?? position?.average_cost);
  const marketPrice = numberValue(position?.market_price);
  const unrealized = numberValue(position?.unrealized_pnl);
  const costBasis = Math.abs(qty * (avgCost || 0));
  const weight = netLiquidation > 0 && value != null ? absValue / netLiquidation * 100 : null;
  const marginPressure = excessLiquidity > 0 ? absValue / excessLiquidity * 100 : null;
  const pnlPct = costBasis > 0 && unrealized != null ? unrealized / costBasis * 100 : null;
  const priceVsCost = avgCost && marketPrice ? (marketPrice / avgCost - 1) * 100 : null;

  return [
    {
      label: 'Position Size',
      value: fmtMoney(absValue, currency),
      detail: rankLabel(rankBy(rows, position, absoluteValue)),
      title: explainTip({
        what: 'The absolute market value of this position.',
        why: 'It shows how large the position is compared with the rest of the portfolio.',
        use: 'Use the rank to spot concentration before adding more exposure to the same name or theme.',
      }),
    },
    {
      label: 'Portfolio Weight',
      value: fmtPct(weight),
      detail: `Net liq ${fmtMoney(netLiquidation, currency)}`,
      title: explainTip({
        what: 'The position market value as a percent of net liquidation value.',
        why: 'It shows how much of the account is tied to this one position.',
        use: 'Keep the weight aligned with the trade risk and avoid letting one position dominate the account.',
      }),
    },
    {
      label: 'Open P&L',
      value: fmtMoney(unrealized, currency),
      detail: `${fmtPct(pnlPct)} on cost basis`,
      tone: pnlColor(unrealized),
      title: explainTip({
        what: 'The unrealized gain or loss on this open position.',
        why: 'It shows the live mark-to-market result before the position is closed.',
        use: 'Review it with the trade plan, stop, and target ladder instead of reacting to P&L alone.',
      }),
    },
    {
      label: 'P&L Rank',
      value: rankLabel(rankBy(rows, position, (item) => numberValue(item.unrealized_pnl), true)),
      detail: 'Lower rank means larger unrealized loss',
      tone: unrealized < 0 ? 'var(--danger)' : 'var(--text-main)',
      title: explainTip({
        what: 'This position rank by unrealized P&L among open positions.',
        why: 'It helps surface the positions creating the most current portfolio pressure.',
        use: 'Check low-ranked losers first against their plan and risk limits.',
      }),
    },
    {
      label: 'Side / Quantity',
      value: qty < 0 ? 'Short' : 'Long',
      detail: `Qty ${fmtNum(Math.abs(qty), 0)}`,
      tone: qty < 0 ? 'var(--warning)' : 'var(--success)',
      title: explainTip({
        what: 'Whether the position is long or short, plus the share or contract quantity.',
        why: 'Direction changes how price movement affects the account.',
        use: 'Confirm the side matches the intended journal plan before using the rest of the metrics.',
      }),
    },
    {
      label: 'Price vs Avg',
      value: fmtPct(priceVsCost),
      detail: `Avg ${fmtMoney(avgCost)} / Market ${fmtMoney(marketPrice)}`,
      tone: pnlColor(priceVsCost),
      title: explainTip({
        what: 'The current market price compared with the average cost.',
        why: 'It shows how far the position has moved from the entry basis.',
        use: 'Use it with the chart and stop level to decide whether the position is behaving as planned.',
      }),
    },
    {
      label: 'Margin Pressure',
      value: fmtPct(marginPressure),
      detail: 'Position / excess liquidity',
      tone: marginPressure == null ? 'var(--text-main)' : marginPressure > 75 ? 'var(--danger)' : 'var(--warning)',
      title: explainTip({
        what: 'This position value compared with account excess liquidity.',
        why: 'A high value means the position is large relative to the available margin cushion.',
        use: 'Treat high pressure as a risk warning before adding exposure or holding through volatility.',
      }),
    },
    {
      label: 'Cost Basis',
      value: fmtMoney(costBasis, currency),
      detail: avgCost ? `${fmtMoney(avgCost)} average cost` : '-',
      title: explainTip({
        what: 'Approximate position cost basis from quantity and average cost.',
        why: 'It gives context for P&L percent and position scale.',
        use: 'Use it for review and journaling, while relying on broker statements for official accounting.',
      }),
    },
  ];
};

const PortfolioPositionInsights = ({ position, positions, summary }) => {
  if (!position?.symbol) return null;
  const insights = buildInsights(position, positions, summary);

  return (
    <section style={{ borderTop: '1px solid var(--border-color)', padding: '12px 14px 14px' }}>
      <div style={{ color: 'var(--text-muted)', fontSize: 10, fontWeight: 800, textTransform: 'uppercase', marginBottom: 9 }}>
        Position Detail
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(155px, 1fr))', gap: 10 }}>
        {insights.map((insight) => (
          <MetricTile
            key={insight.label}
            size="sm"
            label={insight.label}
            value={insight.value}
            sub={insight.detail}
            color={insight.tone}
            title={insight.title || insight.detail}
          />
        ))}
      </div>
    </section>
  );
};

export default PortfolioPositionInsights;
