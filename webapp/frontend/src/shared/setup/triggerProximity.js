// The ONE near-trigger judgment (EC-3; council 2026-08-22 finding 13). Live
// prices are client-polled between scans, so this judgment legitimately lives
// client-side — which is exactly why it lives ONCE: three surfaces carried
// hand-typed copies whose denominators had already diverged (the home zones
// divided by the trigger, the lens and the grid sort by price).
//
// Convention, chosen once: distance is THE MOVE PRICE MUST MAKE —
// (trigger − live) / live. "2% away" means price needs a +2% move to reach
// the trigger. Negative = already above it.
import { finiteOrNull } from '../formatting/format.js';

export const NEAR_TRIGGER_PCT = 0.02; // within 2% below the trigger

// Fraction of upside move needed to reach the trigger; null when unknowable.
export function triggerDistanceFrac(data, live) {
  const price = finiteOrNull(live);
  const trigger = finiteOrNull(data?.trigger);
  if (price == null || trigger == null || price <= 0) return null;
  return (trigger - price) / price;
}

export function triggerFired(data, live) {
  const distance = triggerDistanceFrac(data, live);
  return distance != null && distance <= 0;
}

// Near = below the trigger but within the band; fired names are not "near".
export function nearTriggerFrac(data, live) {
  const distance = triggerDistanceFrac(data, live);
  return distance != null && distance > 0 && distance <= NEAR_TRIGGER_PCT
    ? distance
    : null;
}
