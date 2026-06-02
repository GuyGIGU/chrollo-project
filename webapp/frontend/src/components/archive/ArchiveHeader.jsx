export default function ArchiveHeader({
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
      {updateMsg && <UpdateMessage message={updateMsg} />}
    </>
  );
}

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
      background: message.ok ? 'rgba(63,185,80,0.10)' : 'rgba(248,81,73,0.10)',
      border: `1px solid ${message.ok ? 'rgba(63,185,80,0.35)' : 'rgba(248,81,73,0.35)'}`,
      borderRadius: '6px',
      color: message.ok ? '#3fb950' : '#f85149',
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
