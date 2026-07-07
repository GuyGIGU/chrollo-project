import { TagLegend } from './SetupTags';
import { TAG_CATALOG } from './setupTagsData';
import UniverseSwitcher from './UniverseSwitcher';
import Popover from './ui/Popover';

// The screener command band: the three control rows the toolbar used to stack
// (universe / count + data-ops / filter panel) folded into ONE horizontal
// instrument-framed band, so the card wall starts ~2 rows higher. Frequent
// triage controls stay inline (universe · tier · search · Filters); the rare
// plumbing folds into a right-aligned Data popover (Download + the verbose
// health line). Evaluate stays OUT on the bar — it's run constantly while the
// reading engine is being tuned. Nothing here is new state: it re-seats the
// existing filters/scan controls; mythril marks only the active control.
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
  universe,
  onUniverseChange,
}) {
  // The Download/Evaluate actions operate ONLY on the US-Stocks cache; the ETF
  // universes are refreshed by the scheduled daily scan, so these controls are
  // disabled there rather than misleading the user into a no-op (council #14).
  const scanDisabledTitle = etfUniverse
    ? 'Sector/commodity universes refresh on the scheduled daily scan, not from here.'
    : null;
  // The tier/search/Filters cluster only makes sense once a scan exists; the
  // universe switch and the data ops stay live so an empty universe can be
  // evaluated into existence.
  const showFilters = Boolean(screenerData) && !isEvaluating;
  const advancedCount =
    (filters.setupFilter !== 'ALL' ? 1 : 0) +
    (filters.sortBy !== 'score' ? 1 : 0) +
    filters.tagFilter.size;
  const healthState = marketDataStatus?.health_state || marketDataStatus?.status;
  const evaluateDisabled = isScanning || etfUniverse || marketDataStatus?.can_evaluate === false;
  const downloadDisabled = isScanning || etfUniverse || marketDataStatus?.can_download === false;

  return (
    <div className="instrument-tile screener-command-band">
      <UniverseSwitcher universe={universe} onChange={onUniverseChange} showLabel={false} />

      {showFilters && (
        <>
          <span className="screener-command-seam" />
          {['ALL', 'S', 'A', 'B', 'C', 'WATCHLIST'].map(tier => (
            <button
              key={tier}
              onClick={() => {
                filters.setTierFilter(tier);
                filters.setCurrentPage(1);
              }}
              aria-pressed={filters.tierFilter === tier}
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
          <Popover align="left" panelWidth={360} panelLabel="Setup, sort and tag filters"
            renderTrigger={({ open, toggle, triggerRef }) => (
              <button
                ref={triggerRef}
                onClick={toggle}
                aria-expanded={open}
                title={open ? 'Hide setup, sort, and tag filters' : 'Show setup, sort, and tag filters'}
                style={moreButtonStyle(advancedCount > 0)}
              >
                {advancedCount > 0 ? `▸ Filters · ${advancedCount}` : '▸ Filters'}
              </button>
            )}
          >
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <SortRow filters={filters} />
              <TagFilterRow filters={filters} />
              <TagLegend style={{ borderTop: '1px solid var(--border-color)', paddingTop: '10px' }} />
              {advancedCount > 0 && (
                <button onClick={filters.resetFilters} style={resetStyle}>Reset filters</button>
              )}
            </div>
          </Popover>
        </>
      )}

      <span className="screener-command-spacer" />

      {showFilters && (
        <span style={matchedStyle}>{matchedCount} matched</span>
      )}

      <button
        onClick={onEvaluateCached}
        disabled={evaluateDisabled}
        title={scanDisabledTitle || marketDataStatus?.diagnosis || marketDataStatus?.message || 'Evaluate the current local market-data cache.'}
        style={scanButtonStyle(evaluateDisabled)}
      >
        {isEvaluating ? 'Evaluating…' : 'Evaluate'}
      </button>

      <Popover align="right" panelWidth={280} panelLabel="Market-data status and actions"
        renderTrigger={({ open, toggle, triggerRef }) => (
          <button
            ref={triggerRef}
            onClick={toggle}
            aria-expanded={open}
            title={marketDataStatus?.diagnosis || marketDataStatus?.message || 'Market-data cache status, download and evaluate'}
            style={dataTriggerStyle}
          >
            <span style={statusDotStyle(healthState, marketDataStatus?.severity)} />
            <span style={{ color: 'var(--text-muted)' }}>
              {marketDataStatus ? statusLabel(marketDataStatus) : 'Checking…'}
            </span>
            <span style={{ color: 'var(--text-faint)', fontSize: 10 }}>Data ▾</span>
          </button>
        )}
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          <div style={{ fontSize: 12, color: 'var(--text-muted)', lineHeight: 1.45 }}>
            {marketDataStatus?.diagnosis || marketDataStatus?.message || 'Data status unknown.'}
          </div>
          <button
            onClick={onDownloadData}
            disabled={downloadDisabled}
            title={scanDisabledTitle || marketDataStatus?.diagnosis || marketDataStatus?.message || 'Refresh market-data cache'}
            style={downloadButtonStyle(downloadDisabled, healthState, marketDataStatus?.severity)}
          >
            {isDownloading ? 'Downloading Data...' : marketDataStatus?.download_label || 'Download New Data'}
          </button>
        </div>
      </Popover>
    </div>
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

const scanButtonStyle = (disabled) => ({
  background: disabled ? 'var(--bg-hover)' : 'var(--accent-active)',
  color: disabled ? 'var(--text-muted)' : 'var(--myth-ink)',
  border: 'none', padding: '7px 16px', borderRadius: 'var(--radius-sm)',
  cursor: disabled ? 'not-allowed' : 'pointer',
  fontWeight: '700', transition: 'all 0.2s', fontFamily: 'inherit',
  fontSize: '12px', whiteSpace: 'nowrap', flex: '0 0 auto',
});

const downloadButtonStyle = (disabled, status, severity) => {
  const bg = downloadColor(status, severity);
  return {
    background: disabled ? 'var(--bg-hover)' : bg,
    // Dark ink on the mythril (healthy) fill; white stays on the pink/red
    // repair + blocked states where it reads correctly.
    color: disabled ? 'var(--text-muted)' : bg === 'var(--accent-active)' ? 'var(--myth-ink)' : '#fff',
    border: 'none', padding: '8px 14px', borderRadius: 'var(--radius-sm)',
    cursor: disabled ? 'not-allowed' : 'pointer',
    fontWeight: bg === 'var(--accent-active)' ? '700' : '600', transition: 'all 0.2s', fontFamily: 'inherit',
    whiteSpace: 'nowrap', width: '100%',
  };
};

const downloadColor = (status, severity) => {
  if (severity === 'repair' || status === 'needs_repair') return 'var(--accent-pink, #bb86fc)';
  if (severity === 'blocked' || status === 'stale_session') return 'var(--danger)';
  return 'var(--accent-active)';
};

const dataTriggerStyle = {
  alignItems: 'center',
  background: 'var(--bg-panel)',
  border: '1px solid var(--border-strong)',
  borderRadius: 'var(--radius-sm)',
  cursor: 'pointer',
  display: 'inline-flex',
  flex: '0 0 auto',
  fontFamily: 'inherit',
  fontSize: '12px',
  fontWeight: 600,
  gap: '7px',
  maxWidth: '260px',
  overflow: 'hidden',
  padding: '6px 11px',
  whiteSpace: 'nowrap',
};

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

const matchedStyle = {
  fontSize: '12.5px',
  color: 'var(--text-muted)',
  whiteSpace: 'nowrap',
  fontVariantNumeric: 'tabular-nums',
  flex: '0 0 auto',
};

const filterLabelStyle = { fontSize: '12px', color: 'var(--text-muted)', fontWeight: '500', marginRight: '6px' };
const tierButtonStyle = (active) => ({
  padding: '5px 14px', borderRadius: 'var(--radius-lg)', border: '1px solid',
  borderColor: active ? 'var(--accent-active)' : 'var(--border-color)',
  background: active ? 'var(--accent-active)' : 'transparent',
  color: active ? 'var(--myth-ink)' : 'var(--text-main)',
  cursor: 'pointer', fontWeight: active ? '700' : '500',
  fontSize: '12px', fontFamily: 'inherit', whiteSpace: 'nowrap',
});
const searchStyle = {
  padding: '5px 14px', borderRadius: 'var(--radius-sm)',
  border: '1px solid var(--border-color)',
  background: 'var(--bg-main)',
  color: 'var(--text-main)',
  fontSize: '12px', width: '150px', outline: 'none', fontFamily: 'inherit',
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
  borderRadius: 'var(--radius-lg)', padding: '5px 12px', cursor: 'pointer', fontFamily: 'inherit',
  alignSelf: 'flex-start',
};
// Disclosure trigger for the secondary filters. Goes mythril (active) only when
// hidden filters are applied, so a collapsed band still announces "filters active".
const moreButtonStyle = (active) => ({
  fontSize: '11px', fontWeight: active ? 700 : 600,
  color: active ? 'var(--myth-ink)' : 'var(--text-muted)',
  background: active ? 'var(--accent-active)' : 'transparent',
  border: `1px solid ${active ? 'var(--accent-active)' : 'var(--border-color)'}`,
  borderRadius: 'var(--radius-lg)', padding: '5px 12px', cursor: 'pointer', fontFamily: 'inherit',
  whiteSpace: 'nowrap',
});
const tagButtonStyle = (active) => ({
  fontSize: '10px', fontWeight: 700,
  fontFamily: "'JetBrains Mono', monospace",
  padding: '3px 9px', borderRadius: 'var(--radius-lg)', cursor: 'pointer',
  border: `1px solid ${active ? 'var(--accent-active)' : 'var(--border-color)'}`,
  background: active ? 'var(--accent-active)' : 'transparent',
  color: active ? 'var(--myth-ink)' : 'var(--text-main)',
});

export default ScreenerToolbar;
