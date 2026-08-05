import { useCallback, useEffect, useMemo, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import HealthBoard from './HealthBoard';
import ScreenerCard from './ScreenerCard';
import ScreenerModal from './ScreenerModal';
import ScreenerPager from './ScreenerPager';
import ScreenerScanProgress from './ScreenerScanProgress';
import ScreenerToolbar from './ScreenerToolbar';
import ScreenerWatchlistPanel from './ScreenerWatchlistPanel';
import { universeLabel, isEtfUniverse } from './universeSwitcherData';
import useScanRunner from '../hooks/useScanRunner';
import useReviews from '../hooks/useReviews';
import useScreenerData, { DEFAULT_UNIVERSE } from '../hooks/useScreenerData';
import useScreenerFilters from '../hooks/useScreenerFilters';
import useWatchlist from '../hooks/useWatchlist';
import useDrilldown from '../hooks/useDrilldown';

const ScreenerGrid = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  // The operator's place lives in the URL: ?u= universe, ?dd= drill-down ETF,
  // ?t= open modal ticker — F5 / back-button never lose it.
  const universe = searchParams.get('u') || DEFAULT_UNIVERSE;
  const activeModalTicker = searchParams.get('t');
  const drilldownEtf = searchParams.get('dd');
  const etfUniverse = isEtfUniverse(universe);
  const { watchlist, toggleWatchlist } = useWatchlist();
  const { passed, togglePassed } = useReviews();
  const { screenerData, status, earningsByTicker, fetchScreener, fetchEarnings } = useScreenerData(universe);
  const filters = useScreenerFilters(screenerData, watchlist);
  const scan = useScanRunner(fetchScreener, universe);
  const { drilldown, openDrilldown, closeDrilldown } = useDrilldown();

  // The third render mode. The backend emits `health_board` ONLY for the
  // non-equity universes when HEALTH_BOARD_ENABLED is on; its presence IS the
  // signal to render the board instead of the (empty) firing grid. Flag off ->
  // absent -> the firing grid/empty-state path is byte-identical to today.
  const healthBoard = screenerData?.health_board;
  const showHealthBoard = etfUniverse && Array.isArray(healthBoard?.members);

  // Patch individual params without clobbering the others. Opens PUSH (so the
  // browser Back closes the modal/drill-down); closes and in-modal cycling
  // REPLACE (Back shouldn't walk through every viewed ticker).
  const patchParams = useCallback((patch, { replace = false } = {}) => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      for (const [key, value] of Object.entries(patch)) {
        if (value == null || value === '') next.delete(key);
        else next.set(key, value);
      }
      return next;
    }, { replace });
  }, [setSearchParams]);

  const openModal = useCallback((ticker) => patchParams({ t: ticker }), [patchParams]);
  const cycleModal = useCallback((ticker) => patchParams({ t: ticker }, { replace: true }), [patchParams]);
  const closeModal = useCallback(() => patchParams({ t: null }, { replace: true }), [patchParams]);
  const backToGrid = useCallback(() => patchParams({ dd: null, t: null }, { replace: true }), [patchParams]);

  // The ?dd= param drives the drill-down fetch state, so a reload restores it.
  useEffect(() => {
    if (drilldownEtf) openDrilldown(drilldownEtf);
    else closeDrilldown();
  }, [drilldownEtf, openDrilldown, closeDrilldown]);

  // The board can be long; a drill-down and back must not cost the operator their
  // place (the top-down → bottom-up → back loop). Scroll offset saved when leaving
  // for a drill-down, restored on return. Declared here because BOTH the universe
  // switch (which must clear it) and the drill-down (which saves it) touch it.
  const savedScrollRef = useRef(null);

  // The selected universe lives in the URL (?u=) so it survives reload. Switching
  // resets the page AND the filters (a tag/setup/tier valid in one universe need
  // not exist in another — a stale filter would fake a "no matches" empty state)
  // and drops ?dd=/?t= wholesale, so the switch is never silently masked.
  const handleUniverseChange = (key) => {
    if (key === universe) return;
    filters.resetFilters();
    filters.setCurrentPage(1);
    // Dropping ?dd= here closes any open drill-down; without clearing the saved
    // offset, the restore effect would apply a scroll position captured on the
    // PREVIOUS universe to the freshly-loaded one. Only a real back-to-grid restores.
    savedScrollRef.current = null;
    setSearchParams(key === DEFAULT_UNIVERSE ? {} : { u: key });
  };

  const handleDrilldown = useCallback((etf) => {
    const el = document.querySelector('.content-scroll');
    savedScrollRef.current = el ? el.scrollTop : null;
    patchParams({ dd: etf, t: null });
  }, [patchParams]);

  useEffect(() => {
    if (!drilldown && savedScrollRef.current != null) {
      const el = document.querySelector('.content-scroll');
      if (el) el.scrollTop = savedScrollRef.current;
      savedScrollRef.current = null;
    }
  }, [drilldown]);

  // The modal + arrow-key cycling read the drill-down members when one is open,
  // otherwise the active universe's filtered list.
  const modalChart = drilldown ? (drilldown.chart_data || {}) : (screenerData?.chart_data || {});
  const modalTickers = useMemo(
    () => (drilldown ? (drilldown.ordered_tickers || []) : filters.filteredTickers),
    [drilldown, filters.filteredTickers],
  );

  // Fetch the next-earnings date only for the ticker whose detail lens is open
  // (not the whole page — the card face no longer shows it). The store dedups,
  // so re-opening or cycling back to a ticker is free.
  useEffect(() => {
    if (activeModalTicker) fetchEarnings([activeModalTicker]);
  }, [activeModalTicker, fetchEarnings]);

  const handleNextModal = useCallback(() => {
    if (!activeModalTicker || modalTickers.length === 0) return;
    const currentIndex = modalTickers.indexOf(activeModalTicker);
    const nextIndex = (currentIndex + 1) % modalTickers.length;
    cycleModal(modalTickers[nextIndex]);
  }, [activeModalTicker, modalTickers, cycleModal]);

  const handlePrevModal = useCallback(() => {
    if (!activeModalTicker || modalTickers.length === 0) return;
    const currentIndex = modalTickers.indexOf(activeModalTicker);
    const prevIndex = (currentIndex - 1 + modalTickers.length) % modalTickers.length;
    cycleModal(modalTickers[prevIndex]);
  }, [activeModalTicker, modalTickers, cycleModal]);

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
        closeModal();
      }
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [activeModalTicker, handleNextModal, handlePrevModal, closeModal]);

  return (
    // Screener-only full-bleed: negative margins cancel the content area's 2rem
    // side padding so the chart wall runs edge-to-edge; a small inner padding
    // keeps cards off the very edge. Other tabs keep their padding.
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', margin: '0 -2rem', padding: '0 1rem' }}>
      {/* Main folded the universe switcher INTO the toolbar; the switcher + data
          ops stay live so an ETF universe can always be navigated away from, while
          the filter cluster + "N matched" count are firing-grid concepts that hide
          over the health board (hideFilters) rather than showing a misleading
          0-matched filter row over a full board. */}
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
        etfUniverse={etfUniverse}
        universe={universe}
        onUniverseChange={handleUniverseChange}
        hideFilters={showHealthBoard}
      />
      {isEtfUniverse(universe) && (
        <div style={etfNoteStyle}>
          Breadth is anchored to the broad market — not the ETFs on screen — and breadth-based score components are neutralized for this universe.
        </div>
      )}

      {!showHealthBoard && filters.tierFilter === 'WATCHLIST' && (
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
          onBack={backToGrid}
          onCardClick={openModal}
          watchlist={watchlist}
          toggleWatchlist={toggleWatchlist}
          passed={passed}
          togglePassed={togglePassed}
        />
      ) : showHealthBoard ? (
        <HealthBoard
          board={healthBoard}
          universeLabel={universeLabel(universe)}
          scannedAt={screenerData?.scanned_at}
          onDrilldown={handleDrilldown}
        />
      ) : (!scan.isEvaluating && !scan.scanError && (
        <>
          {status === 'loading' && (
            <EmptyState message={etfUniverse
              ? 'Loading…'
              : 'Loading screener data… (if this takes more than a moment, evaluate the cached data above.)'} />
          )}
          {status === 'error' && (
            <EmptyState message="Couldn't load this screener. Check the backend is running and try again." />
          )}
          {status === 'never_scanned' && (
            <EmptyState message={etfUniverse
              ? `No scan yet for ${universeLabel(universe)}. This universe is refreshed by the scheduled daily scan.`
              : `No scan yet for ${universeLabel(universe)}. Its setups will appear here once a scan has run.`} />
          )}
          {status === 'empty' && (
            <EmptyState message="This scan matched no setups." />
          )}
          {status === 'ready' && filters.paginatedTickers.length === 0 && (
            <EmptyState message="No setups match the current filters." />
          )}
          {status === 'ready' && filters.paginatedTickers.length > 0 && (
            <>
              <div className="screener-grid" style={gridStyle}>
                {filters.paginatedTickers.map(ticker => (
                  <ScreenerCard
                    key={ticker}
                    ticker={ticker}
                    data={screenerData.chart_data[ticker]}
                    watchlisted={watchlist.has(ticker)}
                    onToggleWatchlist={toggleWatchlist}
                    passed={passed.has(ticker)}
                    onTogglePassed={togglePassed}
                    onClick={openModal}
                    onDrilldown={etfUniverse ? handleDrilldown : undefined}
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
          earnings={earningsByTicker[activeModalTicker]}
          // The archive identity's scan-level half, verbatim from the payload
          // (drilldown carries no identity -> the read-verdict control disables
          // honestly rather than guessing a date).
          scanDate={drilldown ? null : (screenerData?.scan_identity?.scan_date ?? null)}
          onClose={closeModal}
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
function DrilldownView({ dd, onBack, onCardClick, watchlist, toggleWatchlist, passed, togglePassed }) {
  const members = dd.ordered_tickers || [];
  const { status, basis } = dd;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
      <div style={lineageHeaderStyle}>
        <button type="button" className="focus-ring" onClick={onBack} style={backButtonStyle}>← Back</button>
        <span style={{ color: 'var(--text-main)', fontWeight: 700, fontSize: 14 }}>{dd.etf}</span>
        <span style={{ color: 'var(--text-faint)', fontSize: 12 }}>
          related US stocks{status === 'loading' ? ' …' : ` · ${members.length}`}
          {' · from the US-Stocks scan'}
        </span>
      </div>
      {status === 'loading' && <EmptyState message="Loading related stocks…" />}
      {status === 'error' && <EmptyState message="Couldn't load related stocks. Go back and try again." />}
      {status === 'empty' && basis === 'none' && <EmptyState message={`No curated stock mapping for ${dd.etf} yet.`} />}
      {status === 'empty' && basis !== 'none' && (
        <EmptyState message={`No ${dd.etf} member stocks set up in today's US-Stocks scan.`} />
      )}
      {status === 'ready' && (
        <div className="screener-grid" style={gridStyle}>
          {members.map(t => (
            <ScreenerCard
              key={t}
              ticker={t}
              data={dd.chart_data[t]}
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
        border: '1px solid rgba(var(--danger-rgb),0.35)',
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
  background: 'var(--accent-active)',
  border: 'none',
  borderRadius: 'var(--radius-sm)',
  color: 'var(--myth-ink)',
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
