// Transient muting for the live risk-alert strip.
//
// Alert ids RECUR: `tradeTableUtils` mints them as `${tradeId}:stop:breached`,
// so the identical string is produced every time that condition fires. A
// dismissal keyed on the id and held for the whole session therefore silences
// the NEXT, genuine breach as well — the operator waves off a bad tick, price
// recovers, and the real re-breach never reaches the one surface whose job is to
// interrupt (council review 2026-09-07, finding 10; live-money surface).
//
// So a dismissal is bound to the firing EPISODE, not to the id: it lives only
// while the alert keeps firing without a break, and never past DISMISS_MAX_MS.
// The moment an alert stops firing, its dismissal is dropped and the next
// occurrence arrives as a fresh, visible alert. Snooze keeps its own purely
// time-based contract — "not for the next half hour" — which is why the two
// buttons remain distinct.

export const SNOOZE_MS = 30 * 60 * 1000;

// A backstop, not the primary expiry: the episode rule above is what normally
// ends a dismissal. This only bounds the pathological case where a level keeps
// firing continuously all day.
export const DISMISS_MAX_MS = 4 * 60 * 60 * 1000;

// `dismissed` is { alertId: dismissedAtMs }; `snoozedUntil` is { alertId: untilMs }.
export function isMuted(alertId, dismissed = {}, snoozedUntil = {}, now = Date.now()) {
  const dismissedAt = dismissed[alertId];
  if (dismissedAt != null && now - dismissedAt < DISMISS_MAX_MS) return true;
  const until = snoozedUntil[alertId];
  return until != null && until > now;
}

export function selectActiveAlerts(alerts = [], dismissed = {}, snoozedUntil = {}, now = Date.now()) {
  return alerts.filter((alert) => alert && !isMuted(alert.id, dismissed, snoozedUntil, now));
}

// Drop every dismissal whose alert is no longer firing (its episode ended) or
// whose backstop expired. Returns the SAME object when nothing changed, so the
// caller's setState is a no-op and the observing effect cannot loop.
export function pruneDismissed(dismissed = {}, alerts = [], now = Date.now()) {
  const firing = new Set(alerts.map((alert) => alert?.id));
  const next = {};
  let changed = false;
  for (const [id, dismissedAt] of Object.entries(dismissed)) {
    if (firing.has(id) && now - dismissedAt < DISMISS_MAX_MS) next[id] = dismissedAt;
    else changed = true;
  }
  return changed ? next : dismissed;
}
