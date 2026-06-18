import { lazy, Suspense } from 'react';
import ErrorBoundary from './ErrorBoundary';

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
  return (
    <div className="content-scroll">
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
              alertTrades={trades}
              draftRow={draftRow}
              setDraftRow={setDraftRow}
              onDetailClick={onDetailClick}
              onTradeUpdate={onTradeUpdate}
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
              alertTrades={optionTrades}
              draftRow={null}
              setDraftRow={() => {}}
              onDetailClick={onDetailClick}
              onTradeUpdate={onTradeUpdate}
            />
          </ErrorBoundary>
        )}
        {activeTab === 'portfolio' && (
          <ErrorBoundary>
            <PortfolioTab key="portfolio" />
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
