// Shared JS theme helpers — the single source of truth for tier colors and the
// sign/value color helpers that were duplicated across components.
//
// tierColor returns a LITERAL hex (not a var()) on purpose: several call sites
// append an alpha suffix (`${tierColor(tier)}55`) to tint a border, which only
// works on a literal hex. The values match the --tier-* CSS tokens in
// index.css / DESIGN.md, so the function and the tokens stay one ladder. Folding
// the three byte-identical inline copies (ScreenerCard/ScreenerModal/
// ScreenerStockLens) here; the archive's copy is reconciled to this ladder
// (its S shade #ff8c00 -> #FF9F43, a deliberate 1-shade alignment to DESIGN.md).

const TIER_COLORS = {
  S: '#FF9F43',
  A: '#BB86FC',
  B: '#58A6FF',
  C: '#3FB950',
  D: '#8B949E',
};

export const tierColor = (tier) => TIER_COLORS[tier] || TIER_COLORS.D;

// Sign-based coloring for returns / P&L / forward returns: positive = success.
export const signColor = (value) => (
  value == null ? undefined : value > 0 ? 'var(--success)' : value < 0 ? 'var(--danger)' : undefined
);

// R-multiple coloring: green only above 1R, danger below 0, neutral in 0..1.
export const rMultipleColor = (value) => (
  value == null ? undefined : value > 1 ? 'var(--success)' : value < 0 ? 'var(--danger)' : undefined
);

// Review-quality label coloring (archive). 'perfect' uses the DESIGN.md
// success token (not the tier-C green — different ladder).
export const labelColor = (label) => ({
  perfect: 'var(--success)',
  good: '#58a6ff',
  noise: '#8b949e',
  miss: '#c76b73',
}[label] || 'var(--text-muted)');
