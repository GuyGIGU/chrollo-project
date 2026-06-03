import { useState } from 'react';
import { TagLegend } from './SetupTags';
import { TAG_CATALOG } from './setupTagsData';

function ScreenerToolbar({
  screenerData,
  isScanning,
  matchedCount,
  watchlistSize,
  filters,
  onRunScan,
}) {
  // Primary triage controls (tier + search) stay always-on; setup, sort, tags,
  // and the legend live behind a disclosure so they don't crowd the grid. The
  // count of active hidden filters keeps that state visible while collapsed.
  const [showMore, setShowMore] = useState(false);
  const advancedCount =
    (filters.setupFilter !== 'ALL' ? 1 : 0) +
    (filters.sortBy !== 'score' ? 1 : 0) +
    filters.tagFilter.size;

  return (
    <>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ color: 'var(--text-muted)' }}>
          {matchedCount} setups matched your constraints.
        </div>
        <button onClick={onRunScan} disabled={isScanning} style={scanButtonStyle(isScanning)}>
          {isScanning ? 'Running Scan...' : 'Run Market Scan Now'}
        </button>
      </div>

      {screenerData && !isScanning && (
        <div style={panelStyle}>
          <FilterRow
            filters={filters}
            watchlistSize={watchlistSize}
            showMore={showMore}
            onToggleMore={() => setShowMore(value => !value)}
            advancedCount={advancedCount}
          />
          {showMore && (
            <>
              <SortRow filters={filters} />
              <TagFilterRow filters={filters} />
              <TagLegend style={{ borderTop: '1px solid var(--border-color)', paddingTop: '10px' }} />
            </>
          )}
        </div>
      )}
    </>
  );
}

function FilterRow({ filters, watchlistSize, showMore, onToggleMore, advancedCount }) {
  return (
    <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
      <span style={filterLabelStyle}>Filter:</span>
      {['ALL', 'S', 'A', 'B', 'C', 'WATCHLIST'].map(tier => (
        <button
          key={tier}
          onClick={() => {
            filters.setTierFilter(tier);
            filters.setCurrentPage(1);
          }}
          style={tierButtonStyle(filters.tierFilter === tier)}
        >
          {tierLabel(tier, watchlistSize)}
        </button>
      ))}
      <input
        type="text"
        placeholder="Search ticker..."
        value={filters.searchTerm}
        onChange={(event) => {
          filters.setSearchTerm(event.target.value);
          filters.setCurrentPage(1);
        }}
        style={searchStyle}
      />
      <button
        onClick={onToggleMore}
        title={showMore ? 'Hide setup, sort, and tag filters' : 'Show setup, sort, and tag filters'}
        style={moreButtonStyle(advancedCount > 0)}
      >
        {showMore
          ? '▾ Filters'
          : advancedCount > 0 ? `▸ Filters · ${advancedCount}` : '▸ Filters'}
      </button>
      {advancedCount > 0 && (
        <button onClick={filters.resetFilters} style={resetStyle}>Reset</button>
      )}
    </div>
  );
}

function SortRow({ filters }) {
  return (
    <div style={{ display: 'flex', gap: '16px', alignItems: 'center', flexWrap: 'wrap' }}>
      <SelectControl
        label="Setup:"
        value={filters.setupFilter}
        onChange={(value) => {
          filters.setSetupFilter(value);
          filters.setCurrentPage(1);
        }}
        options={[['ALL', 'All setups'], ...filters.availableSetups.map(setup => [setup, setup])]}
      />
      <SelectControl
        label="Sort by:"
        value={filters.sortBy}
        onChange={(value) => {
          filters.setSortBy(value);
          filters.setCurrentPage(1);
        }}
        options={[
          ['score', 'Score (high to low)'],
          ['visual', 'Visual score (high to low)'],
          ['market', 'Market score (high to low)'],
          ['base', 'Base age (old to new)'],
          ['trigger', 'Nearest to trigger'],
          ['rs', 'Relative strength'],
        ]}
      />
    </div>
  );
}

function SelectControl({ label, value, options, onChange }) {
  return (
    <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', color: 'var(--text-muted)' }}>
      {label}
      <select value={value} onChange={event => onChange(event.target.value)} style={selectStyle}>
        {options.map(([optionValue, text]) => <option key={optionValue} value={optionValue}>{text}</option>)}
      </select>
    </label>
  );
}

function TagFilterRow({ filters }) {
  if (filters.availableTagIds.size === 0) return null;
  return (
    <div style={{ display: 'flex', gap: '6px', alignItems: 'center', flexWrap: 'wrap' }}>
      <span style={filterLabelStyle}>Tags:</span>
      {TAG_CATALOG.filter(tag => filters.availableTagIds.has(tag.id)).map(tag => {
        const active = filters.tagFilter.has(tag.id);
        return (
          <button
            key={tag.id}
            onClick={() => filters.toggleTagFilter(tag.id)}
            title={active ? 'Click to remove this tag filter' : 'Show only setups carrying this tag'}
            style={tagButtonStyle(active)}
          >
            {tag.label}
          </button>
        );
      })}
    </div>
  );
}

const tierLabel = (tier, watchlistSize) => {
  if (tier === 'ALL') return 'All Tiers';
  if (tier === 'WATCHLIST') return `Watchlist (${watchlistSize})`;
  return `${tier} Tier`;
};

const scanButtonStyle = (isScanning) => ({
  background: isScanning ? 'var(--bg-hover)' : 'var(--accent-blue)',
  color: isScanning ? 'var(--text-muted)' : '#fff',
  border: 'none', padding: '8px 16px', borderRadius: '6px',
  cursor: isScanning ? 'not-allowed' : 'pointer',
  fontWeight: '600', transition: 'all 0.2s', fontFamily: 'inherit',
});

const panelStyle = {
  padding: '10px 16px', background: 'var(--bg-panel)',
  border: '1px solid var(--border-color)',
  borderRadius: '8px', display: 'flex', flexDirection: 'column', gap: '12px',
};

const filterLabelStyle = { fontSize: '12px', color: 'var(--text-muted)', fontWeight: '500', marginRight: '6px' };
const tierButtonStyle = (active) => ({
  padding: '5px 14px', borderRadius: '16px', border: '1px solid',
  borderColor: active ? 'var(--accent-blue)' : 'var(--border-color)',
  background: active ? 'var(--accent-blue)' : 'transparent',
  color: active ? '#fff' : 'var(--text-main)',
  cursor: 'pointer', fontWeight: active ? '600' : '500',
  fontSize: '12px', fontFamily: 'inherit',
});
const searchStyle = {
  marginLeft: 'auto', padding: '5px 14px', borderRadius: '8px',
  border: '1px solid var(--border-color)',
  background: 'var(--bg-main)',
  color: 'var(--text-main)',
  fontSize: '12px', width: '180px', outline: 'none', fontFamily: 'inherit',
};
const selectStyle = {
  padding: '5px 10px', borderRadius: '8px',
  border: '1px solid var(--border-color)',
  background: 'var(--bg-main)',
  color: 'var(--text-main)',
  fontSize: '12px', outline: 'none', cursor: 'pointer', fontFamily: 'inherit',
};
const resetStyle = {
  fontSize: '11px', color: 'var(--text-muted)', background: 'transparent',
  border: '1px solid var(--border-color)',
  borderRadius: '12px', padding: '4px 12px', cursor: 'pointer', fontFamily: 'inherit',
};
// Disclosure for the secondary filters. Goes accent (Signal Blue = active
// selection) only when hidden filters are applied, so a collapsed panel still
// announces "filters active".
const moreButtonStyle = (active) => ({
  fontSize: '11px', fontWeight: 600,
  color: active ? '#fff' : 'var(--text-muted)',
  background: active ? 'var(--accent-blue)' : 'transparent',
  border: `1px solid ${active ? 'var(--accent-blue)' : 'var(--border-color)'}`,
  borderRadius: '12px', padding: '4px 12px', cursor: 'pointer', fontFamily: 'inherit',
});
const tagButtonStyle = (active) => ({
  fontSize: '10px', fontWeight: 700,
  fontFamily: "'JetBrains Mono', monospace",
  padding: '3px 9px', borderRadius: '12px', cursor: 'pointer',
  border: `1px solid ${active ? 'var(--accent-blue)' : 'var(--border-color)'}`,
  background: active ? 'var(--accent-blue)' : 'transparent',
  color: active ? '#fff' : 'var(--text-main)',
});

export default ScreenerToolbar;
