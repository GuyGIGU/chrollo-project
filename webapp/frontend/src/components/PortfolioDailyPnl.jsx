import { fmtMoney, fmtPct, pnlColor, summaryCurrency, summaryValue } from './portfolioFormat';
import { explainTip } from './tooltipText';
import MetricTile from './ui/MetricTile';

const PortfolioDailyPnl = ({ summary }) => {
  const netLiquidation = Number(summaryValue(summary, 'NetLiquidation')) || 0;
  const realized = Number(summaryValue(summary, 'RealizedPnL')) || 0;
  const unrealized = Number(summaryValue(summary, 'UnrealizedPnL')) || 0;
  const total = realized + unrealized;
  const currency = summaryCurrency(summary, 'RealizedPnL') || summaryCurrency(summary, 'UnrealizedPnL');
  const totalPct = netLiquidation > 0 ? (total / netLiquidation) * 100 : null;

  return (
    <section style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))', gap: 12, marginBottom: 18 }}>
      <MetricTile
        size="pnl"
        label="Daily P&L"
        value={fmtMoney(total, currency)}
        sub={`${fmtPct(totalPct)} of net liquidation`}
        color={pnlColor(total)}
        title={explainTip({
          what: 'Broker-reported session P&L: realized P&L plus current unrealized P&L.',
          why: 'It shows how today account movement compares with total account value.',
          use: 'Use it as a daily risk temperature check, not as an automatic reason to add or exit exposure.',
        })}
      />
      <MetricTile
        size="pnl"
        label="Realized Today"
        value={fmtMoney(realized, currency)}
        sub="Closed or partially closed P&L"
        color={pnlColor(realized)}
        title={explainTip({
          what: 'P&L from positions closed or partially closed in the current account snapshot.',
          why: 'It separates booked results from open mark-to-market movement.',
          use: 'Use it to review completed decisions separately from open position noise.',
        })}
      />
      <MetricTile
        size="pnl"
        label="Open P&L"
        value={fmtMoney(unrealized, currency)}
        sub="Live unrealized movement"
        color={pnlColor(unrealized)}
        title={explainTip({
          what: 'Unrealized P&L on positions that are still open.',
          why: 'It shows live portfolio pressure before gains or losses are locked in.',
          use: 'Use it with the trade plan and stop levels; open P&L can change quickly.',
        })}
      />
    </section>
  );
};

export default PortfolioDailyPnl;
