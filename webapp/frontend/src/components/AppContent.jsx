import DashboardStats from './DashboardStats';
import TradeTable from './TradeTable';
import ScreenerGrid from './ScreenerGrid';
import ErrorBoundary from './ErrorBoundary';
import PortfolioTab from './PortfolioTab';
import AnalyticsPanel from './AnalyticsPanel';
import ArchiveTab from './ArchiveTab';

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
    </div>
  );
}

export default AppContent;
