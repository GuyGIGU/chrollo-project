import { useCallback, useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import ScreenerCard from './ScreenerCard';
import MarketRegimeBanner from './MarketRegimeBanner';
import ScreenerModal from './ScreenerModal';
import ScreenerPager from './ScreenerPager';
import ScreenerScanProgress from './ScreenerScanProgress';
import ScreenerToolbar from './ScreenerToolbar';
import ScreenerWatchlistPanel from './ScreenerWatchlistPanel';
import UniverseSwitcher, { universeLabel, isEtfUniverse } from './UniverseSwitcher';
import useScanRunner from '../hooks/useScanRunner';
import useReviews from '../hooks/useReviews';
import useScreenerData, { DEFAULT_UNIVERSE } from '../hooks/useScreenerData';
import useScreenerFilters from '../hooks/useScreenerFilters';
import useWatchlist from '../hooks/useWatchlist';
import { API_BASE } from '../api';

const ScreenerGrid = () => {
  const [activeModalTicker, setActiveModalTicker] = useState(null);
  const [searchParams, setSearchParams] = useSearchParams();
  const universe = searchParams.get('u') || DEFAULT_UNIVERSE;
  const { watchlist, toggleWatchlist } = useWatchlist();
  const { passed, togglePassed } = useReviews();
  const { screenerData, status, earningsByTicker, fetchScreener, fetchEarnings } = useScreenerData(universe);
  const filters = useScreenerFilters(screenerData, watchlist);
  const scan = useScanRunner(fetchScreener);

  // The selected universe lives in the URL (?u=) so it survives reload and any
  // deep link agrees with what's on screen. Switching resets to page 1.
  const handleUniverseChange = (key) => {
    setSearchParams(key === DEFAULT_UNIVERSE ? {} : { u: key });
    filters.setCurrentPage(1);
  };

  // Top-down drill-down: a firing sector/commodity ETF -> its related US-stock
  // setups (resolved server-side, intersected with the latest US-Stocks scan).
  const [drilldown, setDrilldown] = useState(null);
  const openDrilldown = useCallback((etf) => {
    setActiveModalTicker(null);
    setDrilldown({ etf, loading: true, ordered_tickers: [], chart_data: {} });
    fetch(`${API_BASE}/screener-data/drilldown/?etf=${encodeURIComponent(etf)}`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error('drilldown'))))
      .then((d) => setDrilldown({ ...d, loading: false }))
      .catch(() => setDrilldown({ etf, basis: 'error', ordered_tickers: [], chart_data: {}, loading: false }));
  }, []);
  const closeDrilldown = useCallback(() => { setDrilldown(null); setActiveModalTicker(null); }, []);

  // The modal + arrow-key cycling read from the drill-down members when one is
  // open, otherwise from the active universe's filtered list.
  const modalChart = drilldown ? (drilldown.chart_data || {}) : (screenerData?.chart_data || {});
  const modalTickers = drilldown ? (drilldown.ordered_tickers || []) : filters.filteredTickers;

  useEffect(() => {
    fetchEarnings(filters.paginatedTickers);
  }, [fetchEarnings, filters.paginatedTickers]);

  const handleNextModal = useCallback(() => {
    if (!activeModalTicker || modalTickers.length === 0) return;
    const currentIndex = modalTickers.indexOf(activeModalTicker);
    const nextIndex = (currentIndex + 1) % modalTickers.length;
    setActiveModalTicker(modalTickers[nextIndex]);
  }, [activeModalTicker, modalTickers]);

  const handlePrevModal = useCallback(() => {
    if (!activeModalTicker || modalTickers.length === 0) return;
    const currentIndex = modalTickers.indexOf(activeModalTicker);
    const prevIndex = (currentIndex - 1 + modalTickers.length) % modalTickers.length;
    setActiveModalTicker(modalTickers[prevIndex]);
  }, [activeModalTicker, modalTickers]);

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
      <UniverseSwitcher universe={universe} onChange={handleUniverseChange} />
      {isEtfUniverse(universe) && (
        <div style={etfNoteStyle}>
          Breadth is anchored to the broad market — not the ETFs on screen — and breadth-based score components are neutralized for this universe.
        </div>
      )}

      <ScreenerToolbar
        screenerData={screenerData}
        isScanning={scan.isScanning}
        isEvaluating={scan.isEvaluating}
        isDownloading={scan.isDownloading}
        marketDataStatus={scan.marketDataStatus}
        matchedCount={filters.filteredTickers.length}
        watchlistSize={watchlist.size}
        filters={filters}
        onEvaluateCached={scan.handleEvaluateCached}
        onDownloadData={scan.handleDownloadData}
      />

      {screenerData && !scan.isEvaluating && (
        <MarketRegimeBanner marketContext={screenerData.market_context} />
      )}

      {filters.tierFilter === 'WATCHLIST' && (
        <ScreenerWatchlistPanel
          watchlist={watchlist}
          screenerData={screenerData}
          isScanning={scan.isEvaluating}
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
        <ScanErrorBanner message={scan.scanError} onRetry={scan.handleRetryLastJob} />
      )}

      {drilldown ? (
        <DrilldownView
          dd={drilldown}
          onBack={closeDrilldown}
          onCardClick={setActiveModalTicker}
          watchlist={watchlist}
          toggleWatchlist={toggleWatchlist}
          passed={passed}
          togglePassed={togglePassed}
          earningsByTicker={earningsByTicker}
        />
      ) : (!scan.isEvaluating && !scan.scanError && (
        <>
          {status === 'loading' && (
            <EmptyState message="Loading screener data… (if this takes more than a moment, evaluate the cached data above.)" />
          )}
          {status === 'error' && (
            <EmptyState message="Couldn't load this screener. Check the backend is running and try again." />
          )}
          {status === 'never_scanned' && (
            <EmptyState message={`No scan yet for ${universeLabel(universe)}. Its setups will appear here once a scan has run for this universe.`} />
          )}
          {status === 'empty' && (
            <EmptyState message="This scan matched no setups." />
          )}
          {status === 'ready' && filters.paginatedTickers.length === 0 && (
            <EmptyState message="No setups match the current filters." />
          )}
          {status === 'ready' && filters.paginatedTickers.length > 0 && (
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
                    onDrilldown={isEtfUniverse(universe) ? openDrilldown : undefined}
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
        </>
      ))}

      {activeModalTicker && modalChart[activeModalTicker] && (
        <ScreenerModal
          ticker={activeModalTicker}
          data={modalChart[activeModalTicker]}
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

// The drill-down result reads as the SAME instrument, now scoped: the same card
// grid, with one quiet lineage header naming the parent ETF and a way back. The
// hand-off is explicit (these are US-Stocks setups), and the empty states tell
// "no curated mapping" apart from "mapped, but none fired today".
function DrilldownView({ dd, onBack, onCardClick, watchlist, toggleWatchlist, passed, togglePassed, earningsByTicker }) {
  const members = dd.ordered_tickers || [];
  const showGrid = !dd.loading && dd.basis !== 'error' && dd.basis !== 'none' && members.length > 0;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
      <div style={lineageHeaderStyle}>
        <button type="button" onClick={onBack} style={backButtonStyle}>← Back</button>
        <span style={{ color: 'var(--text-main)', fontWeight: 700, fontSize: 14 }}>{dd.etf}</span>
        <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>
          related US stocks{dd.loading ? ' …' : ` · ${members.length}`}
          <span style={{ opacity: 0.7 }}> · from the US-Stocks scan</span>
        </span>
      </div>
      {dd.loading && <EmptyState message="Loading related stocks…" />}
      {!dd.loading && dd.basis === 'error' && <EmptyState message="Couldn't load related stocks. Go back and try again." />}
      {!dd.loading && dd.basis === 'none' && <EmptyState message={`No curated stock mapping for ${dd.etf} yet.`} />}
      {!dd.loading && (dd.basis === 'sector' || dd.basis === 'commodity') && members.length === 0 && (
        <EmptyState message={`No ${dd.etf} member stocks set up in today's US-Stocks scan.`} />
      )}
      {showGrid && (
        <div style={gridStyle}>
          {members.map(t => (
            <ScreenerCard
              key={t}
              ticker={t}
              data={dd.chart_data[t]}
              earnings={earningsByTicker[t]}
              watchlisted={watchlist.has(t)}
              onToggleWatchlist={toggleWatchlist}
              passed={passed.has(t)}
              onTogglePassed={togglePassed}
              onClick={onCardClick}
            />
          ))}
        </div>
      )}
    </div>
  );
}

const lineageHeaderStyle = {
  alignItems: 'center',
  background: 'var(--bg-panel)',
  border: '1px solid var(--border-color)',
  borderRadius: 'var(--radius-sm)',
  display: 'flex',
  gap: '10px',
  padding: '10px 14px',
  flexWrap: 'wrap',
};

const backButtonStyle = {
  background: 'transparent',
  border: '1px solid var(--border-color)',
  borderRadius: 'var(--radius-lg)',
  color: 'var(--text-main)',
  cursor: 'pointer',
  fontFamily: 'inherit',
  fontSize: 12,
  padding: '4px 12px',
};

// Shown when a data job (evaluation or download) stops before it finishes (the
// EventSource errored or the backend reported ERROR). Tells the user what
// happened and offers a one-click retry of the last job, instead of stranding
// them on the generic "Loading…" line.
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
        <strong style={{ color: 'var(--danger)' }}>Action failed.</strong> {message}
      </span>
      <button onClick={onRetry} style={retryButtonStyle}>Try again</button>
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

// Honest-instrument note for the ETF universes: the regime/breadth on screen is
// borrowed from the broad market, not measured over the handful of ETFs.
const etfNoteStyle = {
  fontSize: '12px',
  color: 'var(--text-muted)',
  background: 'var(--bg-panel)',
  border: '1px solid var(--border-color)',
  borderRadius: 'var(--radius-sm)',
  padding: '8px 12px',
  marginTop: '-8px',
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
