import React, { useEffect, useMemo, useState } from 'react';
import usePortfolioSnapshot, { emptyPortfolioSnapshot } from '../hooks/usePortfolioSnapshot';
import AccountSummaryCard from './PortfolioSummary';
import PortfolioDailyPnl from './PortfolioDailyPnl';
import PortfolioPositionChart from './PortfolioPositionChart';
import PortfolioStatusBar from './PortfolioStatusBar';
import { LivePositionsTable, OpenOrdersTable, RecentExecutionsTable } from './PortfolioTables';
import { summaryValue } from '../presentation/portfolioFormat';
import { buildPortfolioPlanMap } from '../model/portfolioPlanUtils';

const unavailableStyle = {
  background: 'var(--bg-panel)',
  border: '1px solid var(--border-color)',
  borderRadius: '8px',
  padding: 32,
  textAlign: 'center',
  color: 'var(--text-muted)',
};

// Status + actions come from the shell's single owners (useIBKRStatus /
// useIbkrActions mounted once in AppShell, threaded via outlet context) — this
// tab must not poll /ibkr/status or hand-roll its own reconnect flow.
const PortfolioTab = ({ onTradeDetailClick, trades = [], riskFor, riskSummary, ibkrStatus: status, ibkrActions }) => {
  const [selectedSymbol, setSelectedSymbol] = useState('');
  const [chartOpen, setChartOpen] = useState(false);
  const enabled = !!status?.available;
  const { snapshot, sseStatus, hasData } = usePortfolioSnapshot(enabled);

  const summary = snapshot.account_summary || emptyPortfolioSnapshot.account_summary;
  const positions = useMemo(() => snapshot.positions || [], [snapshot.positions]);
  const openOrders = snapshot.open_orders || [];
  const executions = snapshot.recent_executions || [];
  const dailyRestart = !!snapshot.daily_restart || !!status?.daily_restart;
  const sessionCompetition = !!snapshot.session_competition || !!status?.session_competition;
  const netLiquidation = Number(summaryValue(summary, 'NetLiquidation')) || 0;
  const positionPlans = useMemo(
    () => buildPortfolioPlanMap(positions, trades, riskFor),
    [positions, trades, riskFor],
  );

  const largestPosition = useMemo(() => (
    positions.reduce((best, item) => {
      const value = Math.abs(Number(item.market_value) || 0);
      const bestValue = Math.abs(Number(best?.market_value) || 0);
      return value > bestValue ? item : best;
    }, null)
  ), [positions]);

  useEffect(() => {
    if (!positions.length) {
      if (selectedSymbol) setSelectedSymbol('');
      if (chartOpen) setChartOpen(false);
      return;
    }
    const stillOpen = positions.some((position) => position.symbol === selectedSymbol);
    if (!stillOpen && largestPosition?.symbol) setSelectedSymbol(largestPosition.symbol);
  }, [chartOpen, largestPosition, positions, selectedSymbol]);

  const selectedPosition = useMemo(
    () => positions.find((position) => position.symbol === selectedSymbol) || largestPosition,
    [positions, selectedSymbol, largestPosition],
  );

  const isStale = useMemo(() => {
    if (snapshot.stale) return true;
    if (!status?.connected) return true;
    return sseStatus === 'error' || sseStatus === 'closed';
  }, [status, sseStatus, snapshot.stale]);

  const openPositionChart = (symbol) => {
    setSelectedSymbol(symbol);
    setChartOpen(true);
  };

  if (!status?.available) {
    return (
      <div style={unavailableStyle}>
        <div style={{ fontSize: 14, marginBottom: 8, color: 'var(--text-main)' }}>IBKR integration unavailable</div>
        <div style={{ fontSize: 12 }}>Install ib_async and start TWS or IB Gateway, then restart the backend.</div>
      </div>
    );
  }

  return (
    <div style={{ opacity: isStale ? 0.9 : 1, transition: 'opacity 0.3s' }}>
      <PortfolioStatusBar
        status={status}
        sseStatus={sseStatus}
        lastUpdate={snapshot.last_update}
        stale={isStale}
        hasData={hasData}
        dailyRestart={dailyRestart}
        sessionCompetition={sessionCompetition}
        onReconnect={ibkrActions?.reconnectIbkr}
        onDisconnect={ibkrActions?.disconnectIbkr}
        riskSummary={riskSummary}
      />
      <PortfolioDailyPnl summary={summary} />
      <AccountSummaryCard summary={summary} positions={positions} />
      <PortfolioPositionChart
        selectedSymbol={selectedSymbol}
        position={selectedPosition}
        positions={positions}
        summary={summary}
        open={chartOpen}
        onClose={() => setChartOpen(false)}
      />
      <LivePositionsTable
        positions={positions}
        positionPlans={positionPlans}
        netLiquidation={netLiquidation}
        selectedSymbol={selectedSymbol}
        onSelectSymbol={openPositionChart}
        onOpenTradePlan={onTradeDetailClick}
      />
      <OpenOrdersTable orders={openOrders} />
      <RecentExecutionsTable executions={executions} />
    </div>
  );
};

export default PortfolioTab;
