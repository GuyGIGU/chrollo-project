import {
  useCallback, useEffect, useMemo, useRef, useState, useSyncExternalStore,
} from 'react';
import useLivePrices from '../hooks/useLivePrices';
import useReviews from '../hooks/useReviews';
import useWatchlist from '../hooks/useWatchlist';
import useWatchlistRecords from '../hooks/useWatchlistRecords';
import {
  getScreenerPayloads, revalidateScreenerUniverse, subscribeScreenerStore,
} from '../../screener/hooks/screenerStore';
import { useCandleEnvelopes, useBatchCells } from '../hooks/useWatchlistCandles';
import {
  fetchBatchCandles, fetchTickerCandles, getBatchCells, revalidateBatchCandles,
} from '../hooks/watchlistCandlesStore';
import {
  fetchWatchlist, getWatchlistStatus, subscribeWatchlistStore,
} from '../hooks/watchlistStore';
import {
  cardPlan, resolvePaneData, resolveRenderedSelection,
} from '../presentation/watchlistChartData';
import { UNIVERSES } from '../../../shared/presentation/universeSwitcherData';
import { fx } from '../../../shared/formatting/format';
import { tierColor } from '../../../shared/presentation/theme';
import { toast } from '../../../shared/components/feedback';
import WatchlistCardGrid from './WatchlistCardGrid';
import WatchlistChartCluster from './WatchlistChartCluster';

// The dedicated Watchlist page: one selected ticker in three panes (Monthly +
// Weekly stacked in a narrow left column, the big Daily pane taking the rest),
// a right-hand ticker rail, and below the fold a full screener-style card grid
// of every starred name (the page scrolls vertically). This shell owns the
// page's SINGLE live-price poller (the Home single-owner mandate) and threads
// the price map down as props; zones never mount their own.
//
// Selection is ONE page-local state slot; the RENDERED selection is derived
// every render (chosen-if-still-listed, else first, else empty) — there is no
// effect that watches the list and "repairs" the selection. The chosen ticker
// survives route bounces within the session.
const SELECTED_KEY = 'wl-selected';

const readSavedSelection = () => {
  try {
    return sessionStorage.getItem(SELECTED_KEY);
  } catch {
    return null;
  }
};

function WatchlistPage() {
  const records = useWatchlistRecords();
  const watchlistStatus = useSyncExternalStore(
    subscribeWatchlistStore, getWatchlistStatus);
  const { watchlist, toggleWatchlist } = useWatchlist();
  const { passed, togglePassed } = useReviews();
  const { prices, priceErr } = useLivePrices();
  const envelopes = useCandleEnvelopes();
  const batchCells = useBatchCells();
  const payloads = useSyncExternalStore(subscribeScreenerStore, getScreenerPayloads);
  const [chosen, setChosen] = useState(readSavedSelection);
  // Page-level and sticky across ticker swaps (never auto-flipped per name);
  // whether the overlay actually DRAWS is derived per ticker in the resolver.
  const [overlayOn, setOverlayOn] = useState(true);
  const pageRef = useRef(null);
  const railRef = useRef(null);

  const selected = resolveRenderedSelection(chosen, records);

  const tickers = useMemo(() => records.map((r) => r.ticker), [records]);

  const pinKeys = useMemo(() => {
    const map = {};
    for (const row of records) {
      if (row.pin_universe_key) map[row.ticker] = row.pin_universe_key;
    }
    return map;
  }, [records]);

  // Selecting ALWAYS re-asks the candle store (in-flight dedup'd; a ready
  // entry serves stale and revalidates in the background) — so the failure
  // pane's "reselect to retry" is a TRUE statement even for the same-ticker
  // reselect React would otherwise bail out of, and an errored card cell is
  // re-asked the moment its name is chosen.
  const select = useCallback((ticker) => {
    setChosen(ticker);
    try {
      sessionStorage.setItem(SELECTED_KEY, ticker);
    } catch {
      /* selection persistence is best-effort */
    }
    fetchTickerCandles(ticker, pinKeys[ticker] || null);
    if (getBatchCells()[ticker]?.status === 'error') {
      revalidateBatchCandles([ticker], pinKeys);
    }
  }, [pinKeys]);

  // A card click happens below the fold — swap the big chart AND bring it
  // back into view, so the click always has a visible result. Instant, not
  // smooth: Chromium won't animate element scrolls under the app's CSS zoom
  // (--ui-scale), so a smooth request silently never moves.
  const selectFromCard = useCallback((ticker) => {
    select(ticker);
    pageRef.current?.scrollTo(0, 0);
  }, [select]);

  // Removal from THIS page consumes the row on screen, so it answers with a
  // toast + Undo (the re-star carries the original pin identity, EC-37); on
  // the screener the same star is safely reversible in place and stays quiet.
  const removeFromPage = useCallback((ticker) => {
    const row = records.find((r) => r.ticker === ticker);
    toggleWatchlist(ticker);
    toast(`${ticker} removed from the watchlist`, {
      action: {
        label: 'Undo',
        run: () => toggleWatchlist(ticker, row?.pin_universe_key
          ? { universe: row.pin_universe_key, scanDate: row.pin_scan_date }
          : null),
      },
    });
  }, [records, toggleWatchlist]);

  // The overlay lookup reads every universe's payload (the two ETF artifacts
  // are small); membership order mirrors the registry's scan order. Summary-
  // first revalidate: a route bounce re-downloads the 30MB artifacts ONLY
  // when a new scan actually landed — an unchanged store keeps every payload
  // reference, so zero charts rebuild on navigation.
  useEffect(() => {
    UNIVERSES.forEach((u) => revalidateScreenerUniverse(u.key));
  }, []);

  const scanSource = useMemo(() => {
    const forTicker = (ticker) => {
      for (const u of UNIVERSES) {
        const payload = payloads[u.key];
        const entry = payload?.chart_data?.[ticker];
        if (entry) {
          return {
            entry,
            scanDate: payload.scan_identity?.scan_date || null,
          };
        }
      }
      return { entry: null, scanDate: null };
    };
    return { forTicker };
  }, [payloads]);

  // Merged ticker->entry map for the card plan, first universe wins.
  const mergedChartData = useMemo(() => {
    const merged = {};
    for (const u of [...UNIVERSES].reverse()) {
      Object.assign(merged, payloads[u.key]?.chart_data || {});
    }
    return merged;
  }, [payloads]);

  // Fetch the selected ticker's envelope (pin-first, EC-37). The fetch is
  // needed even when an artifact exists — toggling the overlay off shows the
  // fresh clean chart without a wait. Every selection change revalidates.
  useEffect(() => {
    if (selected) fetchTickerCandles(selected, pinKeys[selected] || null);
  }, [selected, pinKeys]);

  // The card grid: scan-backed names reuse the scan row client-side,
  // batch-fetch bare candles only for cell-less names (errored cells are
  // NOT in toFetch — retry is select()'s and the mount revalidate's job, so
  // plan→fetch can never loop).
  const grid = useMemo(
    () => cardPlan(tickers, mergedChartData, batchCells),
    [tickers, mergedChartData, batchCells]);
  useEffect(() => {
    if (grid.toFetch.length) fetchBatchCandles(grid.toFetch, pinKeys);
  }, [grid, pinKeys]);

  // Once per route mount: re-ask every batch cell (serving stale meanwhile)
  // so an always-on tab picks up tonight's scan rewrite, and any errored
  // cells from a transient failure get their retry.
  const revalidatedRef = useRef(false);
  useEffect(() => {
    if (revalidatedRef.current || !tickers.length) return;
    revalidatedRef.current = true;
    revalidateBatchCandles(tickers, pinKeys);
  }, [tickers, pinKeys]);

  // Arrow-key traversal — the modal's Prev/Next flip-through, on the rail.
  useEffect(() => {
    const onKey = (event) => {
      if (event.key !== 'ArrowDown' && event.key !== 'ArrowUp') return;
      const target = event.target;
      // Never fight a focused form control or anything inside a dialog
      // surface (the shell's calculator modal floats over this route).
      if (target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA'
        || target.tagName === 'SELECT' || target.isContentEditable
        || target.closest?.('[role="dialog"]'))) return;
      if (!tickers.length) return;
      event.preventDefault();
      const current = resolveRenderedSelection(chosen, records) || tickers[0];
      const index = tickers.indexOf(current);
      const step = event.key === 'ArrowDown' ? 1 : -1;
      select(tickers[(index + step + tickers.length) % tickers.length]);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [tickers, records, chosen, select]);

  // The rail follows the selection: arrow-flipping a long list must not walk
  // the highlight out of the rail's own scroll window.
  useEffect(() => {
    const row = railRef.current?.querySelector('[aria-current]');
    row?.scrollIntoView({ block: 'nearest' });
  }, [selected]);

  // Memoized so the pane bundle keeps a stable reference across unrelated
  // re-renders (the 60s price poll must not rebuild three charts); a
  // selection swap or toggle flip changes an input and rebuilds deliberately.
  const scanFor = useMemo(
    () => scanSource.forTicker(selected), [scanSource, selected]);
  const endpointEntry = envelopes[selected];
  const pane = useMemo(
    () => resolvePaneData({
      scanEntry: scanFor.entry, scanDate: scanFor.scanDate,
      endpointEntry, overlayOn,
    }),
    [scanFor, endpointEntry, overlayOn]);

  if (!records.length) {
    // Three DIFFERENT personalities, never one hint fronting for all: a
    // still-loading list, a failed load (with its retry), and the genuinely
    // empty list (the only one that earns the star hint).
    return (
      <div className="watchlist-page watchlist-page-empty">
        {watchlistStatus === 'error' ? (
          <p className="wl-empty-hint">
            The watchlist could not be loaded — the backend did not answer.
            {' '}
            <button
              className="wl-empty-retry"
              onClick={() => fetchWatchlist()}
              type="button"
            >
              Retry
            </button>
          </p>
        ) : watchlistStatus === 'ready' ? (
          <p className="wl-empty-hint">
            Star a setup — the star on a screener card — to add it here.
          </p>
        ) : (
          <p className="wl-empty-hint">Loading your watchlist…</p>
        )}
      </div>
    );
  }

  return (
    <div className="watchlist-page" ref={pageRef}>
      <div className="wl-top">
        <section
          aria-label="Charts"
          className="wl-chart-zone instrument-tile"
          data-source={pane.source || pane.reason}
        >
          <header className="wl-chart-header">
            <span
              className="wl-chart-ticker"
              // Tier hue is the NAME's identity (scan membership), never the
              // pane artifact's: toggling the overlay off must not strip the
              // rail-matching tier color — a neutral ticker means "the engine
              // has no read on this name", nothing else.
              style={scanFor.entry
                ? { color: tierColor(scanFor.entry.tier) }
                : undefined}
            >
              {selected}
            </span>
            <button
              aria-pressed={overlayOn}
              className={`wl-overlay-toggle${overlayOn && !pane.overlayAvailable ? ' inert' : ''}`}
              onClick={() => setOverlayOn((on) => !on)}
              type="button"
            >
              Engine read
            </button>
            {overlayOn && !pane.overlayAvailable && (
              <span className="wl-toggle-note">
                no engine read for this name — price and volume only
              </span>
            )}
            <span className="wl-chart-stamp">
              {pane.source === 'scan' && (
                `AS SCANNED ${pane.provenance.scanDate || '—'} · last session ${
                  pane.daily.candles?.length
                    ? pane.daily.candles[pane.daily.candles.length - 1].time
                    : '—'}`
              )}
              {pane.source === 'endpoint' && (
                `LAST SESSION ${pane.provenance.lastBarDate || '—'}${
                  pane.provenance.forming.monthly ? ' · month forming' : ''}${
                  pane.provenance.forming.weekly ? ' · week forming' : ''}`
              )}
            </span>
          </header>
          <WatchlistChartCluster pane={pane} ticker={selected} />
        </section>
        <aside aria-label="Watchlist tickers" className="wl-rail instrument-tile" ref={railRef}>
          {records.map((row) => (
            <div
              aria-current={row.ticker === selected || undefined}
              className={`wl-rail-row${row.ticker === selected ? ' selected' : ''}`}
              key={row.ticker}
              onClick={() => select(row.ticker)}
              onKeyDown={(event) => {
                if (event.key === 'Enter' || event.key === ' ') {
                  event.preventDefault();
                  select(row.ticker);
                }
              }}
              role="button"
              tabIndex={0}
            >
              <span
                className="wl-rail-ticker"
                style={mergedChartData[row.ticker]
                  ? { color: tierColor(mergedChartData[row.ticker].tier) }
                  : undefined}
              >
                {row.ticker}
              </span>
              <span className={`wl-rail-price${priceErr ? ' stale' : ''}`}>
                {fx(prices[row.ticker])}
              </span>
            </div>
          ))}
        </aside>
      </div>
      <section aria-label="Watchlist charts" className="wl-grid-zone">
        <div className="wl-grid-head">
          <span>WATCHLIST CHARTS</span>
          <span className="wl-grid-count">{tickers.length}</span>
        </div>
        <WatchlistCardGrid
          cards={grid.cards}
          onSelect={selectFromCard}
          onTogglePassed={togglePassed}
          onToggleWatchlist={removeFromPage}
          passed={passed}
          selected={selected}
          tickers={tickers}
          watchlist={watchlist}
        />
      </section>
    </div>
  );
}

export default WatchlistPage;
