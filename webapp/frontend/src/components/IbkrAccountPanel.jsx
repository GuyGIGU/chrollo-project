import { fmtMoney } from './portfolioFormat';

function IbkrAccountPanel({
  acct,
  stats,
  ibkrStatus,
  isConnected,
  isLive,
  reconnecting,
  onReconnect,
  onDisconnect,
}) {
  if (isConnected) {
    return (
      <PanelShell>
        <StatusLine color="var(--success)" label="Net Liquidation" />
        <MoneyLine value={acct.values?.NetLiquidation} />
        <SmallLine>Cash: {fmtMoney(acct.values?.TotalCashValue)}</SmallLine>
        <SmallLine color="var(--accent-blue)" marginBottom="6px">
          Buying Power: {fmtMoney(acct.values?.BuyingPower)}
        </SmallLine>
        <PanelButton
          onClick={onDisconnect}
          disabled={reconnecting}
          title="Release the IBKR API session so you can use it in TWS / TradingView."
        >
          Disconnect
        </PanelButton>
      </PanelShell>
    );
  }

  if (ibkrStatus?.session_competition) {
    return (
      <PanelShell>
        <StatusLine color="var(--danger)" label="Session Conflict" />
        <MoneyLine value={acct.values?.NetLiquidation} opacity={0.7} />
        <SmallLine color="var(--danger)" marginBottom="6px">Paused - TradingView/TWS has the session</SmallLine>
        <PanelButton
          onClick={onReconnect}
          disabled={reconnecting}
          title="Force a fresh connection. Will bump whatever else is logged into IBKR with this username."
          danger
        >
          {reconnecting ? 'Reconnecting...' : 'Reconnect'}
        </PanelButton>
      </PanelShell>
    );
  }

  if (ibkrStatus?.daily_restart) {
    return (
      <PanelShell>
        <StatusLine color="var(--accent-blue)" label="Daily Restart" pulse />
        <MoneyLine value={acct.values?.NetLiquidation} />
        <SmallLine color="var(--accent-blue)">Gateway restarting - data will resume</SmallLine>
      </PanelShell>
    );
  }

  if (ibkrStatus?.stale && acct.values?.NetLiquidation) {
    return (
      <PanelShell>
        <StatusLine color="var(--accent-yellow, #ca9f3c)" label="Reconnecting..." />
        <MoneyLine value={acct.values?.NetLiquidation} opacity={0.8} />
        <SmallLine color="var(--accent-yellow, #ca9f3c)">Last known - reconnecting...</SmallLine>
      </PanelShell>
    );
  }

  return (
    <PanelShell>
      <StatusLine color="var(--text-muted)" label="Journal P&L" />
      <div style={{ fontSize: '1.2rem', fontWeight: '700', color: '#fff' }}>
        ${Number.isFinite(Number(stats?.total_pnl)) ? Number(stats.total_pnl).toFixed(2) : '0.00'}
      </div>
      <SmallLine marginBottom="6px">IBKR disconnected</SmallLine>
      <PanelButton
        onClick={onReconnect}
        disabled={reconnecting}
        title={isLive
          ? 'Connect Chrollo to your live IBKR account for portfolio snapshots (read-only). You will confirm first.'
          : 'Connect Chrollo to your paper IBKR account.'}
        primary
      >
        {reconnecting ? 'Connecting...' : 'Connect IBKR'}
      </PanelButton>
    </PanelShell>
  );
}

function PanelShell({ children }) {
  return <div className="account-info">{children}</div>;
}

function StatusLine({ color, label, pulse = false }) {
  return (
    <div style={{ color, fontSize: '11px', marginBottom: '0.2rem', display: 'flex', alignItems: 'center', gap: 6 }}>
      <span style={{
        width: 6,
        height: 6,
        borderRadius: '50%',
        background: color,
        animation: pulse ? 'pulse-subtle 2s ease-in-out infinite' : 'none',
      }} />
      {label}
    </div>
  );
}

function MoneyLine({ value, opacity = 1 }) {
  return (
    <div style={{ fontSize: '1.2rem', fontWeight: '700', color: '#fff', opacity }}>
      {fmtMoney(value)}
    </div>
  );
}

function SmallLine({ children, color = 'var(--text-muted)', marginBottom = 0 }) {
  return <div style={{ fontSize: '10px', color, marginBottom }}>{children}</div>;
}

function PanelButton({ children, danger = false, primary = false, ...props }) {
  const color = danger ? 'var(--danger)' : primary ? 'var(--accent-blue)' : 'var(--text-muted)';
  return (
    <button
      type="button"
      style={{
        fontSize: '10px',
        fontWeight: 600,
        letterSpacing: '0.5px',
        padding: '3px 10px',
        borderRadius: 'var(--radius-pill, 999px)',
        background: danger || primary ? `${color}26` : 'transparent',
        color,
        border: `1px solid ${danger || primary ? color : 'var(--border-color)'}`,
        cursor: props.disabled ? 'wait' : 'pointer',
        opacity: props.disabled ? 0.6 : 1,
        fontFamily: 'inherit',
      }}
      {...props}
    >
      {children}
    </button>
  );
}

export default IbkrAccountPanel;
