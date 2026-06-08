import { useCallback, useEffect, useState } from 'react';
import ScreenerCard from './ScreenerCard';
import MarketRegimeBanner from './MarketRegimeBanner';
import ScreenerModal from './ScreenerModal';
import ScreenerPager from './ScreenerPager';
import ScreenerScanProgress from './ScreenerScanProgress';
import ScreenerToolbar from './ScreenerToolbar';
import ScreenerWatchlistPanel from './ScreenerWatchlistPanel';
import useScanRunner from '../hooks/useScanRunner';
import useReviews from '../hooks/useReviews';
import useScreenerData from '../hooks/useScreenerData';
import useScreenerFilters from '../hooks/useScreenerFilters';
import useWatchlist from '../hooks/useWatchlist';

const ScreenerGrid = () => {
  const [activeModalTicker, setActiveModalTicker] = useState(null);
  const { watchlist, toggleWatchlist } = useWatchlist();
  const { passed, togglePassed } = useReviews();
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
    // Screener-only full-bleed: negative margins cancel the content area's 2rem
    // side padding so the chart wall runs edge-to-edge; a small inner padding
    // keeps cards off the very edge. Other tabs keep their padding.
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', margin: '0 -2rem', padding: '0 1rem' }}>
      <ScreenerToolbar
        screenerData={screenerData}
        isScanning={scan.isScanning}
        matchedCount={filters.filteredTickers.length}
        watchlistSize={watchlist.size}
        filters={filters}
        onRunScan={scan.handleRunScan}
      />

      {screenerData && !scan.isScanning && (
        <MarketRegimeBanner marketContext={screenerData.market_context} />
      )}

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

      {scan.scanError && !scan.isScanning && (
        <ScanErrorBanner message={scan.scanError} onRetry={scan.handleRunScan} />
      )}

      {!hasScreenerData && !scan.isScanning && !scan.scanError && <EmptyState message="Loading Screener Data... (If this takes more than a moment, run a new market scan!)" />}
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
                passed={passed.has(ticker)}
                onTogglePassed={togglePassed}
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

// Shown when a scan stops before results arrive (the EventSource errored). Tells
// the user what happened and offers a one-click retry, instead of stranding them
// on the generic "Loading…" line.
function ScanErrorBanner({ message, onRetry }) {
  return (
    <div
      role="alert"
      style={{
        alignItems: 'center',
        background: 'var(--danger-bg)',
        border: '1px solid rgba(242,103,112,0.35)',
        borderRadius: 'var(--radius-sm)',
        color: 'var(--text-main)',
        display: 'flex',
        gap: '12px',
        justifyContent: 'space-between',
        padding: '12px 16px',
      }}
    >
      <span style={{ fontSize: '13px' }}>
        <strong style={{ color: 'var(--danger)' }}>Scan failed.</strong> {message}
      </span>
      <button onClick={onRetry} style={retryButtonStyle}>Run scan again</button>
    </div>
  );
}

const retryButtonStyle = {
  background: 'var(--accent-blue)',
  border: 'none',
  borderRadius: 'var(--radius-sm)',
  color: '#fff',
  cursor: 'pointer',
  fontFamily: 'inherit',
  fontSize: '12px',
  fontWeight: 600,
  padding: '6px 14px',
  whiteSpace: 'nowrap',
};

const gridStyle = {
  display: 'grid',
  // Responsive "reading room": fit as many spacious ~480px cards as the screen
  // allows and stretch them to fill the row. ~3 per row on a wide monitor, 2 on
  // a laptop — big, readable charts with room to visualize each setup.
  gridTemplateColumns: 'repeat(auto-fill, minmax(480px, 1fr))',
  gap: '14px',
  width: '100%',
};

export default ScreenerGrid;
