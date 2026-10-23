import Pager from '../../../shared/components/Pager';
import { TAG_CATALOG } from '../../../shared/setup/tagCatalog';
import { RESULT_VIEWS } from '../model/screenerUrlState.js';

// The visible query: every applied filter has one removal action, including
// filters hidden in the popover. Counts refer only to drawable scan charts.
export default function ScreenerViewSummary({ filters, matchedCount, totalCount }) {
  const active = [];
  if (filters.tierFilter !== 'ALL') {
    const label = filters.tierFilter === 'LIKED' ? 'Liked' : `${filters.tierFilter} Tier`;
    active.push({ id: 'tier', label, clear: () => filters.setTierFilter('ALL') });
  }
  if (filters.searchTerm) active.push({ id: 'search', label: `Search: ${filters.searchTerm}`, clear: () => filters.setSearchTerm('') });
  if (filters.setupFilter !== 'ALL') active.push({ id: 'setup', label: filters.setupFilter, clear: () => filters.setSetupFilter('ALL') });
  for (const id of filters.tagFilter) {
    active.push({ id: `tag:${id}`, label: TAG_CATALOG.find((tag) => tag.id === id)?.label || id, clear: () => filters.toggleTagFilter(id) });
  }
  return (
    <div className="screener-view-summary" aria-label="Results and active filters">
      <span role="status" aria-live="polite" className="screener-result-count">{matchedCount} of {totalCount} setups</span>
      {active.map(({ id, label, clear }) => (
        <button key={id} type="button" className="btn btn-sm screener-filter-chip"
          onClick={clear} aria-label={`Remove ${label} filter`} title={`Remove ${label} filter`}>
          {label} <span aria-hidden="true">×</span>
        </button>
      ))}
      {(active.length > 0 || filters.sortBy !== 'score') && (
        <button type="button" className="btn btn-sm" onClick={filters.resetFilters}>Clear filters</button>
      )}
      <div className="screener-page-controls">
        <div className="screener-result-views" role="group" aria-label="Result view">
          {RESULT_VIEWS.map((view) => (
            <button key={view} type="button" className="btn btn-sm"
              aria-pressed={filters.viewMode === view} onClick={() => filters.setViewMode(view)}>
              {view === 'charts' ? 'Charts' : 'Table'}
            </button>
          ))}
        </div>
        <Pager compact page={filters.currentPage} pageCount={filters.totalPages}
          onPage={filters.setCurrentPage} label="Setup pages (top)" />
      </div>
    </div>
  );
}
