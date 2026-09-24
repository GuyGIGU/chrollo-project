// The decision-proximity ordering for the Market & Sector Health Board — a PURE
// selector the board recomputes each render (never stored in state; the engine is
// the single source of each member's classification, the frontend only orders and
// groups). Kept out of the JSX component so it stays Node-testable.
import { healthStateMeta, HEALTH_STATES } from '../../../shared/setup/healthStateData.js';

const num = (value, fallback) => {
  const n = Number(value);
  return value == null || !Number.isFinite(n) ? fallback : n;
};

// Within a state bucket, the tiebreak that surfaces the most decision-proximate
// member first. A member with a missing value sorts to the back of its bucket.
function railProximity(member) {
  switch (member.state) {
    case 'near_resistance':
      // Closest to the ceiling (box_pos -> 1) first: ascending (1 - box_pos).
      return num(1 - member.box_pos, Infinity);
    case 'near_support':
      // Closest to the floor (box_pos -> 0) first: ascending box_pos.
      return num(member.box_pos, Infinity);
    case 'post_breakout_markup':
      // Freshest breakout (smallest extension above R) first.
      return num(member.breakout_extension, Infinity);
    default:
      return 0; // other states fall straight through to the ticker tiebreak
  }
}

// Stable comparator: state bucket order, then rail proximity, then ticker (so
// equal members never reorder run-to-run).
export function compareHealthMembers(a, b) {
  const orderDelta = healthStateMeta(a.state).order - healthStateMeta(b.state).order;
  if (orderDelta !== 0) return orderDelta;
  const proximityDelta = railProximity(a) - railProximity(b);
  if (proximityDelta < 0) return -1;
  if (proximityDelta > 0) return 1; // (Infinity - finite) and (finite - Infinity) resolve here
  return String(a.ticker).localeCompare(String(b.ticker)); // NaN (both missing) lands here too
}

export function sortHealthMembers(members) {
  return [...(members || [])].sort(compareHealthMembers);
}

// Group the sorted members into decision-proximity BANDS (one per present state,
// in canonical order) so the board can render labeled sections with counts. Built
// off the sort, so within-band order is preserved and the bands come out ordered.
export function groupHealthMembers(members) {
  const sorted = sortHealthMembers(members);
  const bands = [];
  for (const member of sorted) {
    const meta = healthStateMeta(member.state);
    let band = bands[bands.length - 1];
    if (!band || band.key !== meta.key) {
      band = { ...meta, members: [] };
      bands.push(band);
    }
    band.members.push(member);
  }
  return bands;
}

// The count of KNOWN states (for tests / callers that need the closed-set size).
export const KNOWN_STATE_COUNT = HEALTH_STATES.length;
