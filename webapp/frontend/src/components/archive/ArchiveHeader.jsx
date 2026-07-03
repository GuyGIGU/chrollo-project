export default function ArchiveHeader({
  health,
  onAddSetup,
  onOpenAnalysis,
  onOpenHistory,
  onUpdateReturns,
  stats,
  updateMsg,
  updating,
}) {
  return (
    <>
      <div style={{ alignItems: 'center', display: 'flex', justifyContent: 'space-between' }}>
        <div style={{ color: 'var(--text-muted)' }}>
          {stats ? `${stats.total_setups} setups archived - ${stats.with_forward_returns} with forward returns` : 'Loading...'}
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          <HeaderButton onClick={onOpenHistory} title="Recent scan runs.">Scan History</HeaderButton>
          <HeaderButton onClick={() => onOpenAnalysis(false)} title="Run the archive analysis report in-app.">Analysis</HeaderButton>
          <HeaderButton onClick={onAddSetup}>+ Add Setup</HeaderButton>
          <button
            disabled={updating}
            onClick={onUpdateReturns}
            style={{
              background: updating ? 'var(--bg-hover)' : 'var(--accent-blue)',
              border: 'none',
              borderRadius: '6px',
              color: updating ? 'var(--text-muted)' : '#fff',
              cursor: updating ? 'not-allowed' : 'pointer',
              fontFamily: 'inherit',
              fontSize: '12px',
              fontWeight: '600',
              padding: '8px 16px',
              transition: 'all 0.2s',
            }}
          >
            {updating ? 'Updating Returns...' : 'Update Forward Returns'}
          </button>
        </div>
      </div>
      <ArchiveHealthStrip health={health} />
      {updateMsg && <UpdateMessage message={updateMsg} />}
    </>
  );
}

function ArchiveHealthStrip({ health }) {
  if (!health) return null;
  const tone = statusTone(health.status);
  const live = health.live || {};
  const checks = health.checks || [];

  return (
    <div style={{
      background: 'var(--bg-panel)',
      border: `1px solid ${tone.border}`,
      borderRadius: '6px',
      display: 'grid',
      gap: '12px',
      gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
      marginTop: '12px',
      padding: '12px 14px',
    }}>
      <HealthMetric
        label="Research Loop"
        tone={tone.color}
        value={healthStatusLabel(health.status)}
      />
      <HealthMetric
        label="Latest Live Scan"
        value={health.latest_scan_date || '-'}
        sub={health.latest_scan_age_days != null ? `${health.latest_scan_age_days}d old` : null}
      />
      <HealthMetric
        label="Live Episodes"
        value={live.episodes ?? 0}
        sub={`${live.with_20d_returns ?? 0} with 20d / ${live.with_60d_returns ?? 0} with 60d`}
      />
      <HealthMetric
        label="Return Backfill"
        value={`${live.pending_20d_returns ?? 0} / ${live.pending_60d_returns ?? 0}`}
        sub="overdue 20d / 60d"
      />
      {checks.length > 0 && (
        <div style={{
          borderTop: '1px solid var(--border-color)',
          display: 'grid',
          gap: '8px',
          gridColumn: '1 / -1',
          gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
          paddingTop: '10px',
        }}>
          {checks.map(check => <HealthCheck key={check.key} check={check} />)}
        </div>
      )}
    </div>
  );
}

function HealthMetric({ label, sub, tone, value }) {
  return (
    <div style={{ minWidth: 0 }}>
      <div style={{
        color: 'var(--text-faint)',
        fontSize: '9px',
        fontWeight: 700,
        letterSpacing: '0.08em',
        marginBottom: '6px',
        textTransform: 'uppercase',
      }}>{label}</div>
      <div style={{
        color: tone || 'var(--text-main)',
        fontFamily: "'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, Consolas, monospace",
        fontSize: '13px',
        fontVariantNumeric: 'tabular-nums',
        fontWeight: 700,
        overflow: 'hidden',
        textOverflow: 'ellipsis',
        whiteSpace: 'nowrap',
      }}>{value}</div>
      {sub && <div style={{ color: 'var(--text-muted)', fontSize: '11px', marginTop: '4px' }}>{sub}</div>}
    </div>
  );
}

function HealthCheck({ check }) {
  const tone = statusTone(check.status);
  return (
    <div style={{ alignItems: 'flex-start', display: 'flex', gap: '8px', minWidth: 0 }}>
      <span style={{
        background: tone.color,
        borderRadius: '999px',
        flex: '0 0 auto',
        height: '7px',
        marginTop: '5px',
        width: '7px',
      }} />
      <div style={{ minWidth: 0 }}>
        <div style={{ color: 'var(--text-main)', fontSize: '11px', fontWeight: 700 }}>{check.label}</div>
        <div style={{ color: 'var(--text-muted)', fontSize: '11px', lineHeight: 1.35 }}>{check.detail}</div>
      </div>
    </div>
  );
}

const healthStatusLabel = (status) => ({
  ok: 'Ready',
  watch: 'Watch',
  critical: 'Needs Attention',
}[status] || 'Unknown');

const statusTone = (status) => ({
  ok: { border: 'rgba(61, 211, 122, 0.35)', color: 'var(--success)' },
  watch: { border: 'rgba(240, 190, 60, 0.35)', color: 'var(--warning)' },
  critical: { border: 'rgba(242, 103, 112, 0.40)', color: 'var(--danger)' },
}[status] || { border: 'var(--border-color)', color: 'var(--text-muted)' });

function HeaderButton({ children, onClick, title }) {
  return (
    <button
      onClick={onClick}
      title={title}
      style={{
        background: 'transparent',
        border: '1px solid var(--border-color)',
        borderRadius: '6px',
        color: 'var(--text-main)',
        cursor: 'pointer',
        fontFamily: 'inherit',
        fontSize: '12px',
        fontWeight: '600',
        padding: '8px 16px',
        transition: 'all 0.2s',
      }}
    >
      {children}
    </button>
  );
}

function UpdateMessage({ message }) {
  return (
    <div style={{
      background: message.ok ? 'rgba(61,211,122,0.10)' : 'rgba(242,103,112,0.10)',
      border: `1px solid ${message.ok ? 'rgba(61,211,122,0.35)' : 'rgba(242,103,112,0.35)'}`,
      borderRadius: '6px',
      color: message.ok ? 'var(--success)' : 'var(--danger)',
      fontFamily: 'inherit',
      fontSize: '12px',
      margin: '8px 0 12px',
      padding: '8px 12px',
      whiteSpace: 'pre-wrap',
      wordBreak: 'break-word',
    }}>
      {message.ok ? 'OK: ' : 'Warning: '}{message.text}
    </div>
  );
}
