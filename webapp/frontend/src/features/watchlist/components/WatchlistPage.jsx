import { useCallback, useEffect, useMemo, useRef, useState, useSyncExternalStore } from 'react';
import useLivePrices from '../hooks/useLivePrices';
import useReviews from '../hooks/useReviews';
import useWatchlist from '../hooks/useWatchlist';
import useWatchlistRecords from '../hooks/useWatchlistRecords';
import { getScreenerPayloads, revalidateScreenerUniverse, subscribeScreenerStore } from '../../../shared/hooks/screenerStore';
import { fetchWatchlist, getWatchlistStatus, restoreWatchlist, subscribeWatchlistStore } from '../hooks/watchlistStore';
import { buildWatchlistRows, sortWatchlistRows } from '../presentation/watchlistTable';
import { resolveRenderedSelection } from '../presentation/watchlistChartData';
import { UNIVERSES } from '../../../shared/presentation/universeSwitcherData';
import { toast } from '../../../shared/components/feedback';
import useDocumentTitle from '../../../shared/hooks/useDocumentTitle';
import { isPageKeystroke } from '../../../shared/navigation/keyboardGuard';
import HoverGlass from '../../../shared/charts/glance/HoverGlass';
import useHoverGlance from '../../../shared/charts/glance/useHoverGlance';
import { artifactGlance, snapshotGlance } from '../../../shared/charts/glance/glanceResolvers';
import WatchlistTable from './WatchlistTable';
import WatchlistChartDialog from './WatchlistChartDialog';
import WeeklyReview from './WeeklyReview';

const SELECTED_KEY = 'wl-selected';
const readSavedSelection = () => {
  try { return sessionStorage.getItem(SELECTED_KEY); } catch { return null; }
};

// One ticker ledger. Charts and historical replay are opened only when requested.
export default function WatchlistPage() {
  const records = useWatchlistRecords();
  const status = useSyncExternalStore(subscribeWatchlistStore, getWatchlistStatus);
  const { watchlist, toggleWatchlist } = useWatchlist();
  const { liked, toggleLiked } = useReviews();
  const { prices, priceErr, priceStatus } = useLivePrices();
  const payloads = useSyncExternalStore(subscribeScreenerStore, getScreenerPayloads);
  const [chosen, setChosen] = useState(readSavedSelection);
  const [search, setSearch] = useState('');
  const [sort, setSort] = useState({ by: 'added', dir: 'desc' });
  const [inspectOpen, setInspectOpen] = useState(false);
  const [reviewOpen, setReviewOpen] = useState(false);
  const pageRef = useRef(null);
  const chartWasOpen = useRef(false);

  useEffect(() => { UNIVERSES.forEach((universe) => revalidateScreenerUniverse(universe.key)); }, []);
  const sources = useMemo(() => {
    const result = {};
    for (const universe of [...UNIVERSES].reverse()) {
      const payload = payloads[universe.key];
      for (const [ticker, entry] of Object.entries(payload?.chart_data || {})) {
        result[ticker] = { entry, scanDate: payload.scan_identity?.scan_date || null };
      }
    }
    for (const record of records) {
      const payload = payloads[record.pin_universe_key];
      const entry = payload?.chart_data?.[record.ticker];
      if (entry) result[record.ticker] = { entry, scanDate: payload.scan_identity?.scan_date || null };
    }
    return result;
  }, [payloads, records]);
  const screenerData = useMemo(() => ({ chart_data: Object.fromEntries(Object.entries(sources).map(([ticker, value]) => [ticker, value.entry])) }), [sources]);
  const rows = useMemo(() => sortWatchlistRows(
    buildWatchlistRows(watchlist, screenerData, { records, prices })
      .filter((row) => row.ticker.toLowerCase().includes(search.trim().toLowerCase())), sort.by, sort.dir),
  [watchlist, screenerData, records, prices, search, sort]);
  const tickers = useMemo(() => rows.map((row) => row.ticker), [rows]);
  const selected = resolveRenderedSelection(chosen, rows);
  const selectedRecord = records.find((record) => record.ticker === selected);
  useDocumentTitle('Watchlist', selected);

  const select = useCallback((ticker) => {
    setChosen(ticker);
    try { sessionStorage.setItem(SELECTED_KEY, ticker); } catch { /* best-effort memory */ }
  }, []);
  const openChart = (ticker) => { select(ticker); setInspectOpen(true); };
  const closeChart = () => setInspectOpen(false);
  const step = (delta) => {
    const index = tickers.indexOf(selected);
    select(tickers[(index + delta + tickers.length) % tickers.length]);
  };

  useEffect(() => {
    const onKey = (event) => {
      if (event.key !== 'ArrowDown' && event.key !== 'ArrowUp') return;
      if (!isPageKeystroke(event)) return;
      if (!tickers.length) return;
      event.preventDefault();
      const index = tickers.indexOf(selected);
      const delta = event.key === 'ArrowDown' ? 1 : -1;
      const next = (index + delta + tickers.length) % tickers.length;
      select(tickers[next]);
      pageRef.current?.querySelector(`tr[data-ticker="${CSS.escape(tickers[next])}"]`)?.focus({ preventScroll: true });
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [tickers, selected, select]);

  // Keep the list position while inspecting; closing lands on the last ticker viewed.
  useEffect(() => {
    if (inspectOpen) { chartWasOpen.current = true; return; }
    const row = pageRef.current?.querySelector('tr[aria-current="true"]');
    row?.scrollIntoView({ block: 'nearest' });
    if (chartWasOpen.current) { chartWasOpen.current = false; row?.focus({ preventScroll: true }); }
  }, [inspectOpen, selected]);

  const remove = (ticker) => {
    const row = records.find((record) => record.ticker === ticker);
    toggleWatchlist(ticker);
    toast(`${ticker} removed from the watchlist`, { action: { label: 'Undo', run: () => restoreWatchlist(ticker,
      row?.pin_universe_key ? { universe: row.pin_universe_key, scanDate: row.pin_scan_date } : null) } });
  };
  const onSort = (by) => setSort((current) => ({ by,
    dir: current.by === by ? (current.dir === 'asc' ? 'desc' : 'asc')
      : ['added', 'grade', 'price', 'saved_price', 'vs_saved', 'rs_rating', 'market_cap'].includes(by) ? 'desc' : 'asc' }));
  const resolveGlance = useCallback((ticker) => sources[ticker]
    ? artifactGlance(screenerData.chart_data, ticker, sources[ticker].scanDate)
    : snapshotGlance(records.find((record) => record.ticker === ticker)?.id, ticker), [sources, screenerData, records]);
  const { glassProps, anchorProps } = useHoverGlance(resolveGlance, { suspended: inspectOpen || reviewOpen });

  return (
    <div className="watchlist-page wl-list-page" ref={pageRef}>
      <header className="wl-list-header">
        <div><h1>Watchlist</h1><span className="wl-list-count">{rows.length} of {records.length} tickers · {rows.filter((row) => row.in_scan).length} in the latest scans</span></div>
        <label className="wl-list-search">Find ticker<input type="search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search watchlist…" /></label>
        <button type="button" className="btn" onClick={() => setReviewOpen(true)}>Review history</button>
      </header>
      <p className="wl-list-note">Click a ticker row for daily, weekly and monthly charts. Saved price is the price in your saved scan; vs saved compares the latest quote with that price.</p>
      {priceStatus === 'loading' && records.length > 0 && <div className="wl-list-note" role="status">Loading quotes…</div>}
      {priceErr && <div className="wl-list-warning" role="status">Quotes could not refresh. Cached quotes and comparisons may be stale.</div>}
      {status === 'error' && <div className="wl-list-warning" role="alert">Couldn’t refresh the watchlist. <button type="button" className="btn btn-sm" onClick={() => fetchWatchlist()}>Retry</button></div>}
      {records.length > 0 ? (
        rows.length ? <WatchlistTable rows={rows} sort={sort} onSort={onSort} selected={selected} onSelect={openChart}
          onRemove={remove} liked={liked} onLike={toggleLiked} anchorProps={anchorProps} priceErr={priceErr} />
          : <div className="wl-list-empty">No saved tickers match this search. <button type="button" className="btn btn-sm" onClick={() => setSearch('')}>Clear search</button></div>
      ) : status === 'ready' ? <div className="wl-list-empty">Star a setup on the screener to add a ticker here. Saved history remains available in Review history.</div>
        : status !== 'error' && <div className="wl-list-empty" role="status">Loading your watchlist…</div>}
      <HoverGlass {...glassProps} />
      {inspectOpen && selectedRecord && <WatchlistChartDialog record={selectedRecord} scan={sources[selected]}
        onClose={closeChart} onNext={tickers.length > 1 ? () => step(1) : undefined} onPrev={tickers.length > 1 ? () => step(-1) : undefined} />}
      <WeeklyReview open={reviewOpen} onClose={() => setReviewOpen(false)} screenerData={payloads.us_stocks} />
    </div>
  );
}
