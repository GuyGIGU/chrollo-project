import { lazy, Suspense, useMemo } from 'react';
import { useOutletContext } from 'react-router-dom';
import ErrorBoundary from '../components/ErrorBoundary';
import LoadingPanel from './LoadingPanel';

const DashboardStats = lazy(() => import('../components/DashboardStats'));
const TradeTable = lazy(() => import('../components/TradeTable'));
const AnalyticsPanel = lazy(() => import('../components/AnalyticsPanel'));

// Dashboard = the trading-journal analytics view: stats strip + stock trade
// table (with the draft-row entry path) + the analytics panel. Trade data,
// filtering and draft state are owned by AppShell and arrive via outlet context.
function DashboardRoute() {
  const { stats, trades, tradeFilter, onTradeFilterChange, stockTrades, draftRow, setDraftRow, onDetailClick, onTradeUpdate, priceFor } =
    useOutletContext();

  const filteredTrades = useMemo(
    () => filterTrades(stockTrades, tradeFilter),
    [stockTrades, tradeFilter],
  );

  return (
    <Suspense fallback={<LoadingPanel />}>
      <DashboardStats
        stats={stats}
        trades={trades}
        activeFilter={tradeFilter}
        onFilterChange={onTradeFilterChange}
      />
      <TradeTable
        trades={filteredTrades}
        draftRow={draftRow}
        setDraftRow={setDraftRow}
        onDetailClick={onDetailClick}
        onTradeUpdate={onTradeUpdate}
        priceFor={priceFor}
      />
      <ErrorBoundary>
        <AnalyticsPanel />
      </ErrorBoundary>
    </Suspense>
  );
}

function filterTrades(trades, tradeFilter) {
  if (!tradeFilter) return trades;
  return trades.filter(trade => {
    const closed = trade.pnl !== null && trade.pnl !== undefined;
    if (tradeFilter === 'open') return !closed;
    if (tradeFilter === 'wins') return closed && trade.pnl > 0;
    if (tradeFilter === 'losses') return closed && trade.pnl < 0;
    if (tradeFilter === 'wash') return closed && trade.pnl === 0;
    return true;
  });
}

export default DashboardRoute;
