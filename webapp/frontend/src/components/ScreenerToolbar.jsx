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
  hideFilters = false,
}) {
  // The Download/Evaluate actions operate ONLY on the US-Stocks cache; the ETF
  // universes are refreshed by the scheduled daily scan, so these controls are
  // disabled there rather than misleading the user into a no-op (council #14).
  const scanDisabledTitle = etfUniverse
    ? 'Sector/commodity universes refresh on the scheduled daily scan, not from here.'
    : null;
  // The tier/search/Filters cluster only makes sense once a scan exists; the
  // universe switch and the data ops stay live so an empty universe can be
  // evaluated into existence. Over the health board the filter cluster is
  // suppressed (hideFilters) — its "N matched" count and tier/tag filters are
  // firing-grid concepts that would mislead across a full context board.
  const showFilters = Boolean(screenerData) && !isEvaluating && !hideFilters;
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
            {/* minWidth/ellipsis so an unrecognised state (statusLabel falls back to
                the full diagnosis) truncates instead of shoving the caret out of the
                fixed-width, nowrap trigger. */}
            <span style={{ color: 'var(--text-muted)', minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis' }}>
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
  // Readable but behind. Must stay SHORT (the pill is nowrap/232px; the full diagnosis
  // is in the trigger title and the popover), and must state the RELATION: "Behind:
  // <date>" reads as "behind that date" while the date supplied is the one the cache
  // HAS, which is an off-by-one on the only always-visible freshness indicator.
  if (state === 'session_lag') {
    const behind = status.sessions_behind;
    const suffix = behind ? ` (${behind} session${behind === 1 ? '' : 's'} behind)` : '';
    return `On ${status.cache_last_session || '-'}${suffix}`;
  }
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

const TAG_CATALOG_IDS = new Set(TAG_CATALOG.map(tag => tag.id));

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
      {/* Unknown engine ids stay filterable, same verbatim-slug fallthrough
          as the chips — the cards and the filter bar must agree on the tag
          vocabulary (2026-08-08 review, D5: a new engine chip was visible
          on cards but silently unselectable here). */}
      {[...filters.availableTagIds].filter(id => !TAG_CATALOG_IDS.has(id)).map(id => {
        const active = filters.tagFilter.has(id);
        return (
          <button
            key={id}
            onClick={() => filters.toggleTagFilter(id)}
            title={active ? 'Click to remove this tag filter'
              : 'New engine tag (label pending) — show only setups carrying it'}
            style={tagButtonStyle(active)}
          >
            {id}
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

// Fills light enough that white ink fails contrast — these take the dark ink instead.
const DARK_INK_FILLS = new Set(['var(--accent-active)', 'var(--warning)']);

const downloadButtonStyle = (disabled, status, severity) => {
  const bg = downloadColor(status, severity);
  return {
    background: disabled ? 'var(--bg-hover)' : bg,
    // Dark ink on the LIGHT fills (mythril, warning amber); white stays on the
    // pink/red repair + blocked states where it reads correctly. White on
    // --warning (#E2B255) is about 1.8:1 — unreadable — so the amber fill must
    // take the dark treatment, not inherit the white default.
    color: disabled ? 'var(--text-muted)' : DARK_INK_FILLS.has(bg) ? 'var(--myth-ink)' : '#fff',
    border: 'none', padding: '8px 14px', borderRadius: 'var(--radius-sm)',
    cursor: disabled ? 'not-allowed' : 'pointer',
    fontWeight: bg === 'var(--accent-active)' ? '700' : '600', transition: 'all 0.2s', fontFamily: 'inherit',
    whiteSpace: 'nowrap', width: '100%',
  };
};

const downloadColor = (status, severity) => {
  if (severity === 'repair' || status === 'needs_repair') return 'var(--accent-pink, #bb86fc)';
  if (severity === 'blocked' || status === 'stale_session') return 'var(--danger)';
  // Deliberate, not a fall-through: on a lag day the trigger cautions amber, so the
  // panel it opens must not present the full mythril "recommended next step" fill for
  // a click that now launches a ~30-minute full-universe refetch.
  if (status === 'session_lag') return 'var(--warning)';
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
  // FIXED, not max: the pill sits last in the right-aligned cluster, so a
  // state-dependent width drags Evaluate sideways under the operator's cursor every
  // time the status resolves ("Checking…" → real label, and again after each run) —
  // and on the 1536-effective display a wider pill is a plausible trigger for the
  // wrapping command band to take a second row. Truncation now has a stable boundary.
  width: '232px',
  overflow: 'hidden',
  padding: '6px 11px',
  whiteSpace: 'nowrap',
  // The pill renders changing numbers (coverage %, session dates); its neighbour
  // `matchedStyle` on the same band is already tabular. A jittering number is a defect.
  fontVariantNumeric: 'tabular-nums',
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
  // Behind but readable: warn, don't alarm — and don't fall through to the muted
  // default, which is indistinguishable from an unrecognised state. Bare token, no hex
  // fallback: --warning is #E2B255, deliberately softened off the acid #F0BE3C the
  // design system rejected, so a hardcoded fallback would repaint this off-doctrine.
  if (status === 'session_lag') return 'var(--warning)';
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
