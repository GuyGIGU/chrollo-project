// Extension-explicit: this module is in the node --test battery, and Node's ESM
// resolver (unlike Vite) does not guess one.
import { RUN_STATUS_LABELS, RUN_VERDICT_LABELS, RUN_VERDICT_TONES } from '../components/wireVocabulary.js';
import { dateTimeShort, finiteOrNull, fmtInt } from './format.js';

export const fmtScanTime = (value) => {
  if (!value) return 'none';
  return dateTimeShort(value) ?? 'unknown';
};

export const scanStatusColor = (status) => {
  if (status === 'ok') return 'var(--success)';
  if (status === 'running') return 'var(--accent-blue)';
  // 'aborted' belongs on this arm: the backend's own health check counts it as
  // not-ok, and the scan-history table (which used to carry a private copy of
  // this map) has always painted it danger. Folding the twin without it would
  // have quietly turned aborted runs grey.
  if (status === 'failed' || status === 'stale_data' || status === 'aborted') return 'var(--danger)';
  return 'var(--text-muted)';
};

// The failing, operator-relevant health checks — a PASS-THROUGH of the verdict
// the backend already resolved (`/health` -> `failing`), shared by the topbar
// pill's tooltip and the registry's "What is wrong right now" block. Which
// checks count as a failure is chapter membership, so it is decided server-side
// and never re-derived here (EC-28); this used to filter `health.checks` in JS,
// which meant exempting a check server-side still left it listed here.
export const failingChecks = (health) =>
  (health && Array.isArray(health.failing) ? health.failing : []);

export const buildHealthPill = (health) => {
  if (!health) return null;
  // verdict/label/reason arrive already resolved from the backend; the fallbacks
  // only cover an older backend that has not been restarted yet.
  const failing = failingChecks(health)
    .map(check => `${check.label || check.key}: ${check.reason || 'failing'}`);
  const degraded = health.status !== 'ok';
  // The one word the operator decides on. READ off the wire, never worked out
  // here (EC-28) — which of the two states he is in is a judgment, and the
  // engine has already made it.
  const label = degraded ? (RUN_VERDICT_LABELS[health.verdict] || 'Degraded') : 'Healthy';
  const color = degraded ? (RUN_VERDICT_TONES[health.verdict] || 'var(--danger)') : 'var(--success)';
  return {
    color,
    label,
    title: failing.length ? `${label} - ${failing.join('; ')}` : 'All systems OK',
  };
};

export const buildScanStatusText = (scanStatus) => {
  if (!scanStatus || scanStatus.status === 'never') return 'Last scan: none';
  const when = fmtScanTime(scanStatus.finished_at || scanStatus.started_at);
  // The house null guard, imported — never re-declared. Number(null) coerces to
  // zero, and zero is a finite number, so the inline guard this replaces
  // rendered an interrupted run's missing count as "0 setups" and read as "the
  // scan ran and found nothing". finiteOrNull short-circuits on null first, so a
  // real zero still says "0 setups" and only an unknown says unknown.
  const n = finiteOrNull(scanStatus.n_setups);
  const count = n == null ? 'setup count unknown' : `${fmtInt(n)} setups`;
  // The one status vocabulary, shared with the registry's Status column — the
  // pill used to translate stale_data here while the registry three inches
  // below printed the raw wire word.
  const label = RUN_STATUS_LABELS[scanStatus.status] || scanStatus.status;
  return `Last scan: ${when} | ${count} | ${label}`;
};
