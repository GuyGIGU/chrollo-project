// Sort keys mirror the archive table columns (see ArchiveTable COLUMNS) so the
// header-click sort and the filter dropdown stay in sync. 'scan_date' is the
// episode's first-seen (entry) date.
export const SORT_OPTIONS = [
  ['scan_date', 'Entry'],
  ['tier', 'Tier'],
  ['score', 'Score'],
  ['setup_type', 'Type'],
  ['scan_count', 'Scans'],
  ['fwd_return_20d', '20d'],
  ['r_multiple_20d', 'R'],
  ['triggered', 'Trig'],
  ['ticker', 'Ticker'],
];

export const ITEMS_PER_PAGE = 24;
export const QUALITY_LABELS = ['perfect', 'good', 'noise', 'miss'];
export const TIERS = ['ALL', 'S', 'A', 'B', 'C', 'D'];
export const SETUP_TYPES = ['ALL', 'LPS', 'REBOUND', 'BREAKOUT'];

export const SOURCE_FILTERS = [
  ['curated', 'Curated', 'seed,manual'],
  ['all', 'All', null],
  ['seed', 'Seed', 'seed'],
  ['manual', 'Manual', 'manual'],
  ['screener', 'Screener', 'screener'],
];

export const pct = (value) => (value != null ? `${(value * 100).toFixed(2)}%` : '-');

export const fixed = (value, digits = 2) => (
  value == null || !Number.isFinite(Number(value)) ? '-' : Number(value).toFixed(digits)
);

export const tierColor = (tier) => ({
  S: '#ff8c00',
  A: '#bb86fc',
  B: '#58a6ff',
  C: '#3fb950',
  D: '#8b949e',
}[tier] || '#8b949e');

export const labelColor = (label) => ({
  perfect: '#3fb950',
  good: '#58a6ff',
  noise: '#8b949e',
  miss: '#c76b73',
}[label] || 'var(--text-muted)');

// Sign-based coloring for returns, P&L, forward-return values: positive = success.
export const signColor = (value) => (
  value == null ? undefined : value > 0 ? 'var(--success)' : value < 0 ? 'var(--danger)' : undefined
);

// R-multiple coloring: green only above 1R (more than 1× risk returned),
// danger below 0, neutral for the 0–1 range (profitable but sub-1R).
export const rMultipleColor = (value) => (
  value == null ? undefined : value > 1 ? 'var(--success)' : value < 0 ? 'var(--danger)' : undefined
);

export const archiveButtonStyle = (active) => ({
  background: active ? 'var(--accent-blue)' : 'transparent',
  border: '1px solid',
  borderColor: active ? 'var(--accent-blue)' : 'var(--border-color)',
  borderRadius: '16px',
  color: active ? '#fff' : 'var(--text-main)',
  cursor: 'pointer',
  fontFamily: 'inherit',
  fontSize: '12px',
  fontWeight: active ? '600' : '500',
  padding: '5px 14px',
  transition: 'all 0.2s ease',
});
