function IbkrModeControls({
  ibkrStatus,
  isConnected,
  isLive,
  isGateway,
  reconnecting,
  switchingClient,
  switchingMode,
  onToggleClient,
  onToggleMode,
  onReconnect,
  onDisconnect,
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
  const connection = getConnectionPill({ ibkrStatus, isConnected, reconnecting });

  return (
    <div style={{ padding: '0 1.5rem', marginBottom: '1.5rem', display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
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
      <button
        type="button"
        onClick={connection.action === 'disconnect' ? onDisconnect : onReconnect}
        disabled={connection.disabled}
        title={connection.title}
        style={pillStyle({
          background: connection.background,
          color: connection.color,
          border: `1px solid ${connection.border}`,
          cursor: connection.disabled ? 'wait' : 'pointer',
          opacity: connection.disabled ? 0.6 : 1,
        })}
      >
        {connection.label}
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

const getConnectionPill = ({ ibkrStatus, isConnected, reconnecting }) => {
  if (reconnecting) {
    return {
      disabled: true,
      label: 'CONNECTING',
      title: 'Connecting to IBKR.',
      background: 'rgba(91,138,255,0.14)',
      border: 'rgba(91,138,255,0.45)',
      color: '#dce6ff',
    };
  }
  if (isConnected) {
    return {
      action: 'disconnect',
      label: 'IBKR CONNECTED',
      title: 'Release the IBKR API session so you can use it in TWS / TradingView.',
      background: 'rgba(34,197,94,0.14)',
      border: 'rgba(34,197,94,0.42)',
      color: 'var(--success)',
    };
  }
  if (ibkrStatus?.session_competition) {
    return {
      label: 'IBKR CONFLICT',
      title: 'Force a fresh connection. Will bump whatever else is logged into IBKR with this username.',
      background: 'rgba(229,72,77,0.14)',
      border: 'rgba(229,72,77,0.5)',
      color: 'var(--danger)',
    };
  }
  if (ibkrStatus?.daily_restart) {
    return {
      disabled: true,
      label: 'IBKR RESTART',
      title: 'Gateway is restarting; data will resume when IBKR is available.',
      background: 'rgba(91,138,255,0.14)',
      border: 'rgba(91,138,255,0.45)',
      color: '#dce6ff',
    };
  }
  return {
    label: 'CONNECT IBKR',
    title: 'Connect Chrollo to IBKR for read-only portfolio snapshots.',
    background: 'rgba(91,138,255,0.12)',
    border: 'rgba(91,138,255,0.42)',
    color: '#dce6ff',
  };
};

export default IbkrModeControls;
