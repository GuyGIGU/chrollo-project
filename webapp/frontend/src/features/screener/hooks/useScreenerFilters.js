import { useCallback, useMemo, useState } from 'react';
import { buildTagMap, setupTypes, presentTags, filterTickers } from '../model/screenerResults.js';
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
function useScreenerFilters(screenerData, { searchParams, patchParams, liked }) {
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
      liked,
      tagIdsByTicker,
    });
  }, [screenerData, searchTerm, tierFilter, setupFilter, tagFilter, sortBy, liked, tagIdsByTicker]);

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

export default useScreenerFilters;
