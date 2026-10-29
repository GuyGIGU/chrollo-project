// The screener's filters and page live in the address bar, next to ?u= (universe),
// ?dd= (drill-down) and ?t= (open lens), so a reload, the Back button, a bookmark
// or a URL copied to the second monitor all bring back the same view (operator
// 2026-10-03, "never lose your place"). The params: ?tier= ?setup= ?tag= (one per
// tag id, repeated) ?sort= ?q= (search) ?p= (page). A default value is never
// written, so the bare /screener address IS the default view. Pure: its one import
// is the tier ladder.
import { TIER_LETTERS } from '../../../shared/presentation/wireVocabulary.js';

export const FILTER_DEFAULTS = { tierFilter: 'ALL', setupFilter: 'ALL', sortBy: 'score', searchTerm: '' };

// The command band's tier pills and Sort-by keys (ScreenerToolbar; the test pins the two
// copies together). Any other ?tier= or ?sort= reads as the default: ?tier=a faked
// 'No setups match' with no pill pressed, and ?sort=valueOf crashed the sort.
export const TIER_FILTERS = ['ALL', ...TIER_LETTERS, 'LIKED'];
export const SORT_KEYS = ['score', 'base', 'trigger', 'rs'];
const shownOr = (value, shown, fallback) => (shown.includes(value) ? value : fallback);

export function readFilterParams(params) {
  const page = parseInt(params.get('p'), 10);
  return {
    tierFilter: shownOr(params.get('tier'), TIER_FILTERS, 'ALL'),
    setupFilter: params.get('setup') || 'ALL',
    tagIds: params.getAll('tag'),
    sortBy: shownOr(params.get('sort'), SORT_KEYS, 'score'),
    searchTerm: params.get('q') ?? '',
    page: page > 1 ? page : 1,
  };
}

// Only the keys present; a default value maps to null (= omitted from the URL).
export function filterParamPatch(changes) {
  const patch = {};
  if ('tierFilter' in changes) patch.tier = changes.tierFilter === 'ALL' ? null : changes.tierFilter;
  if ('setupFilter' in changes) patch.setup = changes.setupFilter === 'ALL' ? null : changes.setupFilter;
  if ('sortBy' in changes) patch.sort = changes.sortBy === 'score' ? null : changes.sortBy;
  if ('tagIds' in changes) patch.tag = [...changes.tagIds].sort();   // same set -> same URL
  if ('searchTerm' in changes) patch.q = changes.searchTerm === '' ? null : changes.searchTerm;
  if ('page' in changes) patch.p = changes.page > 1 ? String(changes.page) : null;
  return patch;
}

// A filter change returns to page 1.
export const filterChange = (changes) => filterParamPatch({ ...changes, page: 1 });

// Never mutates its input. An array value replaces every copy of its key.
export function applyParamPatch(search, patch) {
  const next = new URLSearchParams(search);
  for (const [key, value] of Object.entries(patch)) {
    next.delete(key);
    if (Array.isArray(value)) value.forEach((item) => next.append(key, item));
    else if (value != null && value !== '') next.set(key, value);
  }
  return next;
}

// A URL value the controls cannot show is ignored, so yesterday's bookmark cannot fake 'No setups match'.
export function dropUnshownFilters({ setupFilter, tagIds }, availableSetups, availableTagIds) {
  return {
    setupFilter: availableSetups.includes(setupFilter) ? setupFilter : 'ALL',
    tagFilter: new Set(tagIds.filter((id) => availableTagIds.has(id))),
  };
}

// The 1-based page holding list position `index`, or null when it is not in the list.
export const pageForIndex = (index, perPage) => (index < 0 ? null : Math.floor(index / perPage) + 1);

// Opening the lens or a drill-down PUSHES a history entry and tags it with who
// pushed it; closing pops that same entry instead of replacing it. A replace
// left the entry from before the open behind it, so the next Back press
// reverted the page and filters to how they were before the lens opened
// (review 2026-10-03). A replace never drops the tag (see ScreenerGrid's
// patchParams), so cycling the lens or turning a page keeps it.
export const PUSHED_BY_LENS = 'lens';
export const PUSHED_BY_DRILLDOWN = 'drilldown';
export const pushedEntry = (pushedBy) => ({ pushedBy });
// True when the current history entry is the one `pushedBy` opened, so closing
// it is a Back. A deep link or a reload of a copied URL carries no tag and closes
// with a replace, as before.
export const closesByPop = (entryState, pushedBy) => entryState?.pushedBy === pushedBy;
