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
  uptrend_bonus:   15,
  rs_bonus:        15,
  high_proximity:   8,
  breadth_bonus:    8,
  contraction:     12,
  ascending_support: 8,
};

// Volume-around-touches z-score thresholds (mirror config/settings.py:
// TOUCH_VOL_Z_NO_SUPPLY, TOUCH_VOL_Z_SPRING, TOUCH_VOL_Z_HEAVY_R).
const TOUCH_VOL_Z_NO_SUPPLY = -0.30;
const TOUCH_VOL_Z_SPRING    = 0.30;
const TOUCH_VOL_Z_HEAVY_R   = 0.50;

const MAX_TAGS = 4;             // keep cards readable

// ── Tag groups ───────────────────────────────────────────────────
// Every tag belongs to a category, and the category sets BOTH its color and
// its display position. So a glance at a card's chip colors tells you which
// dimensions the engine liked, and the colors stay consistent across cards:
//   consolidation — the base / structure (tight box, R/S, coil, base age) → blue
//   lps           — the final pullback / launch pad                       → yellow
//   volume        — supply/demand read from volume                        → lime
//   trend         — leadership / uptrend context                          → green
//   warning       — a risk flag                                           → red
const GROUP_TONES = {
  consolidation: { bg: 'rgba(88,166,255,0.18)', fg: '#58a6ff' },  // blue
  lps:           { bg: 'rgba(231,179,65,0.18)', fg: '#e3b341' },  // yellow
  volume:        { bg: 'rgba(166,226,46,0.18)', fg: '#a6e22e' },  // lime
  trend:         { bg: 'rgba(63,185,80,0.18)',  fg: '#3fb950' },  // green
  warning:       { bg: 'rgba(248,81,73,0.18)',  fg: '#f85149' },  // red
};

// Left-to-right display order of the groups. Lead with the structural story
// (the engine's prime directive), then the launch pad, the volume read, the
// trend context, and finally any risk flag.
const GROUP_ORDER = { consolidation: 0, lps: 1, volume: 2, trend: 3, warning: 4 };

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

// Tag catalogue — each entry: { id, label, group, fires(subScores, flags) → bool, weight }
// `group` sets the color (GROUP_TONES) and the display order (GROUP_ORDER).
// `weight` decides which tags survive when more than MAX_TAGS fire (higher = kept).
const TAG_DEFS = [
  // ── Consolidation / structure (blue) ──────────────────────────
  {
    id: 'phase_d',
    label: '📐 Phase D',
    group: 'consolidation',
    title: 'Inner sub-box (Phase D launchpad) refined the outer base — tighter, newer consolidation inside the larger one',
    weight: 100,
    fires: (_s, flags) => !!flags.phaseDInner,
  },
  {
    id: 'old_base',
    label: '🏛 Old Base',
    group: 'consolidation',
    title: 'Long-built base (high "Wyckoff cause") — base_age sub-score near max',
    weight: 90,
    fires: (s) => FIRE(s, 'base_age', 0.80),
  },
  {
    // The Minervini VCP signature: progressive contractions (e.g. 18->12->6%)
    // tightening into the base. Distinct from Tight Box (static width) — this
    // fires on the *process* of coiling, the strongest pre-breakout footprint.
    id: 'vcp_coil',
    label: '🌀 VCP Coil',
    group: 'consolidation',
    title: 'Progressive volatility contraction — each pullback tighter than the last, ending in a tight final coil (Minervini VCP footprint)',
    weight: 88,
    fires: (s) => FIRE(s, 'contraction', 0.80),
  },
  {
    id: 'tight_box',
    label: '🔒 Tight Box',
    group: 'consolidation',
    title: 'Narrow R/S range — concentrated equilibrium',
    weight: 85,
    fires: (s) => FIRE(s, 'box_tightness', 0.80),
  },
  {
    // Ascending support: the base's swing lows are stair-stepping UP — demand
    // getting more aggressive into each pullback (Minervini tennis-ball action /
    // Qullamaggie higher-lows surfing the rising EMA).
    id: 'ascending_support',
    label: '📈 Ascending Support',
    group: 'consolidation',
    title: 'Swing lows stair-stepping up across the base — rising support / higher lows (tennis-ball action). Demand getting more aggressive into each pullback.',
    weight: 80,
    fires: (s) => FIRE(s, 'ascending_support', 0.80),
  },
  // ── LPS / launch pad (yellow) ─────────────────────────────────
  {
    id: 'tight_lps',
    label: '🪶 Tight LPS',
    group: 'lps',
    title: 'Exceptionally tight final pullback bar — fully maxed LPS-tightness sub-score',
    weight: 80,
    fires: (s) => FIRE(s, 'lps_tightness', 1.00),
  },
  // ── Volume (lime) ─────────────────────────────────────────────
  {
    // Wyckoff "no supply" — buyers absorbed R-touches without driving volume.
    // The textbook precursor to a clean breakout.
    id: 'no_supply',
    label: '🤫 No Supply',
    group: 'volume',
    title: 'Resistance tested on below-average volume — no supply coming out. Buyers absorbing silently.',
    weight: 78,
    fires: (_s, flags) => typeof flags.rTouchVolZ === 'number'
      && flags.rTouchVolZ < TOUCH_VOL_Z_NO_SUPPLY,
  },
  {
    id: 'vol_dryup',
    label: '🌊 Vol Dry-up',
    group: 'volume',
    title: 'LPS-window volume contracted vs the 50-day average — supply has dried up',
    weight: 75,
    fires: (s) => FIRE(s, 'vol_contraction', 0.80),
  },
  {
    // Demand at support — high volume on S-touches INSIDE the range.
    // Renamed from "Spring Strength" because in Wyckoff terminology a
    // Spring is specifically a Phase C undercut BELOW the range (we
    // already label that zone REBOUND in the setup type). This tag is
    // about buying interest absorbing supply at the S boundary itself.
    id: 'demand_at_s',
    label: '💪 Demand at S',
    group: 'volume',
    title: 'Support tested on above-average volume — buyers stepping in at S, selling absorbed. Note: this is demand inside the range, not a Phase C spring (which would show as a REBOUND setup type).',
    weight: 72,
    fires: (_s, flags) => typeof flags.sTouchVolZ === 'number'
      && flags.sTouchVolZ > TOUCH_VOL_Z_SPRING,
  },
  // ── Trend / leadership (green) ────────────────────────────────
  {
    id: 'strong_rs',
    label: '🥇 Strong RS',
    group: 'trend',
    title: 'Strong leadership vs SPY — RS bonus sub-score fully (or nearly fully) ramped',
    weight: 65,
    fires: (s) => FIRE(s, 'rs_bonus', 0.95),
  },
  {
    id: 'uptrend',
    label: '🚀 Uptrend',
    group: 'trend',
    title: 'Re-accumulation inside a fully-developed yearly uptrend — uptrend bonus sub-score fully (or nearly fully) ramped',
    weight: 60,
    fires: (s) => FIRE(s, 'uptrend_bonus', 0.95),
  },
  // ── Warning (red) ─────────────────────────────────────────────
  {
    // WARNING: distribution-flavored resistance. R-touches printing on
    // ABOVE-average volume = supply hitting the bid every time it gets there.
    // Not always a kill, but worth a flag on the card.
    id: 'heavy_resistance',
    label: '⚠️ Heavy Resistance',
    group: 'warning',
    title: 'Resistance tested on ABOVE-average volume — supply hitting the bid at R. Distribution-flavored, breakout risk.',
    weight: 95,  // High weight so the warning survives selection even amid positive tags
    fires: (_s, flags) => typeof flags.rTouchVolZ === 'number'
      && flags.rTouchVolZ > TOUCH_VOL_Z_HEAVY_R,
  },
];

// Derive the tag list from a sub-score dict + flag bag. Returns at most
// MAX_TAGS entries. Selection keeps the most informative tags (by weight);
// display order is then by group (color) so chips are always grouped and
// consistent left-to-right across every card.
//
// `subScores` shape: { box_tightness, touch_density, oscillation, atr_squeeze,
//                      lps_tightness, vol_contraction, base_age, uptrend_bonus,
//                      rs_bonus, high_proximity, breadth_bonus, contraction,
//                      ascending_support }
// `flags` shape:     { phaseDInner: bool, rTouchVolZ: number|null, sTouchVolZ: number|null }
export function deriveTags(subScores, flags = {}) {
  if (!subScores) return [];
  return TAG_DEFS
    .filter(t => t.fires(subScores, flags))
    .sort((a, b) => b.weight - a.weight)          // keep the most informative…
    .slice(0, MAX_TAGS)
    .sort((a, b) =>                                // …then display grouped by color
      (GROUP_ORDER[a.group] - GROUP_ORDER[b.group]) || (b.weight - a.weight));
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
      {tags.map(t => {
        const tone = GROUP_TONES[t.group];
        return (
          <span
            key={t.id}
            title={t.title}
            style={{ ...chipBase, background: tone.bg, color: tone.fg }}
          >
            {t.label}
          </span>
        );
      })}
    </div>
  );
}
