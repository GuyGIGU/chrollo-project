import { lazy, Suspense, useMemo } from 'react';
import ErrorBoundary from './ErrorBoundary';
import useTradeLivePrices from '../hooks/useTradeLivePrices';
import { deriveTradeAlerts } from '../utils/tradeTableUtils';
import TradeRiskAlerts from './tradeTable/TradeRiskAlerts';

const DashboardStats = lazy(() => import('./DashboardStats'));
const TradeTable = lazy(() => import('./TradeTable'));
const ScreenerGrid = lazy(() => import('./ScreenerGrid'));
const PortfolioTab = lazy(() => import('./PortfolioTab'));
const AnalyticsPanel = lazy(() => import('./AnalyticsPanel'));
const ArchiveTab = lazy(() => import('./ArchiveTab'));

const loadingStyle = {
  background: 'var(--bg-panel)',
  border: '1px solid var(--border-color)',
  borderRadius: 8,
  color: 'var(--text-muted)',
  fontSize: 12,
  padding: 18,
};

const LoadingPanel = () => (
  <div style={loadingStyle}>Loading view...</div>
);

function AppContent({
  activeTab,
  stats,
  trades,
  tradeFilter,
  onTradeFilterChange,
  filteredTrades,
  optionTrades,
  draftRow,
  setDraftRow,
  onDetailClick,
  onTradeUpdate,
}) {
  const priceFor = useTradeLivePrices(trades);
  const riskAlerts = useMemo(
    () => deriveTradeAlerts(trades, priceFor),
    [priceFor, trades],
  );

  return (
    <div className="content-scroll">
      <TradeRiskAlerts alerts={riskAlerts} trades={trades} onDetailClick={onDetailClick} />
      <Suspense fallback={<LoadingPanel />}>
        {activeTab === 'dashboard' && (
          <>
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
          </>
        )}
        {activeTab === 'options' && (
          <ErrorBoundary>
            <TradeTable
              trades={optionTrades}
              draftRow={null}
              setDraftRow={() => {}}
              onDetailClick={onDetailClick}
              onTradeUpdate={onTradeUpdate}
              priceFor={priceFor}
            />
          </ErrorBoundary>
        )}
        {activeTab === 'portfolio' && (
          <ErrorBoundary>
            <PortfolioTab key="portfolio" trades={trades} onTradeDetailClick={onDetailClick} />
          </ErrorBoundary>
        )}
        {activeTab === 'screener' && (
          <ErrorBoundary>
            <ScreenerGrid key="screener" />
          </ErrorBoundary>
        )}
        {activeTab === 'archive' && (
          <ErrorBoundary>
            <ArchiveTab key="archive" />
          </ErrorBoundary>
        )}
      </Suspense>
    </div>
  );
}

export default AppContent;
