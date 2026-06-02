function IbkrModeControls({
  isLive,
  isGateway,
  switchingClient,
  switchingMode,
  onToggleClient,
  onToggleMode,
}) {
  const clientTitle = switchingClient
    ? 'Switching...'
    : isGateway
      ? `Click to switch to TWS (${isLive ? 7496 : 7497})`
      : `Click to switch to IB Gateway (${isLive ? 4001 : 4002})`;
  const modeTitle = switchingMode
    ? 'Switching...'
    : isLive
      ? `Click to switch to PAPER (port ${isGateway ? 4002 : 7497})`
      : `Click to switch to LIVE - real money (port ${isGateway ? 4001 : 7496})`;

  return (
    <div style={{ padding: '0 1.5rem', marginBottom: '1.5rem', display: 'flex', gap: '8px' }}>
      <button
        type="button"
        onClick={onToggleClient}
        disabled={switchingClient}
        title={clientTitle}
        style={pillStyle({
          cursor: switchingClient ? 'wait' : 'pointer',
          opacity: switchingClient ? 0.6 : 1,
        })}
      >
        {switchingClient ? '...' : (isGateway ? 'GATEWAY' : 'TWS')}
      </button>
      <button
        type="button"
        onClick={onToggleMode}
        disabled={switchingMode}
        title={modeTitle}
        style={pillStyle({
          background: isLive ? 'var(--danger)' : 'rgba(255,255,255,0.08)',
          color: isLive ? '#fff' : 'var(--text-muted)',
          border: isLive ? '1px solid var(--danger)' : '1px solid var(--border-color)',
          boxShadow: isLive ? '0 0 10px rgba(229,72,77,0.5)' : 'none',
          cursor: switchingMode ? 'wait' : 'pointer',
          opacity: switchingMode ? 0.6 : 1,
        })}
      >
        {switchingMode ? '...' : (isLive ? 'LIVE' : 'PAPER')}
      </button>
    </div>
  );
}

const pillStyle = (overrides = {}) => ({
  fontSize: '9px',
  fontWeight: 700,
  letterSpacing: '1px',
  padding: '3px 8px',
  borderRadius: 'var(--radius-pill, 999px)',
  background: 'rgba(255,255,255,0.08)',
  color: 'var(--text-muted)',
  border: '1px solid var(--border-color)',
  fontFamily: 'inherit',
  ...overrides,
});

export default IbkrModeControls;
