import { useState } from 'react';
import { TagLegend } from './SetupTags';
import { TAG_CATALOG } from './setupTagsData';

function ScreenerToolbar({
  screenerData,
  isScanning,
  isEvaluating,
  isDownloading,
  marketDataStatus,
  matchedCount,
  watchlistSize,
  filters,
  onEvaluateCached,
  onDownloadData,
  etfUniverse = false,
}) {
  // The Download/Evaluate actions operate ONLY on the US-Stocks cache; the ETF
  // universes are refreshed by the scheduled daily scan, so these controls are
  // disabled there rather than misleading the user into a no-op (council #14).
  const scanDisabledTitle = etfUniverse
    ? 'Sector/commodity universes refresh on the scheduled daily scan, not from here.'
    : null;
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
        <div style={actionClusterStyle}>
          <MarketDataStatus status={marketDataStatus} />
          <button
            onClick={onDownloadData}
            disabled={isScanning || etfUniverse || marketDataStatus?.can_download === false}
            title={scanDisabledTitle || marketDataStatus?.diagnosis || marketDataStatus?.message || 'Refresh market-data cache'}
            style={downloadButtonStyle(
              isScanning || etfUniverse || marketDataStatus?.can_download === false,
              marketDataStatus?.health_state || marketDataStatus?.status,
              marketDataStatus?.severity,
            )}
          >
            {isDownloading ? 'Downloading Data...' : marketDataStatus?.download_label || 'Download New Data'}
          </button>
          <button
            onClick={onEvaluateCached}
            disabled={isScanning || etfUniverse || marketDataStatus?.can_evaluate === false}
            title={scanDisabledTitle || marketDataStatus?.diagnosis || marketDataStatus?.message || 'Evaluate the current local market-data cache.'}
            style={scanButtonStyle(isScanning || etfUniverse || marketDataStatus?.can_evaluate === false)}
          >
            {isEvaluating ? 'Evaluating Cache...' : 'Evaluate Cached Data'}
          </button>
        </div>
      </div>

      {screenerData && !isEvaluating && (
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

function MarketDataStatus({ status }) {
  if (!status) {
    return (
      <span style={statusStripStyle('loading')} title="Checking market-data cache status.">
        <span style={statusDotStyle('loading')} />
        Checking data...
      </span>
    );
  }
  const state = status.health_state || status.status;
  return (
    <span style={statusStripStyle(state, status.severity)} title={status.diagnosis || status.message}>
      <span style={statusDotStyle(state, status.severity)} />
      {statusLabel(status)}
    </span>
  );
}

function statusLabel(status) {
  const state = status.health_state || status.status;
  if (state === 'healthy' || state === 'market_wait') {
    return `Healthy: ${pct(status.coverage?.eligible?.ratio ?? status.coverage?.ratio)}`;
  }
  if (state === 'needs_repair') return `Repair ${status.missing_summary?.eligible_missing_count ?? ''}`.trim();
  if (state === 'provider_cooldown') return `Provider limited: ${cooldownText(status.retry_seconds)}`;
  if (state === 'symbol_lagging') return 'Needs help';
  if (state === 'shallow_history' || state === 'regime_mismatch') return 'Rebuild data';
  if (state === 'stale_session') return `Stale: ${status.cache_last_session || '-'}`;
  if (state === 'cache_missing') return 'No cache';
  if (state === 'cache_unreadable') return 'Cache unreadable';
  if (state === 'missing_universe') return 'No ticker cache';
  return status.diagnosis || status.message || 'Data status unknown';
}

function cooldownText(seconds) {
  const value = Number(seconds);
  if (!Number.isFinite(value) || value <= 0) return 'soon';
  const minutes = Math.max(1, Math.ceil(value / 60));
  return `${minutes}m`;
}

function pct(value) {
  const num = Number(value);
  if (!Number.isFinite(num)) return '-';
  return `${(num * 100).toFixed(1)}%`;
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
  border: 'none', padding: '8px 16px', borderRadius: 'var(--radius-sm)',
  cursor: isScanning ? 'not-allowed' : 'pointer',
  fontWeight: '600', transition: 'all 0.2s', fontFamily: 'inherit',
});

const downloadButtonStyle = (disabled, status, severity) => ({
  background: disabled ? 'var(--bg-hover)' : downloadColor(status, severity),
  color: disabled ? 'var(--text-muted)' : '#fff',
  border: 'none', padding: '8px 14px', borderRadius: 'var(--radius-sm)',
  cursor: disabled ? 'not-allowed' : 'pointer',
  fontWeight: '600', transition: 'all 0.2s', fontFamily: 'inherit',
  whiteSpace: 'nowrap',
});

const downloadColor = (status, severity) => {
  if (severity === 'repair' || status === 'needs_repair') return 'var(--accent-pink, #bb86fc)';
  if (severity === 'blocked' || status === 'stale_session') return 'var(--danger)';
  return 'var(--accent-blue)';
};

const actionClusterStyle = {
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'flex-end',
  gap: '8px',
  flexWrap: 'wrap',
};

const statusStripStyle = (status, severity) => ({
  alignItems: 'center',
  background: 'var(--bg-panel)',
  border: '1px solid var(--border-color)',
  borderRadius: 'var(--radius-sm)',
  color: severity === 'repair' || status === 'needs_repair'
    ? 'var(--text-main)'
    : 'var(--text-muted)',
  display: 'inline-flex',
  fontSize: '12px',
  fontWeight: 600,
  gap: '7px',
  minHeight: '32px',
  maxWidth: '280px',
  overflow: 'hidden',
  padding: '0 10px',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
});

const statusDotStyle = (status, severity) => ({
  background: statusColor(status, severity),
  borderRadius: '50%',
  display: 'inline-block',
  flex: '0 0 auto',
  height: 7,
  width: 7,
});

const statusColor = (status, severity) => {
  if (severity === 'ok' || status === 'healthy' || status === 'market_wait') return 'var(--success)';
  if (status === 'provider_cooldown') return 'var(--warning, #f2c94c)';
  if (severity === 'repair' || status === 'needs_repair') return 'var(--accent-pink, #bb86fc)';
  if (severity === 'blocked' || status === 'cache_missing' || status === 'cache_unreadable' || status === 'stale_session' || status === 'symbol_lagging') return 'var(--danger)';
  return 'var(--text-muted)';
};

const panelStyle = {
  padding: '10px 16px', background: 'var(--bg-panel)',
  border: '1px solid var(--border-color)',
  borderRadius: 'var(--radius-sm)', display: 'flex', flexDirection: 'column', gap: '12px',
};

const filterLabelStyle = { fontSize: '12px', color: 'var(--text-muted)', fontWeight: '500', marginRight: '6px' };
const tierButtonStyle = (active) => ({
  padding: '5px 14px', borderRadius: 'var(--radius-lg)', border: '1px solid',
  borderColor: active ? 'var(--accent-blue)' : 'var(--border-color)',
  background: active ? 'var(--accent-blue)' : 'transparent',
  color: active ? '#fff' : 'var(--text-main)',
  cursor: 'pointer', fontWeight: active ? '600' : '500',
  fontSize: '12px', fontFamily: 'inherit',
});
const searchStyle = {
  marginLeft: 'auto', padding: '5px 14px', borderRadius: 'var(--radius-sm)',
  border: '1px solid var(--border-color)',
  background: 'var(--bg-main)',
  color: 'var(--text-main)',
  fontSize: '12px', width: '180px', outline: 'none', fontFamily: 'inherit',
};
const selectStyle = {
  padding: '5px 10px', borderRadius: 'var(--radius-sm)',
  border: '1px solid var(--border-color)',
  background: 'var(--bg-main)',
  color: 'var(--text-main)',
  fontSize: '12px', outline: 'none', cursor: 'pointer', fontFamily: 'inherit',
};
const resetStyle = {
  fontSize: '11px', color: 'var(--text-muted)', background: 'transparent',
  border: '1px solid var(--border-color)',
  borderRadius: 'var(--radius-lg)', padding: '4px 12px', cursor: 'pointer', fontFamily: 'inherit',
};
// Disclosure for the secondary filters. Goes accent (Signal Blue = active
// selection) only when hidden filters are applied, so a collapsed panel still
// announces "filters active".
const moreButtonStyle = (active) => ({
  fontSize: '11px', fontWeight: 600,
  color: active ? '#fff' : 'var(--text-muted)',
  background: active ? 'var(--accent-blue)' : 'transparent',
  border: `1px solid ${active ? 'var(--accent-blue)' : 'var(--border-color)'}`,
  borderRadius: 'var(--radius-lg)', padding: '4px 12px', cursor: 'pointer', fontFamily: 'inherit',
});
const tagButtonStyle = (active) => ({
  fontSize: '10px', fontWeight: 700,
  fontFamily: "'JetBrains Mono', monospace",
  padding: '3px 9px', borderRadius: 'var(--radius-lg)', cursor: 'pointer',
  border: `1px solid ${active ? 'var(--accent-blue)' : 'var(--border-color)'}`,
  background: active ? 'var(--accent-blue)' : 'transparent',
  color: active ? '#fff' : 'var(--text-main)',
});

export default ScreenerToolbar;
