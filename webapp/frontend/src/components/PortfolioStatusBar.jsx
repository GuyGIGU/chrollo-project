import React from 'react';
import { fmtTime } from './portfolioFormat';

const pillStyle = (background, color, border = color) => ({
  padding: '4px 10px',
  borderRadius: '999px',
  fontSize: 10,
  fontWeight: 800,
  background,
  color,
  border: `1px solid ${border}`,
  display: 'inline-flex',
  alignItems: 'center',
  gap: 6,
  textTransform: 'uppercase',
  whiteSpace: 'nowrap',
});

const Dot = ({ color, glow }) => (
  <span style={{
    width: 6,
    height: 6,
    borderRadius: '50%',
    background: color,
    boxShadow: glow ? `0 0 6px ${color}` : 'none',
  }} />
);

const Notice = ({ tone, title, body, action, onAction }) => {
  const colors = {
    danger: ['rgba(var(--danger-rgb),0.12)', 'rgba(var(--danger-rgb),0.32)', 'var(--danger)'],
    info: ['rgba(91,138,255,0.10)', 'rgba(91,138,255,0.28)', 'var(--accent-blue)'],
    warning: ['rgba(var(--warning-rgb),0.10)', 'rgba(var(--warning-rgb),0.28)', 'var(--warning)'],
  }[tone];

  return (
    <div style={{ padding: '12px 14px', borderRadius: 8, background: colors[0], border: `1px solid ${colors[1]}`, color: colors[2], marginBottom: 10 }}>
      <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
        <div style={{ flex: 1 }}>
          <div style={{ fontWeight: 800, fontSize: 12 }}>{title}</div>
          <div style={{ color: 'var(--text-muted)', fontSize: 11, marginTop: 3 }}>{body}</div>
        </div>
        {action && (
          <button type="button" onClick={onAction} style={buttonStyle(true)}>
            {action}
          </button>
        )}
      </div>
    </div>
  );
};

const buttonStyle = (primary = false) => ({
  padding: '6px 12px',
  borderRadius: 6,
  border: primary ? '1px solid var(--accent-active)' : '1px solid var(--border-color)',
  background: primary ? 'var(--myth-soft)' : 'transparent',
  color: primary ? 'var(--myth)' : 'var(--text-muted)',
  fontWeight: 700,
  fontSize: 11,
  cursor: 'pointer',
  whiteSpace: 'nowrap',
  fontFamily: 'inherit',
});

const fmtSignedMoney = (value) => {
  if (value == null || !Number.isFinite(Number(value))) return null;
  const n = Number(value);
  return `${n >= 0 ? '+' : '−'}$${Math.abs(n).toLocaleString('en-US', { maximumFractionDigits: 0 })}`;
};

// Ambient open-risk readout: glanceable from the cockpit chrome, deliberately
// quieter than the connection pills. The at-risk clause reads as ambient tinted
// text (NOT a bold full-saturation phrase competing with the pills — the loud
// stop signal belongs on the Open Book flag, where the trader acts), appears only
// when something is at risk, and the whole strip mutes + flags "stale" when the
// connection behind the numbers is degraded so frozen figures don't read confident.
const OpenRiskStrip = ({ riskSummary, degraded }) => {
  if (!riskSummary || !riskSummary.nOpen) return null;
  const pnl = riskSummary.totalUnrealizedPnl;
  const pnlColor = degraded || pnl == null ? 'var(--text-muted)' : pnl >= 0 ? 'var(--success)' : 'var(--danger)';
  const parts = [];
  if (riskSummary.nBreached) parts.push(`${riskSummary.nBreached} through stop`);
  if (riskSummary.nDanger) parts.push(`${riskSummary.nDanger} near stop`);
  if (riskSummary.nWarning) parts.push(`${riskSummary.nWarning} watch`);
  const atRiskColor = degraded ? 'var(--text-muted)' : (riskSummary.nBreached || riskSummary.nDanger) ? 'var(--danger)' : 'var(--warning)';
  const partial = riskSummary.nPriced != null && riskSummary.nPriced < riskSummary.nOpen;
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8, color: 'var(--text-muted)', fontSize: 11, fontVariantNumeric: 'tabular-nums', opacity: degraded ? 0.6 : 1 }}>
      <span>
        Open P&amp;L <strong style={{ color: pnlColor }}>{fmtSignedMoney(pnl) ?? '—'}</strong>
        <span style={{ opacity: 0.6 }}> · {riskSummary.nOpen} pos</span>
        {partial && <span style={{ opacity: 0.6 }}> · {riskSummary.nPriced}/{riskSummary.nOpen} priced</span>}
      </span>
      {parts.length > 0 && <span style={{ color: atRiskColor }}>{parts.join(' · ')}</span>}
      {degraded && <span style={{ opacity: 0.7 }}>stale</span>}
    </span>
  );
};

const connectionLabel = ({ available, connected, dailyRestart, sessionCompetition }) => {
  if (!available) return ['Not installed', 'rgba(136,136,150,0.15)', 'var(--text-muted)'];
  if (sessionCompetition) return ['Session conflict', 'rgba(var(--danger-rgb),0.14)', 'var(--danger)'];
  if (dailyRestart) return ['Daily restart', 'rgba(91,138,255,0.12)', 'var(--accent-blue)'];
  if (connected) return ['Connected', 'var(--success-bg)', 'var(--success)'];
  return ['Reconnecting', 'rgba(var(--warning-rgb),0.14)', 'var(--warning)'];
};

const PortfolioStatusBar = ({
  status,
  sseStatus,
  lastUpdate,
  stale,
  hasData,
  dailyRestart,
  sessionCompetition,
  onReconnect,
  onDisconnect,
  riskSummary,
}) => {
  const isLive = status?.mode === 'live';
  const connected = !!status?.connected;
  const [label, bg, fg] = connectionLabel({
    available: !!status?.available,
    connected,
    dailyRestart,
    sessionCompetition,
  });

  return (
    <>
      {sessionCompetition && (
        <Notice
          tone="danger"
          title="IBKR session conflict"
          body="Another platform is using the same IBKR API session. Reconnect when you are done there."
          action="Reconnect"
          onAction={onReconnect}
        />
      )}
      {dailyRestart && !sessionCompetition && (
        <Notice tone="info" title="IB Gateway daily restart" body="Data is preserved and will resume automatically." />
      )}
      {stale && hasData && !dailyRestart && !sessionCompetition && !connected && (
        <Notice tone="warning" title="Showing last-known data" body="The live stream is reconnecting automatically." />
      )}
      {stale && !hasData && !dailyRestart && !sessionCompetition && !connected && (
        <Notice
          tone="warning"
          title="Waiting for portfolio data"
          body="Connect IBKR to load a fresh account snapshot. Nothing cached is available yet."
          action="Connect IBKR"
          onAction={onReconnect}
        />
      )}

      <section className="instrument-tile" style={{
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        flexWrap: 'wrap',
        padding: '12px 14px',
        background: 'var(--bg-panel)',
        border: '1px solid var(--border-color)',
        borderRadius: 8,
        marginBottom: 16,
      }}>
        <span style={pillStyle(isLive ? 'rgba(var(--danger-rgb),0.12)' : 'rgba(91,138,255,0.12)', isLive ? 'var(--danger)' : 'var(--accent-blue)')}>
          <Dot color={isLive ? 'var(--danger)' : 'var(--accent-blue)'} glow={isLive} />
          {isLive ? 'Live' : 'Paper'}
        </span>
        <span style={pillStyle(bg, fg)}>
          <Dot color={fg} glow={connected} />
          IBKR {label}
        </span>
        <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>Stream: {sseStatus === 'reconnecting' ? 'retrying' : sseStatus}</span>
        {status?.host && <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>{status.host}:{status.port} / client {status.client_id}</span>}
        {lastUpdate && <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>Updated {fmtTime(lastUpdate)}</span>}
        <OpenRiskStrip riskSummary={riskSummary} degraded={!connected || sessionCompetition || stale} />
        {status?.available && connected && (
          <button type="button" onClick={onDisconnect} title="Release the IBKR API session." style={{ ...buttonStyle(), marginLeft: 'auto' }}>
            Disconnect
          </button>
        )}
        {status?.available && !connected && !sessionCompetition && !dailyRestart && (
          <button type="button" onClick={onReconnect} style={{ ...buttonStyle(true), marginLeft: 'auto' }}>
            Connect IBKR
          </button>
        )}
      </section>
    </>
  );
};

export default PortfolioStatusBar;
