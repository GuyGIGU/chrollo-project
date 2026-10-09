// One off-scan card's chart state, as a value keyed by its ticker (build task 15 of the two-eyes reader).
//
// The engine's ONE state word for a chart the scan did not list arrives from `/screener-data/state/<ticker>`,
// already resolved (EC-28): "not scanned" with the door's leg and its distance in ranges, or the lines and their
// facts. Two things are NOT words and never borrow one of his ten: a read still on its way (pending) and a read
// that failed (the server said so, or the fetch did). And an answer is only ever shown for the ticker it was asked
// about: the hook used to keep the last answer and swap it only when the next arrived, so a card handed a new
// ticker kept saying the OLD ticker's word and lines while it loaded, and for good when the fetch failed.
import { fmtDay, fx } from '../../../shared/formatting/format.js';

export const pendingEntry = (ticker) => ({ ticker, screen: 'pending', body: null });

// An answer for `ticker`: ready with its word, or failed (no body, or the server's own failed read).
export const settledEntry = (ticker, body) => (
  body == null || body.failed === true
    ? { ticker, screen: 'failed', body: body ?? null }
    : { ticker, screen: 'ready', body }
);

// What the card shows for `ticker`: its own answer, or "pending" — never another ticker's.
export const entryFor = (entry, ticker) => (entry && entry.ticker === ticker ? entry : pendingEntry(ticker));

// The card's line. Null with no entry, so the card keeps its own copy.
export const chartStateLine = (entry) => {
  if (!entry) return null;
  if (entry.screen === 'pending') return 'reading the chart…';
  if (entry.screen === 'failed') return 'the read failed';
  const state = entry.body;
  if (!state?.state) return null;
  let line = state.why ? `${state.state}: ${state.why}` : state.state;
  // The days that ride beside a word that counts them, never written into the word.
  if (state.days != null) line += ` (${fx(state.days, 0)} days)`;
  if (state.distance_ranges != null) line += ` (${fx(state.distance_ranges, 1)} ranges)`;
  if (state.R != null && state.S != null) {
    line += ` · R ${fx(state.R, 2)} / S ${fx(state.S, 2)} · open ${fmtDay(state.open)}`;
    if (state.age != null) line += ` · ${fx(state.age, 0)} days`;
    if (state.turns_at_r != null) line += ` · turns ${fx(state.turns_at_r, 0)} / ${fx(state.turns_at_s, 0)}`;
  }
  return line;
};
