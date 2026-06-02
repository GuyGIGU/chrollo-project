import React from 'react';
import { fmtMoney, fmtNum, fmtPct, pnlColor, summaryCurrency, summaryValue } from './portfolioFormat';

const cardStyle = {
  background: 'rgba(255,255,255,0.025)',
  border: '1px solid var(--border-color)',
  borderRadius: 8,
  padding: '10px 12px',
  minHeight: 76,
};

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
    },
    {
      label: 'Portfolio Weight',
      value: fmtPct(weight),
      detail: `Net liq ${fmtMoney(netLiquidation, currency)}`,
    },
    {
      label: 'Open P&L',
      value: fmtMoney(unrealized, currency),
      detail: `${fmtPct(pnlPct)} on cost basis`,
      tone: pnlColor(unrealized),
    },
    {
      label: 'P&L Rank',
      value: rankLabel(rankBy(rows, position, (item) => numberValue(item.unrealized_pnl), true)),
      detail: 'Lower rank means larger unrealized loss',
      tone: unrealized < 0 ? 'var(--danger)' : 'var(--text-main)',
    },
    {
      label: 'Side / Quantity',
      value: qty < 0 ? 'Short' : 'Long',
      detail: `Qty ${fmtNum(Math.abs(qty), 0)}`,
      tone: qty < 0 ? 'var(--warning)' : 'var(--success)',
    },
    {
      label: 'Price vs Avg',
      value: fmtPct(priceVsCost),
      detail: `Avg ${fmtMoney(avgCost)} / Market ${fmtMoney(marketPrice)}`,
      tone: pnlColor(priceVsCost),
    },
    {
      label: 'Margin Pressure',
      value: fmtPct(marginPressure),
      detail: 'Position / excess liquidity',
      tone: marginPressure == null ? 'var(--text-main)' : marginPressure > 75 ? 'var(--danger)' : 'var(--warning)',
    },
    {
      label: 'Cost Basis',
      value: fmtMoney(costBasis, currency),
      detail: avgCost ? `${fmtMoney(avgCost)} average cost` : '-',
    },
  ];
};

const InsightCard = ({ insight }) => (
  <div style={cardStyle} title={insight.detail}>
    <div style={{ color: 'var(--text-muted)', fontSize: 10, fontWeight: 800, textTransform: 'uppercase', marginBottom: 7 }}>
      {insight.label}
    </div>
    <div style={{ color: insight.tone || 'var(--text-main)', fontSize: 15, fontWeight: 850 }}>
      {insight.value}
    </div>
    <div style={{ color: 'var(--text-muted)', fontSize: 11, marginTop: 6 }}>
      {insight.detail}
    </div>
  </div>
);

const PortfolioPositionInsights = ({ position, positions, summary }) => {
  if (!position?.symbol) return null;
  const insights = buildInsights(position, positions, summary);

  return (
    <section style={{ borderTop: '1px solid var(--border-color)', padding: '12px 14px 14px' }}>
      <div style={{ color: 'var(--text-muted)', fontSize: 10, fontWeight: 800, textTransform: 'uppercase', marginBottom: 9 }}>
        Position Detail
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(155px, 1fr))', gap: 10 }}>
        {insights.map((insight) => <InsightCard key={insight.label} insight={insight} />)}
      </div>
    </section>
  );
};

export default PortfolioPositionInsights;
