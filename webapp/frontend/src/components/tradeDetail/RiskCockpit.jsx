import { useMemo } from 'react';
import useTradeLivePrices from '../../hooks/useTradeLivePrices';
import { buildTradeAlerts, deriveTradeRow, fmtInt, fmtMoney } from '../../utils/tradeTableUtils';

const fx = (value, digits) => (
  value == null || !Number.isFinite(Number(value)) ? '-' : Number(value).toFixed(digits)
);

export default function RiskCockpit({ trade }) {
  const trades = useMemo(() => (trade ? [trade] : []), [trade]);
  const priceFor = useTradeLivePrices(trades);
  const derived = useMemo(
    () => (trade ? deriveTradeRow(trade, priceFor) : null),
    [priceFor, trade],
  );

  if (!derived || (derived.status !== 'open' && derived.status !== 'partial')) return null;

  const cockpitAlerts = buildTradeAlerts(trade, derived);
  const topAlert = cockpitAlerts[0] || null;
  const nextTarget = derived.nextTarget;
  const liveSource = sourceLabel(derived.currentExitSource);
  const nextTargetValue = nextTarget
    ? `${nextTarget.label} $${fmtMoney(nextTarget.price)}`
    : '-';
  const nextTargetSub = nextTarget
    ? targetDistanceLabel(nextTarget)
    : derived.targetLadder.length ? 'Targets complete' : 'No target';

  return (
    <section style={cockpitStyle}>
      <div style={cockpitHeaderStyle}>
        <div>
          <div style={eyebrowStyle}>Live Cockpit</div>
          <strong style={titleStyle}>{trade.ticker}</strong>
        </div>
        <span className={`status-cell ${derived.status}`}>{derived.status}</span>
      </div>

      {topAlert && (
        <div style={{ ...alertStyle, ...alertToneStyle(topAlert.level) }}>
          <strong>{topAlert.title}</strong>
          <span>{topAlert.detail}</span>
        </div>
      )}

      <div style={metricGridStyle}>
        <Metric
          label="Live Price"
          value={derived.currentExit != null ? `$${fmtMoney(derived.currentExit)}` : '-'}
          sub={liveSource}
        />
        <Metric
          label="P&L"
          value={formatSignedMoney(derived.pnl)}
          sub={formatR(derived.rValue, true)}
          tone={toneForSigned(derived.pnl)}
        />
        <Metric
          label="To Stop"
          value={formatPct(derived.distToStopPct)}
          sub={formatR(derived.rToStop)}
          tone={derived.stopRiskTone}
        />
        <Metric
          label="Next Target"
          value={nextTargetValue}
          sub={nextTargetSub}
          tone={nextTarget ? 'target' : null}
        />
      </div>

      <TargetLadder targets={derived.targetLadder} />
    </section>
  );
}

function Metric({ label, sub, tone, value }) {
  return (
    <div style={metricStyle}>
      <span style={metricLabelStyle}>{label}</span>
      <strong style={{ ...metricValueStyle, color: toneColor(tone) }}>{value}</strong>
      <small style={metricSubStyle}>{sub || '-'}</small>
    </div>
  );
}

function TargetLadder({ targets }) {
  if (!targets.length) {
    return <div style={emptyTargetsStyle}>No targets set.</div>;
  }

  return (
    <div style={targetListStyle}>
      {targets.map(target => (
        <div key={target.index} style={targetRowStyle}>
          <span style={{ ...targetBadgeStyle, ...targetStateStyle(target) }}>
            {target.label}
          </span>
          <strong style={targetPriceStyle}>${fmtMoney(target.price)}</strong>
          <span style={targetMetaStyle}>
            {target.qty ? `${fmtInt(target.qty)} qty` : '-'}
          </span>
          <span style={{ ...targetStatusStyle, color: targetStatusColor(target) }}>
            {targetStatus(target)}
          </span>
        </div>
      ))}
    </div>
  );
}

const formatSignedMoney = (value) => {
  if (value == null || !Number.isFinite(Number(value))) return '-';
  return `${Number(value) >= 0 ? '+' : '-'}$${fmtMoney(Math.abs(Number(value)))}`;
};

const formatPct = (value) => {
  const text = fx(value, 1);
  return text === '-' ? '-' : `${text}%`;
};

const formatSignedPct = (value) => {
  if (value == null || !Number.isFinite(Number(value))) return '-';
  return `${Number(value) >= 0 ? '+' : ''}${Number(value).toFixed(1)}%`;
};

const formatR = (value, signed = false) => {
  if (value == null || !Number.isFinite(Number(value))) return '-';
  return `${signed && Number(value) >= 0 ? '+' : ''}${Number(value).toFixed(2)}R`;
};

const sourceLabel = (source) => {
  if (source === 'ibkr') return 'IBKR';
  if (source === 'yf') return 'LIVE';
  if (source === 'fills') return 'FILLS';
  return 'NO QUOTE';
};

const targetStatus = (target) => {
  if (target.hit) return 'Hit';
  if (target.isNext && target.distToTargetPct != null) return `${formatSignedPct(target.distToTargetPct)} away`;
  if (target.isNext) return 'Next';
  return 'Pending';
};

const targetDistanceLabel = (target) => {
  if (target.distToTargetPct == null || !Number.isFinite(Number(target.distToTargetPct))) {
    return 'No quote';
  }
  return `${formatSignedPct(target.distToTargetPct)} away`;
};

const toneForSigned = (value) => {
  if (value == null || !Number.isFinite(Number(value))) return null;
  if (Number(value) > 0) return 'success';
  if (Number(value) < 0) return 'danger';
  return null;
};

const toneColor = (tone) => {
  if (tone === 'success') return 'var(--success)';
  if (tone === 'danger' || tone === 'breached') return 'var(--danger)';
  if (tone === 'warning') return 'var(--warning)';
  if (tone === 'target') return 'var(--accent-blue)';
  return 'var(--text-main)';
};

const targetStatusColor = (target) => {
  if (target.hit) return 'var(--success)';
  if (target.isNext) return 'var(--accent-blue)';
  return 'var(--text-muted)';
};

const targetStateStyle = (target) => {
  if (target.hit) {
    return {
      background: 'rgba(61, 211, 122, 0.12)',
      borderColor: 'rgba(61, 211, 122, 0.34)',
      color: 'var(--success)',
    };
  }
  if (target.isNext) {
    return {
      background: 'var(--accent-blue-soft)',
      borderColor: 'rgba(91, 138, 255, 0.38)',
      color: '#bfd0ff',
    };
  }
  return {};
};

const alertToneStyle = (level) => {
  if (level === 'critical' || level === 'danger') {
    return {
      background: 'rgba(242, 103, 112, 0.10)',
      borderColor: 'rgba(242, 103, 112, 0.32)',
    };
  }
  if (level === 'warning') {
    return {
      background: 'rgba(240, 190, 60, 0.10)',
      borderColor: 'rgba(240, 190, 60, 0.30)',
    };
  }
  return {
    background: 'rgba(91, 138, 255, 0.10)',
    borderColor: 'rgba(91, 138, 255, 0.30)',
  };
};

const cockpitStyle = {
  background: 'rgba(255, 255, 255, 0.025)',
  border: '1px solid var(--border-color)',
  borderRadius: 'var(--radius-sm)',
  display: 'flex',
  flexDirection: 'column',
  gap: 12,
  marginBottom: 18,
  padding: 14,
};

const cockpitHeaderStyle = {
  alignItems: 'center',
  display: 'flex',
  justifyContent: 'space-between',
  gap: 12,
};

const alertStyle = {
  alignItems: 'center',
  border: '1px solid',
  borderRadius: 'var(--radius-sm)',
  display: 'flex',
  gap: 8,
  justifyContent: 'space-between',
  padding: '8px 10px',
};

const eyebrowStyle = {
  color: 'var(--text-muted)',
  fontSize: 10,
  fontWeight: 700,
  letterSpacing: '0.08em',
  textTransform: 'uppercase',
};

const titleStyle = {
  color: 'var(--text-main)',
  display: 'block',
  fontSize: 15,
  marginTop: 3,
};

const metricGridStyle = {
  display: 'grid',
  gap: 8,
  gridTemplateColumns: 'repeat(4, minmax(0, 1fr))',
};

const metricStyle = {
  borderTop: '1px solid rgba(255,255,255,0.07)',
  minWidth: 0,
  paddingTop: 9,
};

const metricLabelStyle = {
  color: 'var(--text-faint)',
  display: 'block',
  fontSize: 10,
  fontWeight: 700,
  letterSpacing: '0.04em',
  textTransform: 'uppercase',
};

const metricValueStyle = {
  display: 'block',
  fontSize: 14,
  fontWeight: 800,
  marginTop: 4,
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
};

const metricSubStyle = {
  color: 'var(--text-muted)',
  display: 'block',
  fontSize: 10,
  marginTop: 3,
};

const targetListStyle = {
  display: 'grid',
  gap: 6,
};

const targetRowStyle = {
  alignItems: 'center',
  display: 'grid',
  gap: 8,
  gridTemplateColumns: '42px minmax(76px, 1fr) minmax(54px, 0.7fr) minmax(82px, 1fr)',
  minHeight: 30,
};

const targetBadgeStyle = {
  border: '1px solid var(--border-color)',
  borderRadius: 'var(--radius-xs)',
  color: 'var(--text-muted)',
  fontSize: 10,
  fontWeight: 800,
  padding: '3px 0',
  textAlign: 'center',
};

const targetPriceStyle = {
  color: 'var(--text-main)',
  fontSize: 12,
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
};

const targetMetaStyle = {
  color: 'var(--text-faint)',
  fontSize: 10,
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
};

const targetStatusStyle = {
  fontSize: 11,
  fontWeight: 700,
  overflow: 'hidden',
  textAlign: 'right',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
};

const emptyTargetsStyle = {
  borderTop: '1px solid rgba(255,255,255,0.07)',
  color: 'var(--text-muted)',
  fontSize: 12,
  paddingTop: 10,
};
