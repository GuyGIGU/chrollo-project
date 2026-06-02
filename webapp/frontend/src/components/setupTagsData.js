import { SUB_SCORE_CAPS } from './setupScoreMath';

export const GROUP_TONES = {
  consolidation: { bg: 'rgba(88,166,255,0.18)', fg: '#58a6ff' },
  lps: { bg: 'rgba(231,179,65,0.18)', fg: '#e3b341' },
  volume: { bg: 'rgba(166,226,46,0.18)', fg: '#a6e22e' },
  trend: { bg: 'rgba(63,185,80,0.18)', fg: '#3fb950' },
  warning: { bg: 'rgba(248,81,73,0.18)', fg: '#f85149' },
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
  lps: 'LPS / launch pad',
  volume: 'Volume',
  trend: 'Trend',
  warning: 'Warning',
};

const TOUCH_VOL_Z_NO_SUPPLY = -0.30;
const TOUCH_VOL_Z_SPRING = 0.30;
const TOUCH_VOL_Z_HEAVY_R = 0.50;
const MAX_TAGS = 4;

const firesAt = (scores, key, fraction) => (
  (scores?.[key] ?? 0) >= fraction * SUB_SCORE_CAPS[key]
);

const tag = (id, label, group, title, weight, fires) => ({
  id,
  label,
  group,
  title,
  weight,
  fires,
});

const TAG_DEFS = [
  tag(
    'phase_d',
    '📐 Phase D',
    'consolidation',
    'A tighter, newer consolidation has formed inside the larger base — the engine swapped to this refined inner box (Wyckoff Phase D launchpad). How to read it: often the final tightening just before a move. Watch the inner-box edges for the trigger; strongest when paired with a volume dry-up.',
    100,
    (_scores, flags) => !!flags.phaseDInner,
  ),
  tag('old_base', '🏛 Old Base', 'consolidation', 'A long-built base — the stock has spent many months forming this consolidation (lots of Wyckoff "cause"). How to read it: more time building = more stored energy for a potential move. But age alone isn\'t a trigger — still wants a tight edge and a volume dry-up to act on.', 90, scores => firesAt(scores, 'base_age', 0.80)),
  tag('vcp_coil', '🌀 VCP Coil', 'consolidation', 'Progressive volatility contraction — each pullback in the base is tighter than the one before, ending in a tight final coil (Minervini\'s VCP). How to read it: the classic pre-breakout footprint of supply drying up in stages. The tighter the final coil, the closer your stop can sit — so the lower-risk the entry.', 88, scores => firesAt(scores, 'contraction', 0.80)),
  tag('tight_box', '🔒 Tight Box', 'consolidation', 'Price is compressed into a narrow resistance/support range — a tightly-wound horizontal box. How to read it: tightness means a coiled spring and a clean, close stop just under support. You want the breakout on rising volume; if it fails, the tight range keeps the loss small.', 85, scores => firesAt(scores, 'box_tightness', 0.80)),
  tag('ascending_support', '📈 Ascending Support', 'consolidation', 'The base\'s swing lows are stair-stepping upward — rising support / higher lows (Minervini "tennis-ball action", Qullamaggie higher-lows surfing a rising EMA). How to read it: demand is getting more aggressive into each pullback — buyers stepping in earlier every dip. A rising floor under a flat ceiling is a stronger, more urgent coil than a flat floor.', 80, scores => firesAt(scores, 'ascending_support', 0.80)),
  tag('tight_lps', '🪶 Tight LPS', 'lps', 'The final pullback (the launch pad) is exceptionally tight — an unusually calm, narrow last pause before a potential breakout. How to read it: no selling pressure right before the move, the trigger sits just overhead, and the tightness lets you place a close stop. The lower-risk spot to act.', 80, scores => firesAt(scores, 'lps_tightness', 1.00)),
  tag(
    'no_supply',
    '🤫 No Supply',
    'volume',
    'Resistance was tested on below-average volume — barely any selling came out at the ceiling (Wyckoff "no supply"). How to read it: a bullish tell — the lid is weakly defended, which often precedes a clean breakout. Supply is being absorbed quietly.',
    78,
    (_scores, flags) => typeof flags.rTouchVolZ === 'number' && flags.rTouchVolZ < TOUCH_VOL_Z_NO_SUPPLY,
  ),
  tag('vol_dryup', '🌊 Vol Dry-up', 'volume', 'Volume in the final pause shrank well below the 50-day average — supply has dried up (the "quiet before the move"). How to read it: sellers look exhausted into the tightening. Now you want volume to EXPAND on the breakout to confirm demand actually shows up.', 75, scores => firesAt(scores, 'vol_contraction', 0.80)),
  tag(
    'demand_at_s',
    '💪 Demand at S',
    'volume',
    'Support was tested on above-average volume — buyers stepped in at the floor and absorbed the selling. How to read it: active demand defending the bottom of the range is strength under the base. (This is buying inside the range, not a Phase C spring — a spring would show as a REBOUND setup type.)',
    72,
    (_scores, flags) => typeof flags.sTouchVolZ === 'number' && flags.sTouchVolZ > TOUCH_VOL_Z_SPRING,
  ),
  tag('strong_rs', '🥇 Strong RS', 'trend', 'The stock is strongly outperforming the S&P 500 over the last ~6 months — a relative-strength leader. How to read it: money is already flowing into this name versus the market, and leaders tend to keep leading. A real leader resting in a base beats a laggard bouncing. Pairs powerfully with High ADR.', 65, scores => firesAt(scores, 'rs_bonus', 0.95)),
  tag('uptrend', '🚀 Uptrend', 'trend', 'The base sits inside a fully-developed yearly uptrend — this is re-accumulation (a rest stop), not a bottoming attempt. How to read it: you\'d be trading WITH the dominant trend rather than betting on a reversal — generally higher-odds context for a continuation move.', 60, scores => firesAt(scores, 'uptrend_bonus', 0.95)),
  tag('high_adr', '⚡ High ADR', 'trend', 'High Average Daily Range — a volatile mover (Qullamaggie ADR% ≥ ~5%). A big-range stock resting in a tight base is prime momentum-continuation fuel.', 62, scores => firesAt(scores, 'adr', 0.80)),
  tag(
    'heavy_resistance',
    '⚠️ Heavy Resistance',
    'warning',
    'Resistance is being tested on ABOVE-average volume — real supply hits the bid every time price reaches the ceiling (distribution-flavored). How to read it: a caution flag, not an automatic pass. The breakout will need heavy demand to overwhelm the sellers — be quicker to cut if price stalls at resistance.',
    95,
    (_scores, flags) => typeof flags.rTouchVolZ === 'number' && flags.rTouchVolZ > TOUCH_VOL_Z_HEAVY_R,
  ),
];

export function deriveTags(subScores, flags = {}) {
  if (!subScores) return [];
  return TAG_DEFS
    .filter(tagDef => tagDef.fires(subScores, flags))
    .sort((a, b) => b.weight - a.weight)
    .slice(0, MAX_TAGS)
    .sort((a, b) => (
      GROUP_ORDER[a.group] - GROUP_ORDER[b.group] || b.weight - a.weight
    ));
}

export const TAG_CATALOG = [...TAG_DEFS]
  .sort((a, b) => GROUP_ORDER[a.group] - GROUP_ORDER[b.group] || b.weight - a.weight)
  .map(({ id, label, group }) => ({ id, label, group }));
