// The presentational tag catalog — labels, groups, tones, ordering. Extracted
// from setupTagsData.js at the legacy retirement (council 2026-08-22) so the
// RESOLVED chip path owns its presentation without dragging the retired fire
// rules along. Which chips FIRE is decided engine-side and arrives on the wire
// as `fired_tags` verdicts (EC-28); this module never tests a threshold.
//
// The list order is the frozen presentational order the legacy file computed
// (group order, then weight descending within a group) — materialized as a
// literal so nothing here re-runs a ranking. `strong_rs` and `uptrend` are
// deliberately ABSENT: both terms are demoted to weight 0 (decisions.md
// 2026-07-25) and the engine's cap>0 rule means they can never fire; listing
// them would put two dead entries in the filter menu. If the engine ever
// re-fires an unknown id, the resolver's raw-slug fallback keeps it visible.
import { displayLabel } from './wireVocabulary.js';

// Tag backgrounds sit quiet (0.12 alpha) so a row of chips reads calm on a dense
// grid; the meaningful foreground hue is kept, and the warning tag keeps a little
// more presence (0.16) since it's the one chip meant to catch the eye.
export const GROUP_TONES = {
  consolidation: { bg: 'rgba(88,166,255,0.12)', fg: '#58a6ff' },
  lps: { bg: 'rgba(231,179,65,0.12)', fg: '#e3b341' },
  volume: { bg: 'rgba(166,226,46,0.12)', fg: '#a6e22e' },
  trend: { bg: 'rgba(61,211,122,0.12)', fg: 'var(--success)' },
  warning: { bg: 'rgba(var(--danger-rgb),0.16)', fg: 'var(--danger)' },
};

export const GROUP_ORDER = {
  consolidation: 0,
  lps: 1,
  volume: 2,
  trend: 3,
  warning: 4,
};

export const GROUP_LABELS = {
  consolidation: 'Structure',
  lps: 'LPS / support test',
  volume: 'Volume',
  trend: 'Trend',
  warning: 'Warning',
};

export const TAG_CATALOG = [
  { id: 'phase_d', label: '📐 Phase D', group: 'consolidation' },
  { id: 'old_base', label: '🏛 Old Base', group: 'consolidation' },
  { id: 'vcp_coil', label: '🌀 VCP Coil', group: 'consolidation' },
  { id: 'tight_box', label: '🔒 Tight Box', group: 'consolidation' },
  { id: 'ascending_support', label: '📈 Ascending Support', group: 'consolidation' },
  { id: 'worked_equilibrium', label: `⚖️ ${displayLabel('traversal_density')}`, group: 'consolidation' },
  { id: 'phase_c_test', label: '🪝 Spring/Test', group: 'lps' },
  { id: 'tight_lps', label: '🪶 Tight LPS', group: 'lps' },
  { id: 'no_supply', label: '🤫 No Supply', group: 'volume' },
  { id: 'vol_dryup', label: '🌊 Vol Dry-up', group: 'volume' },
  { id: 'demand_at_s', label: '💪 Demand at S', group: 'volume' },
  { id: 'weekly_reaccum', label: '⬆ Weekly Re-accum', group: 'trend' },
  { id: 'high_adr', label: '⚡ High ADR', group: 'trend' },
  { id: 'heavy_resistance', label: '⚠️ Heavy Resistance', group: 'warning' },
  { id: 'last_supper', label: 'Last Supper', group: 'warning' },
  { id: 'weak_monthly', label: '⬇ Weak monthly', group: 'warning' },
];
