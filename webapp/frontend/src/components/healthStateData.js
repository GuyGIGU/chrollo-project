// The seven position-in-cycle states for the Market & Sector Health Board, in
// decision-proximity order — the SAME closed set + order the engine emits
// (core/pipeline/health_board.HealthState / the serve-boundary HealthStateName
// Literal). This is the single frontend source for how each state is NAMED,
// EXPLAINED, and ORDERED; the sort selector and the board bands both read it.
//
// Copy rule (the hardest AC): labels + blurbs are POSITIONAL, never imperative —
// "sitting on support", never "buy zone". The board is a health READ, not a
// signal. `decision` marks the at-a-rail / just-broke-out states so the board can
// emphasize them and recess the dormant ones (a two-tone attention ramp, NOT a
// per-state color).
export const HEALTH_STATES = [
  {
    key: 'near_resistance',
    label: 'Near resistance',
    decision: true,
    blurb: 'Coiled just under the top of its range, pressing the ceiling.',
  },
  {
    key: 'post_breakout_markup',
    label: 'Broke out',
    decision: true,
    blurb: 'Price has moved above the top of its established range (a coarse read, not a confirmed continuation).',
  },
  {
    key: 'near_support',
    label: 'On support',
    decision: true,
    blurb: 'Sitting on the floor of its range.',
  },
  {
    key: 'consolidating',
    label: 'Consolidating',
    decision: false,
    blurb: 'Working a two-sided range, price inside the rails.',
  },
  {
    key: 'trending',
    label: 'Trending',
    decision: false,
    blurb: 'A clean directional move with no established base.',
  },
  {
    key: 'deep_correction',
    label: 'Deep correction',
    decision: false,
    blurb: 'Fallen well below its recent high.',
  },
  {
    key: 'no_structure',
    label: 'No clear structure',
    decision: false,
    blurb: 'No readable base and nothing else to note.',
  },
];

// The canonical order of the closed set (mirrors HEALTH_STATE_ORDER on the engine).
export const HEALTH_STATE_ORDER = HEALTH_STATES.map((s) => s.key);

const BY_KEY = Object.fromEntries(
  HEALTH_STATES.map((s, index) => [s.key, { ...s, order: index }]),
);

// An unrecognized / missing state lands in a stable fallback bucket AFTER every
// known state, so a future engine state (or a bad value) is surfaced, never
// silently dropped or mislabeled.
export const UNKNOWN_HEALTH_STATE = {
  key: 'unknown',
  label: 'Unrecognized',
  decision: false,
  blurb: 'State not recognized by this build.',
  order: HEALTH_STATES.length,
};

export function healthStateMeta(key) {
  return BY_KEY[key] || { ...UNKNOWN_HEALTH_STATE, key: key || 'unknown' };
}
