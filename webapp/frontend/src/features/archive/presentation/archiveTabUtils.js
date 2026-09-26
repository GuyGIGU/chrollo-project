import { fmtPctFrac, fx } from '../../../shared/formatting/format.js';
import { TIER_LETTERS } from '../../../shared/presentation/wireVocabulary';

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
export const REVIEW_REASONS = [
  ['earnings', 'Earnings'],
  ['extended', 'Extended'],
  ['weak_structure', 'Weak structure'],
  ['weak_sector', 'Weak sector'],
  ['no_room', 'No room'],
  ['already_owned', 'Already owned'],
  ['illiquid', 'Illiquid'],
  ['other', 'Other'],
];
export const TIERS = ['ALL', ...TIER_LETTERS];
export const SETUP_TYPES = ['ALL', 'LPS', 'REBOUND', 'BREAKOUT'];

export const SOURCE_FILTERS = [
  ['curated', 'Curated', 'seed,manual'],
  ['all', 'All', null],
  ['seed', 'Seed', 'seed'],
  ['manual', 'Manual', 'manual'],
  ['screener', 'Screener', 'screener'],
];

// Archive dialect: forward returns arrive as fractions; `fixed` is the house fx.
export const pct = (value) => fmtPctFrac(value, 2);

export const fixed = (value, digits = 2) => fx(value, digits);

// Color helpers now live in the shared theme module (one tier ladder for the
// whole app). Re-exported here so existing archive imports keep working. NOTE:
// the archive's S tier was #ff8c00; it now resolves to the DESIGN.md #FF9F43
// like the rest of the app — a deliberate one-shade reconciliation.
export { tierColor, labelColor, signColor, rMultipleColor } from '../../../shared/presentation/theme';

export const archiveButtonStyle = (active) => ({
  background: active ? 'var(--accent-active)' : 'transparent',
  border: '1px solid',
  borderColor: active ? 'var(--accent-active)' : 'var(--border-color)',
  borderRadius: '16px',
  color: active ? 'var(--myth-ink)' : 'var(--text-main)',
  cursor: 'pointer',
  fontFamily: 'inherit',
  fontSize: '12px',
  fontWeight: active ? '600' : '500',
  padding: '5px 14px',
  transition: 'all 0.2s ease',
});
