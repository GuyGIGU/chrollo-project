// Imperative toast + confirm primitives — the in-app replacement for the
// browser-native alert()/window.confirm() dialogs. Module-level store so any
// code (hooks, async flows) can call toast()/confirmDialog(); FeedbackHost
// (mounted once in AppShell) subscribes and renders. No JSX here on purpose —
// the store stays react-refresh-clean and callable from plain modules.

let state = { toasts: [], confirm: null };
const listeners = new Set();
let nextToastId = 1;

const setState = (next) => {
  state = next;
  for (const listener of listeners) listener();
};

export const subscribeFeedback = (listener) => {
  listeners.add(listener);
  return () => listeners.delete(listener);
};

export const getFeedbackState = () => state;

// Show a transient toast. tone: 'info' | 'success' | 'danger' | 'warning'.
// Optional `action` = { label, run }: one inline action button (e.g. Undo) —
// clicking it runs the callback and dismisses the toast.
export function toast(message, { tone = 'info', duration = 6000, action = null } = {}) {
  const id = nextToastId++;
  setState({ ...state, toasts: [...state.toasts, { id, message, tone, duration, action }] });
  return id;
}

export function dismissToast(id) {
  if (!state.toasts.some((item) => item.id === id)) return;
  setState({ ...state, toasts: state.toasts.filter((item) => item.id !== id) });
}

// Ask the user to confirm; resolves true/false (Escape / backdrop / Cancel ->
// false). One dialog at a time, like window.confirm: a second request
// supersedes the first, which resolves false.
export function confirmDialog({ title = 'Confirm', message = '', confirmLabel = 'Confirm', cancelLabel = 'Cancel', danger = false } = {}) {
  return new Promise((resolve) => {
    state.confirm?.resolve(false);
    setState({ ...state, confirm: { title, message, confirmLabel, cancelLabel, danger, resolve } });
  });
}

export function settleConfirm(result) {
  const pending = state.confirm;
  if (!pending) return;
  setState({ ...state, confirm: null });
  pending.resolve(result);
}
