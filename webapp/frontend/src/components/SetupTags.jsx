// "Why ranked" tag chips for screener / archive cards.
//
// Each tag is a one-glance answer to "what did the engine like about this
// setup?" — derived from the sub-score decomposition that drives the total
// score. A sub-score "fires" as a tag when it sits at >= 80% of its cap (or
// > 0 for ramp-style bonuses). Phase D is its own boolean flag from the
// hierarchical detector.
//
// Caps mirror config/settings.py. They change rarely; the small duplication
// is worth keeping the frontend independent of a backend payload for caps.

const SUB_SCORE_CAPS = {
  box_tightness:   15,
  touch_density:   25,
  oscillation:      5,
  atr_squeeze:      8,
  lps_tightness:   20,
  vol_contraction: 20,
  base_age:        35,
};

const MAX_TAGS = 4;             // keep cards readable

// Per-tag thresholds tuned against the live distribution. The goal is for
// a tag to fire on roughly the top quintile (15-25%) of setups for that
// dimension — so a tag actually *means* something on a card, instead of
// becoming a participation chip. Notes:
//   - touch_density and the two ramp-bonuses (rs/uptrend) max out easily
//     in a bull market, so they require the FULL cap (or very close).
//   - lps_tightness similarly: most LPS bars are tight by construction;
//     "tight LPS" should mean exceptionally so.
//   - base_age, box_tightness already discriminate well at 80%.
const FIRE = (s, key, frac) => (s?.[key] ?? 0) >= frac * SUB_SCORE_CAPS[key];

// Tag catalogue — each entry: { id, label, tone, fires(subScores, flags) → bool, weight }
// `weight` decides ordering when more than MAX_TAGS fire. Higher = shown first.
const TAG_DEFS = [
  {
    id: 'phase_d',
    label: '📐 Phase D',
    tone: { bg: 'rgba(255,140,0,0.18)',  fg: '#ff8c00' },
    title: 'Inner sub-box (Phase D launchpad) refined the outer base — tighter, newer consolidation inside the larger one',
    weight: 100,
    fires: (_s, flags) => !!flags.phaseDInner,
  },
  {
    id: 'old_base',
    label: '🏛 Old Base',
    tone: { bg: 'rgba(187,134,252,0.18)', fg: '#bb86fc' },
    title: 'Long-built base (high "Wyckoff cause") — base_age sub-score near max',
    weight: 90,
    fires: (s) => FIRE(s, 'base_age', 0.80),
  },
  {
    id: 'tight_box',
    label: '🔒 Tight Box',
    tone: { bg: 'rgba(231,179,65,0.18)',  fg: '#e3b341' },
    title: 'Narrow R/S range — concentrated equilibrium',
    weight: 85,
    fires: (s) => FIRE(s, 'box_tightness', 0.80),
  },
  {
    id: 'tight_lps',
    label: '🪶 Tight LPS',
    tone: { bg: 'rgba(63,185,80,0.18)',   fg: '#3fb950' },
    title: 'Exceptionally tight final pullback bar — fully maxed LPS-tightness sub-score',
    weight: 80,
    fires: (s) => FIRE(s, 'lps_tightness', 1.00),
  },
  {
    id: 'vol_dryup',
    label: '🌊 Vol Dry-up',
    tone: { bg: 'rgba(88,166,255,0.18)',  fg: '#58a6ff' },
    title: 'LPS-window volume contracted vs the 50-day average — supply has dried up',
    weight: 75,
    fires: (s) => FIRE(s, 'vol_contraction', 0.80),
  },
  // touch_density intentionally has no tag: ~92% of setups max it out
  // (the touch bonus is binary and easy to trigger), so a "heavy touches"
  // chip would fire on nearly every card and tell the user nothing.
  {
    id: 'strong_rs',
    label: '📈 Strong RS',
    tone: { bg: 'rgba(63,185,80,0.18)',   fg: '#3fb950' },
    title: 'Strong leadership vs SPY — RS bonus sub-score fully (or nearly fully) ramped',
    weight: 65,
    fires: (s) => FIRE(s, 'rs_bonus', 0.95),
  },
  {
    id: 'uptrend',
    label: '🚀 Uptrend',
    tone: { bg: 'rgba(63,185,80,0.18)',   fg: '#3fb950' },
    title: 'Re-accumulation inside a fully-developed yearly uptrend — uptrend bonus sub-score fully (or nearly fully) ramped',
    weight: 60,
    fires: (s) => FIRE(s, 'uptrend_bonus', 0.95),
  },
];

// Derive the tag list from a sub-score dict + flag bag. Returns at most
// MAX_TAGS entries, ordered by weight (so the most informative show first).
//
// `subScores` shape: { box_tightness, touch_density, oscillation, atr_squeeze,
//                      lps_tightness, vol_contraction, base_age,
//                      uptrend_bonus, rs_bonus }
// `flags` shape:     { phaseDInner: bool }
export function deriveTags(subScores, flags = {}) {
  if (!subScores) return [];
  return TAG_DEFS
    .filter(t => t.fires(subScores, flags))
    .sort((a, b) => b.weight - a.weight)
    .slice(0, MAX_TAGS);
}

const chipBase = {
  padding: '1px 6px',
  borderRadius: '8px',
  fontSize: '9px',
  fontWeight: 700,
  fontFamily: "'JetBrains Mono', monospace",
  whiteSpace: 'nowrap',
};

// Renders a horizontal row of tag chips. Auto-wraps if the card is narrow.
export function TagRow({ subScores, flags, style }) {
  const tags = deriveTags(subScores, flags);
  if (tags.length === 0) return null;
  return (
    <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap', ...style }}>
      {tags.map(t => (
        <span
          key={t.id}
          title={t.title}
          style={{ ...chipBase, background: t.tone.bg, color: t.tone.fg }}
        >
          {t.label}
        </span>
      ))}
    </div>
  );
}
