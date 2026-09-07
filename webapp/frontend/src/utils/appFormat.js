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

// The failing, operator-relevant health checks. One extraction shared by the
// topbar pill's tooltip and the diagnostics registry's "What is wrong right now"
// block, so the two can never disagree about what is red.
export const failingChecks = (health) =>
  Object.entries((health && health.checks) || {})
    .filter(([key, value]) => key !== 'ibkr' && value && value.ok === false)
    .map(([key, value]) => ({ key, ...value }));

export const buildHealthPill = (health) => {
  if (!health) return null;
  // label/reason arrive already resolved from the backend; the fallbacks only
  // cover an older backend that has not been restarted yet.
  const failing = failingChecks(health)
    .map(check => `${check.label || check.key}: ${check.reason || check.detail || 'failing'}`);
  const degraded = health.status !== 'ok';
  return {
    color: degraded ? 'var(--danger)' : 'var(--success)',
    label: degraded ? 'Degraded' : 'Healthy',
    title: failing.length ? `Degraded - ${failing.join('; ')}` : 'All systems OK',
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
  const label = scanStatus.status === 'stale_data' ? 'stale' : scanStatus.status;
  return `Last scan: ${when} | ${count} | ${label}`;
};
