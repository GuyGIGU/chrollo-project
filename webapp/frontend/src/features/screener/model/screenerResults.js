// Pure selection over the published scan: preserves engine rank unless a display sort is chosen.
import { resolveTags } from '../../../shared/setup/tagResolver.js';
import { triggerDistanceFrac } from '../../../shared/setup/triggerProximity.js';
import { finiteOrNull, numAsc } from '../../../shared/formatting/format.js';

export function buildTagMap(screenerData) {
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

export function setupTypes(screenerData) {
  if (!screenerData?.chart_data) return [];
  return Array.from(new Set(
    Object.values(screenerData.chart_data)
      .map(data => data.setup)
      .filter(Boolean),
  )).sort();
}

export function presentTags(tagIdsByTicker) {
  const seen = new Set();
  for (const ids of Object.values(tagIdsByTicker)) {
    ids.forEach(id => seen.add(id));
  }
  return seen;
}

export function filterTickers(options) {
  const { screenerData, tierFilter, tagFilter, liked, tagIdsByTicker } = options;
  if (!screenerData?.ordered_tickers) return [];

  const matched = screenerData.ordered_tickers.filter(ticker => {
    const data = screenerData.chart_data[ticker];
    if (!data) return false;
    return tickerMatches(ticker, data, options)
      && tagsMatch(tagFilter, tagIdsByTicker[ticker] || new Set())
      && (tierFilter !== 'LIKED' || liked.has(ticker));
  });
  return sortTickers(matched, options.sortBy, screenerData.chart_data);
}

function tickerMatches(ticker, data, { searchTerm, tierFilter, setupFilter }) {
  const matchesSearch = ticker.toLowerCase().includes(searchTerm.toLowerCase());
  const matchesTier = ['ALL', 'LIKED'].includes(tierFilter) || data.tier === tierFilter;
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
    // Strongest first; an unrated stock sinks, and ties keep the grade order.
    rs: (a, b) => numAsc(finiteOrNull(chartData[b].rs_rating), finiteOrNull(chartData[a].rs_rating)),
  };
  return sorted.sort(sorters[sortBy] || (() => 0));
}

const distanceToTrigger = data => {
  const frac = triggerDistanceFrac(data, data?.price);
  return frac == null ? Infinity : frac;
};
