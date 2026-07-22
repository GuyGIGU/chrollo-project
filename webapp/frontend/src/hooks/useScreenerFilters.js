import { useCallback, useEffect, useMemo, useState } from 'react';
import { deriveScoreBreakdown } from '../components/setupScoreMath';
import { deriveTags } from '../components/setupTagsData';
import { tagFlagsFromWire } from '../components/wireVocabulary';

const ITEMS_PER_PAGE = 24;

function useScreenerFilters(screenerData, watchlist) {
  const [searchTerm, setSearchTerm] = useState('');
  const [tierFilter, setTierFilter] = useState('ALL');
  const [setupFilter, setSetupFilter] = useState('ALL');
  const [tagFilter, setTagFilter] = useState(() => new Set());
  const [sortBy, setSortBy] = useState('score');
  const [currentPage, setCurrentPage] = useState(1);

  const tagIdsByTicker = useMemo(() => buildTagMap(screenerData), [screenerData]);
  const availableSetups = useMemo(() => setupTypes(screenerData), [screenerData]);
  const availableTagIds = useMemo(() => presentTags(tagIdsByTicker), [tagIdsByTicker]);
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
  const paginatedTickers = filteredTickers.slice(
    (currentPage - 1) * ITEMS_PER_PAGE,
    currentPage * ITEMS_PER_PAGE,
  );

  useEffect(() => {
    if (currentPage > totalPages) setCurrentPage(1);
  }, [currentPage, totalPages]);

  const toggleTagFilter = useCallback((id) => {
    setTagFilter(previous => {
      const next = new Set(previous);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
    setCurrentPage(1);
  }, []);

  const resetFilters = () => {
    setSearchTerm('');
    setTierFilter('ALL');
    setSetupFilter('ALL');
    setTagFilter(new Set());
    setSortBy('score');
    setCurrentPage(1);
  };

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
  };
}

function buildTagMap(screenerData) {
  const map = {};
  if (!screenerData?.chart_data) return map;
  for (const [ticker, data] of Object.entries(screenerData.chart_data)) {
    const tags = deriveTags(data.sub_scores, tagFlagsFromWire(data));
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
    visual: (a, b) => visualScore(chartData[b]) - visualScore(chartData[a]),
    market: (a, b) => marketScore(chartData[b]) - marketScore(chartData[a]),
    base: (a, b) => (chartData[b].base_len || 0) - (chartData[a].base_len || 0),
    trigger: (a, b) => distanceToTrigger(chartData[a]) - distanceToTrigger(chartData[b]),
    rs: (a, b) => (chartData[b].sub_scores?.rs_bonus || 0) - (chartData[a].sub_scores?.rs_bonus || 0),
  };
  return sorted.sort(sorters[sortBy] || (() => 0));
}

const visualScore = data => deriveScoreBreakdown(data.sub_scores).visual.score || 0;
const marketScore = data => deriveScoreBreakdown(data.sub_scores).market.score || 0;
const distanceToTrigger = data => (
  data?.trigger && data?.price ? (data.trigger - data.price) / data.price : Infinity
);

export default useScreenerFilters;
