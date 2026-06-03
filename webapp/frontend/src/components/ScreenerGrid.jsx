import { useCallback, useEffect, useState } from 'react';
import ScreenerCard from './ScreenerCard';
import ScreenerModal from './ScreenerModal';
import ScreenerPager from './ScreenerPager';
import ScreenerScanProgress from './ScreenerScanProgress';
import ScreenerToolbar from './ScreenerToolbar';
import ScreenerWatchlistPanel from './ScreenerWatchlistPanel';
import useScanRunner from '../hooks/useScanRunner';
import useScreenerData from '../hooks/useScreenerData';
import useScreenerFilters from '../hooks/useScreenerFilters';
import useWatchlist from '../hooks/useWatchlist';

const ScreenerGrid = () => {
  const [activeModalTicker, setActiveModalTicker] = useState(null);
  const { watchlist, toggleWatchlist } = useWatchlist();
  const { screenerData, earningsByTicker, fetchScreener, fetchEarnings } = useScreenerData();
  const filters = useScreenerFilters(screenerData, watchlist);
  const scan = useScanRunner(fetchScreener);
  const hasScreenerData = !!screenerData?.ordered_tickers;

  useEffect(() => {
    fetchEarnings(filters.paginatedTickers);
  }, [fetchEarnings, filters.paginatedTickers]);

  const handleNextModal = useCallback(() => {
    if (!activeModalTicker || filters.filteredTickers.length === 0) return;
    const currentIndex = filters.filteredTickers.indexOf(activeModalTicker);
    const nextIndex = (currentIndex + 1) % filters.filteredTickers.length;
    setActiveModalTicker(filters.filteredTickers[nextIndex]);
  }, [activeModalTicker, filters.filteredTickers]);

  const handlePrevModal = useCallback(() => {
    if (!activeModalTicker || filters.filteredTickers.length === 0) return;
    const currentIndex = filters.filteredTickers.indexOf(activeModalTicker);
    const prevIndex = (currentIndex - 1 + filters.filteredTickers.length) % filters.filteredTickers.length;
    setActiveModalTicker(filters.filteredTickers[prevIndex]);
  }, [activeModalTicker, filters.filteredTickers]);

  useEffect(() => {
    const handleKeyDown = (event) => {
      if (!activeModalTicker) return;
      if (event.key === 'ArrowRight' || event.key === 'ArrowDown') {
        event.preventDefault();
        handleNextModal();
      }
      if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') {
        event.preventDefault();
        handlePrevModal();
      }
      if (event.key === 'Escape') {
        event.preventDefault();
        setActiveModalTicker(null);
      }
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [activeModalTicker, handleNextModal, handlePrevModal]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      <ScreenerToolbar
        screenerData={screenerData}
        isScanning={scan.isScanning}
        matchedCount={filters.filteredTickers.length}
        watchlistSize={watchlist.size}
        filters={filters}
        onRunScan={scan.handleRunScan}
      />

      {filters.tierFilter === 'WATCHLIST' && (
        <ScreenerWatchlistPanel
          watchlist={watchlist}
          screenerData={screenerData}
          isScanning={scan.isScanning}
          onToggleWatchlist={toggleWatchlist}
        />
      )}

      <ScreenerScanProgress
        isScanning={scan.isScanning}
        scanProgress={scan.scanProgress}
        scanPhase={scan.scanPhase}
        scanLogs={scan.scanLogs}
      />

      {!hasScreenerData && !scan.isScanning && <EmptyState message="Loading Screener Data... (If this takes more than a moment, run a new market scan!)" />}
      {hasScreenerData && !scan.isScanning && filters.paginatedTickers.length === 0 && <EmptyState message="No setups found matching current filters." />}
      {hasScreenerData && !scan.isScanning && filters.paginatedTickers.length > 0 && (
        <>
          <div style={gridStyle}>
            {filters.paginatedTickers.map(ticker => (
              <ScreenerCard
                key={ticker}
                ticker={ticker}
                data={screenerData.chart_data[ticker]}
                earnings={earningsByTicker[ticker]}
                watchlisted={watchlist.has(ticker)}
                onToggleWatchlist={toggleWatchlist}
                onClick={setActiveModalTicker}
              />
            ))}
          </div>
          <ScreenerPager
            currentPage={filters.currentPage}
            totalPages={filters.totalPages}
            onPageChange={filters.setCurrentPage}
          />
        </>
      )}

      {activeModalTicker && screenerData?.chart_data?.[activeModalTicker] && (
        <ScreenerModal
          ticker={activeModalTicker}
          data={screenerData.chart_data[activeModalTicker]}
          onClose={() => setActiveModalTicker(null)}
          onNext={handleNextModal}
          onPrev={handlePrevModal}
        />
      )}
    </div>
  );
};

function EmptyState({ message }) {
  return (
    <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>
      {message}
    </div>
  );
}

const gridStyle = {
  display: 'grid',
  gridTemplateColumns: 'repeat(4, minmax(0, 1fr))',
  gap: '14px',
  width: '100%',
};

export default ScreenerGrid;
