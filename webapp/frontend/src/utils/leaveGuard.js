// The app's ONE "leaving this surface loses unsaved work" registry.
//
// Council review 2026-09-07, finding 8: the calibration sitting armed
// `beforeunload`, which covers a reload and a tab close — but NOT an in-app
// route change, and the top nav sits two centimetres above the chart. One
// misclick wiped hand-drawn ground truth, the most expensive and least
// reproducible data the project holds. The guard was also armed only on a
// COMPLETE box, so rails-placed-but-LPS-pending was unprotected even on a real
// reload.
//
// Same armed flag for both exits, so a page can never be protected against a
// reload and not against a click. The app runs on `BrowserRouter`, not a data
// router, so react-router's `useBlocker` is unavailable; the top nav is the one
// funnel out of a route and asks this registry before it navigates.

let armedMessage = null;

export function armLeaveGuard(message) {
  armedMessage = message;
}

export function disarmLeaveGuard() {
  armedMessage = null;
}

export function leaveGuardMessage() {
  return armedMessage;
}

// Is this in-app nav click one the guard must intercept? A modified or
// non-primary click is left alone so open-in-new-tab keeps working, and an
// unarmed guard never touches a click at all.
export function shouldInterceptNavClick(event) {
  if (!event || event.defaultPrevented || event.button !== 0) return false;
  if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return false;
  return leaveGuardMessage() != null;
}

// Decide whether a navigation away may proceed. `ask` is injected (defaulted by
// the caller that owns a dialog) so the rule itself — armed means confirm,
// disarmed means straight through — is testable without a DOM.
export async function confirmLeave(ask) {
  const message = leaveGuardMessage();
  if (message == null) return true;
  return Boolean(await ask(message));
}
