// The Action Center's readiness verdict.
//
// Council review 2026-09-07, finding 9: the strip summed four derived lists,
// each legitimately empty while its source was still loading, and painted
// "✓ Nothing needs action right now" on the very first frame — and again when a
// source had FAILED. The one surface designed to say "what needs me right now"
// stated affirmative safety when it knew nothing. Same class as the "Degraded,
// 0 setups" defect.
//
// So the all-clear is a CLAIM, and a claim needs evidence: it may only be made
// once all three sources have answered. Everything here is per-source load
// status the page already owns — no judgment is recomputed client-side (EC-28).

// Per source, the statuses that count as "this source has answered". Each set is
// the source hook's own vocabulary, kept next to the source it belongs to:
//   risk     — useLiveRisk: idle | loading | ready | stale | error
//   prices   — useLivePrices: idle (nothing to price) | loading | ready | error
//   screener — screenerStore: loading | ready | empty | never_scanned | error
const ANSWERED = {
  risk: new Set(['ready', 'stale']),
  prices: new Set(['idle', 'ready']),
  screener: new Set(['ready', 'empty', 'never_scanned']),
};

// Plain trading words, not hook names — this text reaches the operator.
const LABEL = {
  risk: 'open risk',
  prices: 'live prices',
  screener: 'the latest scan',
};

const ORDER = ['risk', 'prices', 'screener'];

export function actionCenterReadiness(statuses = {}) {
  const pending = [];
  const failed = [];
  for (const key of ORDER) {
    const status = statuses[key];
    if (status === 'error') failed.push(LABEL[key]);
    else if (!ANSWERED[key].has(status)) pending.push(LABEL[key]);
  }
  return { pending, failed, ready: pending.length === 0 && failed.length === 0 };
}

const listOf = (items) => (
  items.length <= 1 ? items.join('') : `${items.slice(0, -1).join(', ')} and ${items[items.length - 1]}`
);

// The single line the strip shows when it found nothing. Only the third branch
// is a claim of safety, and it is reachable only from a fully-answered read.
export function emptyStateLine(readiness) {
  if (readiness.failed.length) {
    return {
      text: `Cannot say what needs action — ${listOf(readiness.failed)} did not load.`,
      color: 'var(--danger)',
    };
  }
  if (readiness.pending.length) {
    return { text: `Reading ${listOf(readiness.pending)}…`, color: 'var(--text-faint)' };
  }
  return {
    text: '✓ Nothing needs action right now — no open risk, triggers, or fresh S-tier setups.',
    color: null,
  };
}

// The header count. A count derived from sources that have not all answered is a
// FLOOR, not a total, and says so with a '+' rather than presenting as complete.
export function countLabel(total, readiness) {
  if (total === 0) {
    if (readiness.failed.length) return 'cannot say';
    if (readiness.pending.length) return 'checking…';
    return 'all clear';
  }
  const suffix = total === 1 ? 'needs a look' : 'need a look';
  return readiness.ready ? `${total} ${suffix}` : `${total}+ ${suffix}`;
}

// A qualifier for the groups that ARE rendered, so a partial read is never
// presented as the whole picture. Null when there is nothing to qualify.
export function partialReadNote(readiness) {
  if (readiness.failed.length) return `${listOf(readiness.failed)} did not load`;
  if (readiness.pending.length) return `still reading ${listOf(readiness.pending)}`;
  return null;
}
