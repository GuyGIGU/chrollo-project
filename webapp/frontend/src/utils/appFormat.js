export const fmtScanTime = (value) => {
  if (!value) return 'none';
  const dt = new Date(value);
  if (Number.isNaN(dt.getTime())) return 'unknown';
  return dt.toLocaleString([], {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
};

export const scanStatusColor = (status) => {
  if (status === 'ok') return 'var(--success)';
  if (status === 'running') return 'var(--accent-blue)';
  if (status === 'failed' || status === 'stale_data') return 'var(--danger)';
  return 'var(--text-muted)';
};

export const tabTitle = (activeTab) => {
  if (activeTab === 'home') return 'Command Center';
  if (activeTab === 'dashboard') return 'Trading Journal Analytics';
  if (activeTab === 'options') return 'Options Trades';
  if (activeTab === 'portfolio') return 'Live IBKR Portfolio';
  if (activeTab === 'archive') return 'Setup Archive & Calibration';
  return 'Wyckoff Screener Scans';
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
