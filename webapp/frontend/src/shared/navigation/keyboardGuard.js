// The app's ONE "is this keystroke for the page?" rule for page-level keys: the
// '?' key sheet, '/' to the search box, the screener card keys and the
// calibration list's Up/Down. A key is the page's only when the operator is not
// typing in a field, holds no command modifier (a browser or OS shortcut), and
// no dialog is up (the big chart, a confirm, a popover) — a dialog owns its keys.
// Pure (the document is injectable), so node --test pins it.

export function isTypingTarget(target) {
  if (!target) return false;
  const tag = target.tagName;
  return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || Boolean(target.isContentEditable);
}

// Shift is NOT a command modifier: '?' is Shift+/, and '/' is Shift+7 on some layouts.
export function hasCommandModifier(event) {
  return Boolean(event?.ctrlKey || event?.metaKey || event?.altKey);
}

export function dialogOpen(doc = globalThis.document) {
  return doc?.querySelector('[role="dialog"]') != null;
}

// A MODAL dialog is up that `el` is not part of. A screener card keeps DOM focus
// after it opens the big chart (the lens does not take it), so its own Enter/W/L
// would still answer — and act on the card BEHIND the chart, not the one on
// screen. Modal only: the command bar's Filters/Data popovers and the Scale
// popover are dialogs too, but non-modal (Tab is free to leave them), and a card
// reached by Tab with one still open must keep its keys.
export function dialogOpenOutside(el, doc = globalThis.document) {
  const dialogs = doc?.querySelectorAll('[role="dialog"][aria-modal="true"]') ?? [];
  return [...dialogs].some((dialog) => !dialog.contains(el));
}

export function isPageKeystroke(event, doc = globalThis.document) {
  return !hasCommandModifier(event) && !isTypingTarget(event?.target) && !dialogOpen(doc);
}
