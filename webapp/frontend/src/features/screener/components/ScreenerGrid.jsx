import { useCallback, useEffect, useMemo, useRef } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import HealthBoard from './HealthBoard';
import ScreenerCard from '../../../shared/setup/ScreenerCard';
import ScreenerModal from '../../../shared/setup/ScreenerModal';
import Pager from '../../../shared/components/Pager';
import ScreenerScanProgress from './ScreenerScanProgress';
import ScreenerToolbar from './ScreenerToolbar';
import ScreenerViewSummary from './ScreenerViewSummary';
import ScreenerResultsTable from './ScreenerResultsTable';
import WatchLanePanel from './WatchLanePanel';
import { universeLabel, isEtfUniverse } from '../../../shared/presentation/universeSwitcherData';
import useScanRunner from '../hooks/useScanRunner';
import useReviews from '../../watchlist/hooks/useReviews';
import useFixedBoxes from '../../../shared/setup/useFixedBoxes';
import useScreenerData, { DEFAULT_UNIVERSE } from '../../../shared/hooks/useScreenerData';
import useScreenerFilters from '../hooks/useScreenerFilters';
import useWatchlist from '../../watchlist/hooks/useWatchlist';
import useDrilldown from '../hooks/useDrilldown';
import useCardKeyboard from '../hooks/useCardKeyboard';
import useDocumentTitle from '../../../shared/hooks/useDocumentTitle';
import { hasCommandModifier, isTypingTarget } from '../../../shared/navigation/keyboardGuard';
import {
  PUSHED_BY_DRILLDOWN,
  PUSHED_BY_LENS,
  applyParamPatch,
  closesByPop,
  pushedEntry,
} from '../model/screenerUrlState.js';
import { canStepLens, lensPosition, stepTicker } from '../model/lensStepping.js';

const ScreenerGrid = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  // The operator's place lives in the URL: ?u= universe, ?dd= drill-down ETF,
  // ?t= open modal ticker — F5 / back-button never lose it. ?tier= ?setup=
  // ?tag= (repeated) ?sort= ?q= ?p= hold the filters and the page, all written
  // with REPLACE (model/screenerUrlState.js).
  const universe = searchParams.get('u') || DEFAULT_UNIVERSE;
  const activeModalTicker = searchParams.get('t');
  const drilldownEtf = searchParams.get('dd');
  const etfUniverse = isEtfUniverse(universe);
  const { watchlist, toggleWatchlist } = useWatchlist();
  const { liked, toggleLiked, likesStatus, reloadLiked } = useReviews();
  // The charts he fixed on the lens, for the card's glyph; re-read when the lens closes (a fix may have been saved).
  const { fixed: fixedBoxes, refresh: refreshFixedBoxes } = useFixedBoxes();
  const { screenerData, status, refreshFailed, refreshing, earningsByTicker, fetchScreener, fetchEarnings } = useScreenerData(universe);

  const navigate = useNavigate();
  // Opens PUSH a tagged entry (model/screenerUrlState.js); closing pops it; cycling and
  // every filter/page write REPLACE, keeping the entry's tag. Built on the LIVE address
  // bar: react-router 7's setSearchParams updater gets the render-time params, so two
  // writes in one click would undo each other. Side benefit: navigate is stable, so
  // openModal etc. stop changing identity.
  const patchParams = useCallback((patch, { replace = false, state } = {}) => {
    const next = applyParamPatch(window.location.search, patch).toString();
    // react-router keeps an entry's state under history.state.usr; a replace that
    // dropped it would turn a close back into a replace (a duplicate entry).
    const entryState = state !== undefined ? state : (replace ? window.history.state?.usr : undefined);
    navigate({ search: next ? `?${next}` : '' }, { replace, state: entryState });
  }, [navigate]);
  const filters = useScreenerFilters(screenerData, { searchParams, patchParams, liked });
  const likedView = filters.tierFilter === 'LIKED';
  const showResults = status === 'ready' && (!likedView || likesStatus === 'ready');
  const scan = useScanRunner(fetchScreener, universe);
  const { drilldown, openDrilldown, closeDrilldown } = useDrilldown();

  // The third render mode. The backend emits `health_board` ONLY for the
  // non-equity universes when HEALTH_BOARD_ENABLED is on; its presence IS the
  // signal to render the board instead of the (empty) firing grid. Flag off ->
  // absent -> the firing grid/empty-state path is byte-identical to today.
  const healthBoard = screenerData?.health_board;
  const showHealthBoard = etfUniverse && Array.isArray(healthBoard?.members);

  // A star carries the DISPLAYED scan identity so the backend can pin the
  // artifact the operator is actually looking at (EC-37) — and refuse to pin
  // a page the on-disk artifact has moved past. The drill-down shows
  // US-Stocks setups regardless of the page universe, so its stars carry the
  // drill-down payload's own identity.
  const scanDate = screenerData?.scan_identity?.scan_date ?? null;
  const handleToggleWatchlist = useCallback(
    (ticker) => toggleWatchlist(ticker, { universe, scanDate }),
    [toggleWatchlist, universe, scanDate],
  );
  const drilldownScanDate = drilldown?.scan_identity?.scan_date ?? null;
  const handleToggleWatchlistDrilldown = useCallback(
    (ticker) => toggleWatchlist(ticker, { universe: 'us_stocks', scanDate: drilldownScanDate }),
    [toggleWatchlist, drilldownScanDate],
  );

  const openModal = useCallback(
    (ticker) => patchParams({ t: ticker }, { state: pushedEntry(PUSHED_BY_LENS) }),
    [patchParams],
  );
  const cycleModal = useCallback((ticker) => patchParams({ t: ticker }, { replace: true }), [patchParams]);
  const closeModal = useCallback(() => {
    refreshFixedBoxes();
    if (closesByPop(window.history.state?.usr, PUSHED_BY_LENS)) navigate(-1);
    else patchParams({ t: null }, { replace: true });
  }, [navigate, patchParams, refreshFixedBoxes]);
  const backToGrid = useCallback(() => {
    if (closesByPop(window.history.state?.usr, PUSHED_BY_DRILLDOWN)) navigate(-1);
    else patchParams({ dd: null, t: null }, { replace: true });
  }, [navigate, patchParams]);

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
  // PUSHES fresh params, which drops the page AND the filters (a tag/setup/tier
  // valid in one universe need not exist in another — a stale filter would fake a
  // "no matches" empty state) and ?dd=/?t= wholesale, so the switch is never
  // silently masked. No resetFilters() first: that would REPLACE the old
  // universe's history entry with a cleared copy, so Back would return without
  // its filters.
  const handleUniverseChange = (key) => {
    if (key === universe) return;
    // Dropping ?dd= here closes any open drill-down; without clearing the saved
    // offset, the restore effect would apply a scroll position captured on the
    // PREVIOUS universe to the freshly-loaded one. Only a real back-to-grid restores.
    savedScrollRef.current = null;
    setSearchParams(key === DEFAULT_UNIVERSE ? {} : { u: key });
  };

  const handleDrilldown = useCallback((etf) => {
    const el = document.querySelector('.content-scroll');
    savedScrollRef.current = el ? el.scrollTop : null;
    patchParams({ dd: etf, t: null }, { state: pushedEntry(PUSHED_BY_DRILLDOWN) });
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
  const modalChart = useMemo(
    () => (drilldown ? (drilldown.chart_data || {}) : (screenerData?.chart_data || {})),
    [drilldown, screenerData],
  );
  const modalTickers = useMemo(
    () => (drilldown ? (drilldown.ordered_tickers || []) : filters.filteredTickers),
    [drilldown, filters.filteredTickers],
  );
  // The lens on screen, gated exactly like its render and the keydown handler.
  const lensTicker = activeModalTicker && modalChart[activeModalTicker] ? activeModalTicker : null;
  useDocumentTitle('Screener', lensTicker);

  // Fetch the next-earnings date only for the ticker whose detail lens is open
  // (not the whole page — the card face no longer shows it). The store dedups,
  // so re-opening or cycling back to a ticker is free.
  useEffect(() => {
    if (activeModalTicker) fetchEarnings([activeModalTicker]);
  }, [activeModalTicker, fetchEarnings]);

  // The last place the lens ticker had in the list: un-liking it with L in the
  // Liked view drops it from the list while the lens stays open, and Next
  // then lands on the setup that slid into that place (model/lensStepping.js).
  const lensIndexRef = useRef(null);
  useEffect(() => {
    const index = modalTickers.indexOf(activeModalTicker);
    if (index >= 0) lensIndexRef.current = index;
  }, [activeModalTicker, modalTickers]);

  // Prev/Next only when another setup is in the list: one match that is the chart on
  // screen has nowhere to go, so the lens hides the buttons and the arrows stay put too.
  const canStep = canStepLens(modalTickers, activeModalTicker);
  const stepModal = useCallback((delta) => {
    if (!activeModalTicker || !canStep) return;
    const ticker = stepTicker(modalTickers, activeModalTicker, lensIndexRef.current, delta);
    if (ticker) cycleModal(ticker);
  }, [activeModalTicker, canStep, modalTickers, cycleModal]);
  const handleNextModal = useCallback(() => stepModal(1), [stepModal]);
  const handlePrevModal = useCallback(() => stepModal(-1), [stepModal]);

  useEffect(() => {
    const handleKeyDown = (event) => {
      // Gate exactly like the render: a stale ?t= naming a ticker absent from
      // the current chart_data must not keep the arrows armed with no modal
      // on screen (it would hijack keys inside the weekly-review replay).
      if (!activeModalTicker || !modalChart[activeModalTicker]) return;
      // Keys typed into the lens's own "what's off?" box move its caret, never the
      // setup; Alt+Left / Alt+Right stay the browser's Back / Forward.
      if (isTypingTarget(event.target) || hasCommandModifier(event)) return;
      if (event.key === 'ArrowRight' || event.key === 'ArrowDown') {
        event.preventDefault();
        handleNextModal();
      }
      if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') {
        event.preventDefault();
        handlePrevModal();
      }
      // NO Escape here: the lens's own window listener is its one Escape closer.
      // closeModal POPS the entry the open pushed, so a second closer on the same
      // keystroke popped twice and Escape left the Screener for the page before it.
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [activeModalTicker, modalChart, handleNextModal, handlePrevModal]);

  const rootRef = useRef(null);
  useCardKeyboard(rootRef);

  // Closing the lens (X, Escape or Back) lands on the card it last showed. Prev/Next walk the
  // whole filtered list, so go to that card's page first; the next pass lands. Instant scroll
  // (Chromium won't animate under the CSS zoom, see WatchlistPage). The focus is the landing
  // mark: the card's own lock-on, and Enter reopens it. Keyed on the lens DRAWN, not on
  // ?t=: a close that pops back to an address naming a chart the lens cannot draw still lands.
  const lensTickerRef = useRef(null);
  const { currentPage, pageOf, setCurrentPage } = filters;
  useEffect(() => {
    if (lensTicker) {
      lensTickerRef.current = lensTicker;
      return;
    }
    const ticker = lensTickerRef.current;
    if (!ticker) return;
    const page = drilldown ? null : pageOf(ticker);
    if (page != null && page !== currentPage) {
      setCurrentPage(page);
      return;
    }
    lensTickerRef.current = null;
    const escaped = CSS.escape(ticker);
    const card = rootRef.current?.querySelector(`.screener-card[data-ticker="${escaped}"], .screener-result-open[data-ticker="${escaped}"]`);
    if (!card) return;
    card.scrollIntoView({ block: 'nearest' });
    card.focus({ preventScroll: true });
  }, [lensTicker, drilldown, currentPage, pageOf, setCurrentPage]);

  return (
    // Screener-only full-bleed: negative margins cancel the content area's 2rem
    // side padding so the chart wall runs edge-to-edge; a small inner padding
    // keeps cards off the very edge. Other tabs keep their padding.
    <div ref={rootRef} style={{ display: 'flex', flexDirection: 'column', gap: '20px', margin: '0 -2rem', padding: '0 1rem' }}>
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
        likedSize={likesStatus === 'ready'
          ? (screenerData?.ordered_tickers || []).filter((ticker) => screenerData.chart_data[ticker] && liked.has(ticker)).length
          : null}
        filters={filters}
        onEvaluateCached={scan.handleEvaluateCached}
        onDownloadData={scan.handleDownloadData}
        etfUniverse={etfUniverse}
        universe={universe}
        onUniverseChange={handleUniverseChange}
        hideFilters={showHealthBoard}
      />
      {screenerData && refreshFailed && (
        <div className="screener-refresh-warning" role="alert">
          <span>Refresh failed. Showing the last loaded scan for {universeLabel(universe)}.</span>
          <button type="button" className="btn btn-sm" disabled={refreshing}
            onClick={() => fetchScreener(universe)}>{refreshing ? 'Retrying…' : 'Retry refresh'}</button>
        </div>
      )}
      {showResults && !showHealthBoard && !drilldown && (
        <ScreenerViewSummary filters={filters} matchedCount={filters.filteredTickers.length}
          totalCount={Object.keys(screenerData.chart_data || {}).length} />
      )}
      {isEtfUniverse(universe) && (
        <div style={etfNoteStyle}>
          Breadth is anchored to the broad market — not the ETFs on screen — and breadth-based score components are neutralized for this universe.
        </div>
      )}

      <ScreenerScanProgress
        isScanning={scan.isScanning}
        scanProgress={scan.scanProgress}
        scanPhase={scan.scanPhase}
        scanLogs={scan.scanLogs}
        onStop={scan.handleStopJob}
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
          toggleWatchlist={handleToggleWatchlistDrilldown}
          liked={liked}
          toggleLiked={toggleLiked}
        />
      ) : showHealthBoard ? (
        <HealthBoard
          board={healthBoard}
          universeLabel={universeLabel(universe)}
          scannedAt={screenerData?.scanned_at}
          onDrilldown={handleDrilldown}
        />
      ) : (
        // Evaluate keeps the last finished scan on screen, dimmed and inert, until
        // the new one is fetched. A failed run leaves it at full strength under the
        // error banner; a stopped run is not a failure (no banner): it stays dimmed
        // through one re-fetch, then returns at full strength.
        <div style={resultsStyle} className={scan.resultsStale ? 'screener-stale' : undefined} inert={scan.resultsStale}>
          {status === 'loading' && !scan.resultsStale && !scan.scanError && (
            <GridSkeleton hint={etfUniverse ? null : 'If this takes more than a moment, evaluate the cached data above.'} />
          )}
          {status === 'error' && (
            <EmptyState message="Couldn't load this screener. Check the backend is running and try again."
              onRetry={() => fetchScreener(universe)} />
          )}
          {status === 'ready' && likedView && likesStatus === 'loading' && <GridSkeleton />}
          {status === 'ready' && likedView && likesStatus === 'error' && (
            <EmptyState message="Couldn't load your liked setups. Your saved hearts may still be there."
              onRetry={reloadLiked} />
          )}
          {status === 'never_scanned' && (
            <EmptyState message={etfUniverse
              ? `No scan yet for ${universeLabel(universe)}. This universe is refreshed by the scheduled daily scan.`
              : `No scan yet for ${universeLabel(universe)}. Its setups will appear here once a scan has run.`} />
          )}
          {status === 'empty' && (
            <EmptyState message="This scan matched no setups." />
          )}
          {showResults && filters.paginatedTickers.length === 0 && (
            <EmptyState message={likedView && liked.size === 0
              ? 'No liked setups yet. Heart a setup to find it here.'
              : 'No setups match the current filters.'} />
          )}
          {showResults && filters.paginatedTickers.length > 0 && (
            <>
              {filters.viewMode === 'table' ? (
                <ScreenerResultsTable tickers={filters.paginatedTickers} chartData={screenerData.chart_data}
                  watchlist={watchlist} liked={liked} onOpen={openModal}
                  onToggleWatchlist={handleToggleWatchlist} onToggleLike={toggleLiked} />
              ) : <div className="screener-grid" style={gridStyle}>
                {filters.paginatedTickers.map(ticker => (
                  <ScreenerCard
                    key={ticker}
                    ticker={ticker}
                    data={screenerData.chart_data[ticker]}
                    watchlisted={watchlist.has(ticker)}
                    onToggleWatchlist={handleToggleWatchlist}
                    liked={liked.has(ticker)}
                    onToggleLike={toggleLiked}
                    fixed={fixedBoxes.get(ticker) ?? null}
                    onClick={openModal}
                    onDrilldown={etfUniverse ? handleDrilldown : undefined}
                  />
                ))}
              </div>}
              <Pager page={filters.currentPage} pageCount={filters.totalPages} onPage={filters.setCurrentPage} label="Setup pages" />
            </>
          )}
          {/* The watch lane (point 22): apart from the leaderboard, present on
              the wire only once the method flips; nothing renders before. */}
          {(status === 'ready' || status === 'empty') && (
            <WatchLanePanel watch={screenerData?.market_context?.watch} />
          )}
        </div>
      )}

      {activeModalTicker && modalChart[activeModalTicker] && (
        <ScreenerModal
          ticker={activeModalTicker}
          data={modalChart[activeModalTicker]}
          earnings={earningsByTicker[activeModalTicker]}
          // The archive identity, verbatim from the payload — the drilldown
          // response now carries the source artifact's own scan_identity, so
          // the verdict loop stays live in the top-down view too (council
          // review 2026-08-05, finding 4).
          scanIdentity={drilldown ? (drilldown.scan_identity ?? null) : (screenerData?.scan_identity ?? null)}
          onClose={closeModal}
          onNext={canStep ? handleNextModal : undefined}
          onPrev={canStep ? handlePrevModal : undefined}
          // The card's star and heart in the top bar, saving to the same lists
          // (the drill-down's star carries its own scan identity, EC-37).
          watchlisted={watchlist.has(activeModalTicker)}
          onToggleWatchlist={drilldown ? handleToggleWatchlistDrilldown : handleToggleWatchlist}
          liked={liked.has(activeModalTicker)}
          onToggleLike={toggleLiked}
          position={lensPosition(modalTickers, activeModalTicker)}
        />
      )}
    </div>
  );
};

function EmptyState({ message, onRetry, actionLabel = 'Retry' }) {
  return (
    <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>
      {message}
      {onRetry && <div style={{ marginTop: 12 }}><button type="button" className="btn" onClick={onRetry}>{actionLabel}</button></div>}
    </div>
  );
}

// A card-wall-shaped placeholder (the one loading look, shared Skeleton's card form):
// 4 blocks = one row at 2560, 3+1 at 1920. Reuses gridStyle, so no extra copy of the card minimum.
function GridSkeleton({ hint }) {
  return (
    <div role="status" aria-label="Loading setups">
      <div className="screener-grid" style={gridStyle}>
        {[0, 1, 2, 3].map((i) => <div key={i} className="skeleton-block skeleton-card" />)}
      </div>
      {hint && <EmptyState message={hint} />}
    </div>
  );
}

// The drill-down result reads as the SAME instrument, now scoped: the same card
// grid, with one quiet lineage header naming the parent ETF and a way back. The
// hand-off is explicit (these are US-Stocks setups), and the empty states tell
// "no curated mapping" apart from "mapped, but none fired today".
function DrilldownView({ dd, onBack, onCardClick, watchlist, toggleWatchlist, liked, toggleLiked }) {
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
      {status === 'loading' && <GridSkeleton />}
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
              liked={liked.has(t)}
              onToggleLike={toggleLiked}
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
      <button type="button" className="btn btn-primary" onClick={onRetry}>Try again</button>
    </div>
  );
}

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

// Keeps the grid, pager and watch-lane spacing equal to the outer column's gap.
const resultsStyle = { display: 'flex', flexDirection: 'column', gap: '20px' };

const gridStyle = {
  display: 'grid',
  // ONE CARD SIZE ON EVERY SCREEN (operator 2026-10-03, "retain the original size
  // so the scaling looks the same, with the extra monitor space I could just ...
  // see more of the website"): cards of at least 590px stretched to fill the row —
  // three of 618px on his 1920 screen, four of 620px on his 2560 one. It replaces
  // the 2026-10-02 three-card ceiling, which drew three 831px cards at 2560. (A
  // 620px minimum on 2026-09-02 was a different thing: on the 1536px screen he
  // had then it meant TWO wide, short cards, and was put back the same day.) The
  // well is locked to the card's width at --card-chart-aspect, so the same card
  // size is the same setup shape. Keep this in sync with uiScale.CARD_MIN_PX and
  // index.html's pre-paint copy; HealthBoard and .wl-card-grid must match too, or
  // a surface sharing ScreenerMiniChart frames the same window in a different
  // pane. uiScale.test.js pins all five.
  gridTemplateColumns: 'repeat(auto-fill, minmax(590px, 1fr))',
  gap: '14px',
  width: '100%',
};

export default ScreenerGrid;
