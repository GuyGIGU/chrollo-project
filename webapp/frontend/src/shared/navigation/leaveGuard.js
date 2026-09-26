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
// Same armed flag for every exit, so a page can never be protected against a
// reload and not against a click. The app runs on `BrowserRouter`, not a data
// router, so react-router's `useBlocker` is unavailable and each exit asks this
// registry itself. Covered today: `beforeunload` (reload / tab close), the top
// nav, and the topbar's "+ New trade" button, which navigates to the journal.
// NOT covered: the browser's own Back button — `beforeunload` does not fire on
// a history pop and nothing listens for `popstate`. Closing that needs the
// router converted to `createBrowserRouter`, which is a bigger change than the
// finding (council review 2026-09-07, A2 — the earlier claim that the top nav
// was the single funnel out of a route was wrong on both counts).

// Explicit extension: node --test resolves this file for real (vite would let
// an extensionless path through, and this src tree has a case-twin .js/.jsx
// pair that an extensionless import has already broken a build over).
import { confirmDialog } from '../components/feedback.js';

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
// unarmed guard never touches a click at all. `to`/`currentPath` are optional:
// a click on the tab you are ALREADY on navigates nowhere and discards nothing,
// so asking "leave and discard?" there is a prompt whose Yes does nothing
// (council review 2026-09-07, A9).
export function shouldInterceptNavClick(event, to = null, currentPath = null) {
  if (!event || event.defaultPrevented || event.button !== 0) return false;
  if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return false;
  if (to != null && currentPath != null && samePath(to, currentPath)) return false;
  return leaveGuardMessage() != null;
}

// Trailing slashes only — these are the app's own route strings, not user input.
const samePath = (a, b) => a.replace(/\/+$/, '') === b.replace(/\/+$/, '');

// Decide whether a navigation away may proceed. `ask` is injected (defaulted by
// the caller that owns a dialog) so the rule itself — armed means confirm,
// disarmed means straight through — is testable without a DOM.
export async function confirmLeave(ask) {
  const message = leaveGuardMessage();
  if (message == null) return true;
  return Boolean(await ask(message));
}

// The ONE bound form: every exit asks with the same words. A second exit that
// wrote its own dialog would drift, and the "+ New trade" button shipped with
// no dialog at all — a click inches from the nav that still discarded marks.
export function confirmLeaveWithDialog() {
  return confirmLeave(message => confirmDialog({
    title: 'Unsaved marks',
    message,
    confirmLabel: 'Leave and discard',
    cancelLabel: 'Stay',
    danger: true,
  }));
}
