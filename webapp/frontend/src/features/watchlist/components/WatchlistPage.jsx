import { useCallback, useEffect, useMemo, useRef, useState, useSyncExternalStore } from 'react';
import useBestGains from '../hooks/useBestGains';
import useLivePrices from '../hooks/useLivePrices';
import useWatchlist from '../hooks/useWatchlist';
import useWatchlistRecords from '../hooks/useWatchlistRecords';
import { usePastWeek, useWatchlistWeeks } from '../hooks/useWatchlistWeeks';
import { getScreenerPayloads, revalidateScreenerUniverse, subscribeScreenerStore } from '../../../shared/hooks/screenerStore';
import { fetchWatchlist, getWatchlistStatus, markWatch, restoreWatchlist, subscribeWatchlistStore } from '../hooks/watchlistStore';
import { buildWatchlistRows, finvizLink, sortWatchlistRows } from '../presentation/watchlistTable';
import { resolveRenderedSelection } from '../presentation/watchlistChartData';
import { UNIVERSES } from '../../../shared/presentation/universeSwitcherData';
import { dayShort } from '../../../shared/setup/fundamentalsSheetRead.js';
import { toast } from '../../../shared/components/feedback';
import useDocumentTitle from '../../../shared/hooks/useDocumentTitle';
import { isPageKeystroke } from '../../../shared/navigation/keyboardGuard';
import HoverGlass from '../../../shared/charts/glance/HoverGlass';
import useHoverGlance from '../../../shared/charts/glance/useHoverGlance';
import { artifactGlance, snapshotGlance } from '../../../shared/charts/glance/glanceResolvers';
import WatchlistTable from './WatchlistTable';
import WatchlistAddBox from './WatchlistAddBox';
import WatchlistChartDialog from './WatchlistChartDialog';
import WeeklyReview from './WeeklyReview';

const SELECTED_KEY = 'wl-selected';
const readSavedSelection = () => {
  try { return sessionStorage.getItem(SELECTED_KEY); } catch { return null; }
};
// Number columns open high-first; 52W distance opens nearest-the-high first.
const DESC_FIRST = ['ready', 'added', 'change', 'diff_since_add', 'best_since_add', 'best_60d', 'best_30d',
  'best_14d', 'best_7d', 'best_2d', 'market_cap', 'rs'];
const recordsKey = (records) => records.map((record) => `${record.ticker}:${record.id}`).sort().join(',');

// The weekly list: this week's names with his marks, last weeks one click back.
// Charts and historical replay are opened only when requested.
export default function WatchlistPage() {
  const records = useWatchlistRecords();
  const status = useSyncExternalStore(subscribeWatchlistStore, getWatchlistStatus);
  const { watchlist, toggleWatchlist } = useWatchlist();
  const thisWeekKey = useMemo(() => recordsKey(records), [records]);
  const weeks = useWatchlistWeeks(thisWeekKey);
  const [week, setWeek] = useState(null); // null = this week
  const pastWeek = week != null && week !== weeks.current ? week : null;
  const past = usePastWeek(pastWeek);
  const shown = pastWeek ? past.records : records;
  const { prices, priceErr, priceStatus } = useLivePrices(useMemo(
    () => past.records.map((record) => record.ticker).join(','), [past.records]));
  // A save's id changes with a re-star, so a new basis refetches too.
  const gains = useBestGains(useMemo(() => recordsKey(shown), [shown]), pastWeek);
  const payloads = useSyncExternalStore(subscribeScreenerStore, getScreenerPayloads);
  const [chosen, setChosen] = useState(readSavedSelection);
  const [search, setSearch] = useState('');
  const [sort, setSort] = useState({ by: 'ready', dir: 'desc' });
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
    for (const record of shown) {
      const payload = payloads[record.pin_universe_key];
      const entry = payload?.chart_data?.[record.ticker];
      if (entry) result[record.ticker] = { entry, scanDate: payload.scan_identity?.scan_date || null };
    }
    return result;
  }, [payloads, shown]);
  const screenerData = useMemo(() => ({ chart_data: Object.fromEntries(Object.entries(sources).map(([ticker, value]) => [ticker, value.entry])) }), [sources]);
  // Which sectors and groups lead, read by the US-stocks scan for every stock it read.
  const leadership = payloads.us_stocks?.market_context?.leadership || null;
  const shownWeek = pastWeek || weeks.current;
  const rows = useMemo(() => sortWatchlistRows(
    buildWatchlistRows(shown.map((record) => record.ticker), screenerData,
      { records: shown, prices, gains, leadership, weekStart: shownWeek })
      .filter((row) => row.ticker.toLowerCase().includes(search.trim().toLowerCase())), sort.by, sort.dir),
  [shown, screenerData, prices, gains, leadership, shownWeek, search, sort]);
  const tickers = useMemo(() => rows.map((row) => row.ticker), [rows]);
  const selected = resolveRenderedSelection(chosen, rows);
  const selectedRecord = shown.find((record) => record.ticker === selected);
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

  // Saves into this week's list, read against the scan on screen; never a toggle-off.
  // False when the name is already on it.
  const addThisWeek = (ticker, side, universe = 'us_stocks') => {
    if (watchlist.has(ticker)) {
      toast(`${ticker} is already on this week's list`);
      return false;
    }
    toggleWatchlist(ticker, { universe, scanDate: payloads[universe]?.scan_identity?.scan_date ?? null, side });
    return true;
  };
  const carryOver = (row) => {
    if (addThisWeek(row.ticker, row.side, row.record?.pin_universe_key || 'us_stocks')) {
      toast(`${row.ticker} carried over to this week`);
    }
  };
  const remove = (ticker) => {
    const row = records.find((record) => record.ticker === ticker);
    toggleWatchlist(ticker);
    toast(`${ticker} removed from the watchlist`, { action: { label: 'Undo', run: () => restoreWatchlist(ticker,
      row?.pin_universe_key ? { universe: row.pin_universe_key, scanDate: row.pin_scan_date } : null) } });
  };
  const onSort = (by) => setSort((current) => ({ by,
    dir: current.by === by ? (current.dir === 'asc' ? 'desc' : 'asc') : DESC_FIRST.includes(by) ? 'desc' : 'asc' }));
  const resolveGlance = useCallback((ticker) => sources[ticker]
    ? artifactGlance(screenerData.chart_data, ticker, sources[ticker].scanDate)
    : snapshotGlance(shown.find((record) => record.ticker === ticker)?.id, ticker), [sources, screenerData, shown]);
  const { glassProps, anchorProps } = useHoverGlance(resolveGlance, { suspended: inspectOpen || reviewOpen });

  // The list as shown, as a Finviz chart page: copied to share, Open from the toast.
  const shareFinviz = () => {
    const link = finvizLink(tickers);
    if (!link) return;
    const open = () => window.open(link, '_blank', 'noopener');
    const copy = navigator.clipboard ? navigator.clipboard.writeText(link) : Promise.reject(new Error('no clipboard'));
    copy
      .then(() => toast(`Finviz link copied: ${tickers.length} tickers`, { action: { label: 'Open', run: open } }))
      .catch(() => toast('The Finviz link could not be copied', { action: { label: 'Open', run: open } }));
  };

  // The switcher walks the weeks newest-first: older is a step right in the list.
  const weekIndex = weeks.weeks.indexOf(shownWeek);
  const olderWeek = weekIndex >= 0 ? weeks.weeks[weekIndex + 1] : weeks.weeks[0];
  const newerWeek = weekIndex > 0 ? weeks.weeks[weekIndex - 1] : null;
  const loading = pastWeek ? past.status === 'loading' : status !== 'ready' && status !== 'error';

  return (
    <div className="watchlist-page wl-list-page" ref={pageRef}>
      <header className="wl-list-header">
        <div><h1>Watchlist</h1><span className="wl-list-count">{rows.length} of {shown.length} tickers · {rows.filter((row) => row.ready === 2).length} ✓✓ · {rows.filter((row) => row.ready === 1).length} ✓</span></div>
        <nav className="wl-week" aria-label="Week">
          <button type="button" className="btn btn-sm" disabled={!olderWeek} onClick={() => setWeek(olderWeek)} aria-label="Older week">‹</button>
          <span className="wl-week-label">{pastWeek ? `Week of ${dayShort(pastWeek)}` : `This week${weeks.current ? ` · ${dayShort(weeks.current)}` : ''}`}</span>
          <button type="button" className="btn btn-sm" disabled={!pastWeek} onClick={() => setWeek(newerWeek === weeks.current ? null : newerWeek)} aria-label="Newer week">›</button>
        </nav>
        {!pastWeek && <WatchlistAddBox onAdd={(ticker, side) => addThisWeek(ticker, side)} />}
        <label className="wl-list-search">Find ticker<input type="search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search watchlist…" /></label>
        <button type="button" className="btn" onClick={shareFinviz} disabled={!tickers.length}
          title="Copy a Finviz link to these tickers' charts, in this order">Finviz link</button>
        <button type="button" className="btn" onClick={() => setReviewOpen(true)}>Review history</button>
      </header>
      <p className="wl-list-note">{pastWeek
        ? 'A past week, as its list ended. Carry over puts a name on this week’s list with a fresh basis.'
        : 'The list starts fresh after Friday’s scan; earlier weeks stay one click back (‹). Click Ready for ✓ (take it on the trigger) or ✓✓ (top of the week), and a row for its charts.'}</p>
      {priceStatus === 'loading' && shown.length > 0 && <div className="wl-list-note" role="status">Loading quotes…</div>}
      {priceErr && <div className="wl-list-warning" role="status">Quotes could not refresh. Change % and % Diff since add may be stale.</div>}
      {!pastWeek && status === 'error' && <div className="wl-list-warning" role="alert">Couldn’t refresh the watchlist. <button type="button" className="btn btn-sm" onClick={() => fetchWatchlist()}>Retry</button></div>}
      {pastWeek && past.status === 'error' && <div className="wl-list-warning" role="alert">Couldn’t load that week.</div>}
      {shown.length > 0 ? (
        rows.length ? <WatchlistTable rows={rows} sort={sort} onSort={onSort} selected={selected} onSelect={openChart}
          onRemove={remove} onMark={markWatch} onCarry={carryOver} pastWeek={Boolean(pastWeek)} thisWeek={watchlist}
          anchorProps={anchorProps} priceErr={priceErr} />
          : <div className="wl-list-empty">No saved tickers match this search. <button type="button" className="btn btn-sm" onClick={() => setSearch('')}>Clear search</button></div>
      ) : loading ? <div className="wl-list-empty" role="status">Loading the list…</div>
        : pastWeek ? <div className="wl-list-empty">Nothing was on that week’s list.</div>
          : status === 'ready' && <div className="wl-list-empty">Nothing on this week’s list yet. Star a setup on the screener or add a ticker above.{olderWeek && <> <button type="button" className="btn btn-sm" onClick={() => setWeek(olderWeek)}>See last week</button></>}</div>}
      <HoverGlass {...glassProps} />
      {inspectOpen && selectedRecord && <WatchlistChartDialog record={selectedRecord} scan={sources[selected]}
        onClose={closeChart} onNext={tickers.length > 1 ? () => step(1) : undefined} onPrev={tickers.length > 1 ? () => step(-1) : undefined} />}
      <WeeklyReview open={reviewOpen} onClose={() => setReviewOpen(false)} screenerData={payloads.us_stocks} />
    </div>
  );
}
