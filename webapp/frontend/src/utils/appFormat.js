import { dateTimeShort } from './format.js';

export const fmtScanTime = (value) => {
  if (!value) return 'none';
  return dateTimeShort(value) ?? 'unknown';
};

export const scanStatusColor = (status) => {
  if (status === 'ok') return 'var(--success)';
  if (status === 'running') return 'var(--accent-blue)';
  if (status === 'failed' || status === 'stale_data') return 'var(--danger)';
  return 'var(--text-muted)';
};

export const buildHealthPill = (health) => {
  if (!health) return null;
  const checks = health.checks || {};
  const failing = Object.entries(checks)
    .filter(([key, value]) => key !== 'ibkr' && value && value.ok === false)
    .map(([key, value]) => `${key}${value.detail ? `: ${value.detail}` : ''}`);
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
  const count = Number.isFinite(Number(scanStatus.n_setups))
    ? `${Number(scanStatus.n_setups)} setups`
    : 'setup count unknown';
  const label = scanStatus.status === 'stale_data' ? 'stale' : scanStatus.status;
  return `Last scan: ${when} | ${count} | ${label}`;
};
