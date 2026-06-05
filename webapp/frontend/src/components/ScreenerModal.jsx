import React, { useEffect, useMemo, useRef, useState } from 'react';
import { ScoreBreakdownPills } from './ScoreBreakdown';
import { buildPhaseRegions } from './chartPhaseOverlay';
import useScreenerModalChart from '../hooks/useScreenerModalChart';

const formatMoney = (value) =>
  value != null && value !== '' && Number.isFinite(Number(value)) ? `$${Number(value).toFixed(2)}` : '-';

const formatPct = (value) =>
  value != null && value !== '' && Number.isFinite(Number(value)) ? `${Number(value).toFixed(1)}%` : '-';

const tierColor = (tier) => {
  switch (tier) {
    case 'S': return '#ff9f43';
    case 'A': return '#bb86fc';
    case 'B': return '#58a6ff';
    case 'C': return '#3fb950';
    default: return '#8b949e';
  }
};

const distanceToTriggerPct = (data) => {
  const currentPrice = data.candles?.[data.candles.length - 1]?.close;
  if (!data?.trigger || !currentPrice) return null;
  return ((data.trigger - currentPrice) / currentPrice) * 100;
};

const buttonStyle = {
  background: 'rgba(255,255,255,0.03)',
  border: '1px solid var(--border-color)',
  borderRadius: 6,
  color: 'var(--text-main)',
  cursor: 'pointer',
  fontFamily: 'inherit',
  fontSize: 12,
  height: 30,
  padding: '0 11px',
};

function Metric({ label, value, tone }) {
  return (
    <div style={{ borderBottom: '1px solid rgba(255,255,255,0.06)', padding: '10px 0' }}>
      <div style={{ color: 'var(--text-muted)', fontSize: 10, fontWeight: 800, textTransform: 'uppercase' }}>
        {label}
      </div>
      <div style={{ color: tone || 'var(--text-main)', fontSize: 14, fontWeight: 800, marginTop: 4 }}>
        {value}
      </div>
    </div>
  );
}

function PhaseBinPanel({ activeRegion, data, onRegionChange }) {
  const regions = useMemo(() => buildPhaseRegions(data), [data]);
  if (regions.length === 0) return null;

  return (
    <div className="phase-bin-panel">
      <div className="phase-bin-panel-label">Bins</div>
      <div className="phase-bin-list">
        {regions.map(region => (
          <button
            key={region.key}
            type="button"
            className={`phase-bin-control phase-bin-${region.key}${activeRegion === region.key ? ' is-active' : ''}`}
            onBlur={() => onRegionChange(null)}
            onFocus={() => onRegionChange(region.key)}
            onMouseEnter={() => onRegionChange(region.key)}
            onMouseLeave={() => onRegionChange(null)}
            aria-label={`${region.name} - ${region.detail}`}
          >
            <span className="phase-bin-token">{region.label}</span>
            <span className="phase-bin-copy">
              <span className="phase-bin-name">{region.name}</span>
              <span className="phase-bin-detail">{region.detail}</span>
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}

function SetupInspector({ activeRegion, data, onRegionChange }) {
  const currentPrice = data.candles?.[data.candles.length - 1]?.close;
  const triggerDistance = distanceToTriggerPct(data);

  return (
    <aside style={{
      background: '#1d202b',
      borderLeft: '1px solid var(--border-color)',
      display: 'flex',
      flexDirection: 'column',
      gap: 8,
      overflowY: 'auto',
      padding: '14px 16px',
      width: 260,
    }} className="screener-modal-inspector">
      <div>
        <div style={{ color: 'var(--text-muted)', fontSize: 10, fontWeight: 800, textTransform: 'uppercase' }}>
          Setup
        </div>
        <div style={{ color: 'var(--text-main)', fontSize: 15, fontWeight: 800, marginTop: 4 }}>
          {data.setup || '-'}
        </div>
      </div>
      <ScoreBreakdownPills subScores={data.sub_scores} includeFusion style={{ justifyContent: 'flex-start' }} />
      <PhaseBinPanel activeRegion={activeRegion} data={data} onRegionChange={onRegionChange} />
      <Metric label="Score" value={data.score ?? '-'} tone={tierColor(data.tier)} />
      <Metric label="Current Price" value={formatMoney(currentPrice)} />
      <Metric label="Trigger" value={formatMoney(data.trigger)} tone="#e3b341" />
      <Metric
        label="To Trigger"
        value={formatPct(triggerDistance)}
        tone={triggerDistance != null && triggerDistance <= 0.5 ? 'var(--warning)' : 'var(--success)'}
      />
    </aside>
  );
}

function ModalToolbar({ data, onClose, onNext, onPrev, ticker }) {
  return (
    <header style={{
      alignItems: 'center',
      background: '#202330',
      borderBottom: '1px solid var(--border-color)',
      display: 'flex',
      gap: 16,
      justifyContent: 'space-between',
      minHeight: 52,
      padding: '8px 14px',
    }} className="screener-modal-toolbar">
      <div style={{ alignItems: 'center', display: 'flex', gap: 12, minWidth: 0 }}>
        <strong style={{ color: tierColor(data.tier), fontFamily: "'JetBrains Mono', monospace", fontSize: 22 }}>
          {ticker}
        </strong>
        <span style={{
          border: `1px solid ${tierColor(data.tier)}55`,
          borderRadius: 6,
          color: tierColor(data.tier),
          fontSize: 11,
          fontWeight: 800,
          padding: '2px 7px',
        }}>
          {data.tier} TIER
        </span>
        <span style={{ color: 'var(--text-muted)', fontSize: 12, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {data.setup}
        </span>
      </div>
      <div style={{ alignItems: 'center', display: 'flex', gap: 8 }}>
        <button onClick={onPrev} style={buttonStyle}>Prev</button>
        <button onClick={onNext} style={buttonStyle}>Next</button>
        <button
          onClick={onClose}
          style={{ ...buttonStyle, color: 'var(--text-muted)', fontSize: 18, padding: '0 10px' }}
          title="Close"
        >
          x
        </button>
      </div>
    </header>
  );
}

const ScreenerModal = ({ ticker, data, onClose, onPrev, onNext, footer = null }) => {
  const chartContainerRef = useRef(null);
  const [activeRegion, setActiveRegion] = useState(null);

  useEffect(() => {
    setActiveRegion(null);
  }, [ticker]);

  useScreenerModalChart(chartContainerRef, ticker, data, activeRegion);

  return (
    <div
      style={{
        background: 'rgba(8, 10, 15, 0.92)',
        bottom: 0,
        display: 'flex',
        left: 0,
        padding: 28,
        position: 'fixed',
        right: 0,
        top: 0,
        zIndex: 5000,
      }}
      onClick={onClose}
    >
      <section
        className="screener-modal-shell"
        style={{
          background: 'var(--bg-main)',
          border: '1px solid var(--border-color)',
          borderRadius: 8,
          boxShadow: '0 22px 55px rgba(0,0,0,0.45)',
          display: 'flex',
          flex: 1,
          flexDirection: 'column',
          margin: '0 auto',
          maxWidth: 1500,
          minHeight: 0,
          overflow: 'hidden',
        }}
        onClick={event => event.stopPropagation()}
      >
        <ModalToolbar data={data} onClose={onClose} onNext={onNext} onPrev={onPrev} ticker={ticker} />
        <div className="screener-modal-body" style={{ display: 'flex', flex: 1, minHeight: 0 }}>
          <div ref={chartContainerRef} className="screener-modal-chart" style={{ flex: 1, minHeight: 0, position: 'relative' }} />
          <SetupInspector activeRegion={activeRegion} data={data} onRegionChange={setActiveRegion} />
        </div>
        {footer}
      </section>
    </div>
  );
};

export default ScreenerModal;
