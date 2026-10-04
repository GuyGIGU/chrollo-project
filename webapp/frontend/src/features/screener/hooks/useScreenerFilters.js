import { useCallback, useMemo, useState } from 'react';
import { resolveTags } from '../../../shared/setup/tagResolver';
import { triggerDistanceFrac } from '../../../shared/setup/triggerProximity';
import {
  FILTER_DEFAULTS,
  dropUnshownFilters,
  filterChange,
  filterParamPatch,
  pageForIndex,
  readFilterParams,
} from '../model/screenerUrlState.js';

const ITEMS_PER_PAGE = 24;

// The filters and the page live in the URL (model/screenerUrlState.js); the grid
// owns the address bar and hands in its params plus the one writer.
function useScreenerFilters(screenerData, watchlist, { searchParams, patchParams }) {
  const url = useMemo(() => readFilterParams(searchParams), [searchParams]);
  // BrowserRouter applies URL changes in a transition, and a text box fed from a
  // transition drops keystrokes. So the box shows what was typed while the LIVE
  // address bar still says it; Back, a universe switch or Reset changes the
  // address bar and wins.
  const [typed, setTyped] = useState(url.searchTerm);
  const liveSearch = new URLSearchParams(window.location.search).get('q') ?? '';
  const searchTerm = typed === liveSearch ? typed : url.searchTerm;

  const tagIdsByTicker = useMemo(() => buildTagMap(screenerData), [screenerData]);
  const availableSetups = useMemo(() => setupTypes(screenerData), [screenerData]);
  const availableTagIds = useMemo(() => presentTags(tagIdsByTicker), [tagIdsByTicker]);
  const { setupFilter, tagFilter } = useMemo(
    () => dropUnshownFilters(url, availableSetups, availableTagIds),
    [url, availableSetups, availableTagIds],
  );
  const { tierFilter, sortBy } = url;
  const filteredTickers = useMemo(() => {
    return filterTickers({
      screenerData,
      searchTerm,
      tierFilter,
      setupFilter,
      tagFilter,
      sortBy,
      watchlist,
      tagIdsByTicker,
    });
  }, [screenerData, searchTerm, tierFilter, setupFilter, tagFilter, sortBy, watchlist, tagIdsByTicker]);

  const totalPages = Math.max(1, Math.ceil(filteredTickers.length / ITEMS_PER_PAGE));
  // Clamped at render, never written back: a restored ?p= must survive the renders before the scan loads.
  const currentPage = Math.min(url.page, totalPages);
  const paginatedTickers = filteredTickers.slice(
    (currentPage - 1) * ITEMS_PER_PAGE,
    currentPage * ITEMS_PER_PAGE,
  );

  // Every write REPLACES the history entry: Back leaves the screener (or closes
  // the lens), it never undoes a filter. A filter change returns to page 1.
  const write = useCallback((changes) => patchParams(filterChange(changes), { replace: true }), [patchParams]);
  const setSearchTerm = useCallback((term) => {
    setTyped(term);
    write({ searchTerm: term });
  }, [write]);
  const setTierFilter = useCallback((value) => write({ tierFilter: value }), [write]);
  const setSetupFilter = useCallback((value) => write({ setupFilter: value }), [write]);
  const setSortBy = useCallback((value) => write({ sortBy: value }), [write]);
  const setCurrentPage = useCallback(
    (page) => patchParams(filterParamPatch({ page }), { replace: true }),
    [patchParams],
  );

  const toggleTagFilter = useCallback((id) => {
    const next = new Set(tagFilter);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    write({ tagIds: next });
  }, [tagFilter, write]);

  const resetFilters = useCallback(() => {
    setTyped('');
    write({ ...FILTER_DEFAULTS, tagIds: [] });
  }, [write]);

  // The page a ticker sits on in the filtered list (null when filtered out).
  const pageOf = useCallback(
    (ticker) => pageForIndex(filteredTickers.indexOf(ticker), ITEMS_PER_PAGE),
    [filteredTickers],
  );

  return {
    searchTerm,
    setSearchTerm,
    tierFilter,
    setTierFilter,
    setupFilter,
    setSetupFilter,
    tagFilter,
    sortBy,
    setSortBy,
    currentPage,
    setCurrentPage,
    availableSetups,
    availableTagIds,
    filteredTickers,
    paginatedTickers,
    totalPages,
    toggleTagFilter,
    resetFilters,
    pageOf,
  };
}

function buildTagMap(screenerData) {
  const map = {};
  if (!screenerData?.chart_data) return map;
  for (const [ticker, data] of Object.entries(screenerData.chart_data)) {
    // The SAME resolver the cards render from (task 11) — the filter bar is
    // structurally incapable of disagreeing with the chips the grid shows.
    const tags = resolveTags(data);
    map[ticker] = new Set(tags.map(tag => tag.id));
  }
  return map;
}

function setupTypes(screenerData) {
  if (!screenerData?.chart_data) return [];
  return Array.from(new Set(
    Object.values(screenerData.chart_data)
      .map(data => data.setup)
      .filter(Boolean),
  )).sort();
}

function presentTags(tagIdsByTicker) {
  const seen = new Set();
  for (const ids of Object.values(tagIdsByTicker)) {
    ids.forEach(id => seen.add(id));
  }
  return seen;
}

function filterTickers(options) {
  const { screenerData, tierFilter, tagFilter, watchlist, tagIdsByTicker } = options;
  if (!screenerData?.ordered_tickers) return [];

  const matched = screenerData.ordered_tickers.filter(ticker => {
    const data = screenerData.chart_data[ticker];
    if (!data) return false;
    return tickerMatches(ticker, data, options)
      && tagsMatch(tagFilter, tagIdsByTicker[ticker] || new Set())
      && (tierFilter !== 'WATCHLIST' || watchlist.has(ticker));
  });
  return sortTickers(matched, options.sortBy, screenerData.chart_data);
}

function tickerMatches(ticker, data, { searchTerm, tierFilter, setupFilter }) {
  const matchesSearch = ticker.toLowerCase().includes(searchTerm.toLowerCase());
  const matchesTier = tierFilter === 'ALL' || tierFilter === 'WATCHLIST' || data.tier === tierFilter;
  const matchesSetup = setupFilter === 'ALL' || data.setup === setupFilter;
  return matchesSearch && matchesTier && matchesSetup;
}

function tagsMatch(tagFilter, tagIds) {
  return tagFilter.size === 0 || Array.from(tagFilter).every(id => tagIds.has(id));
}

function sortTickers(tickers, sortBy, chartData) {
  if (sortBy === 'score') return tickers;
  const sorted = [...tickers];
  const sorters = {
    base: (a, b) => (chartData[b].base_len || 0) - (chartData[a].base_len || 0),
    trigger: (a, b) => distanceToTrigger(chartData[a]) - distanceToTrigger(chartData[b]),
  };
  return sorted.sort(sorters[sortBy] || (() => 0));
}

const distanceToTrigger = data => {
  const frac = triggerDistanceFrac(data, data?.price);
  return frac == null ? Infinity : frac;
};

export default useScreenerFilters;
