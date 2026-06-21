import React, { useEffect, useRef, useState } from 'react';
import ScreenerStockLens from './ScreenerStockLens';
import TimeframeCharts from './TimeframeCharts';
import useScreenerModalChart from '../hooks/useScreenerModalChart';

const tierColor = (tier) => {
  switch (tier) {
    case 'S': return '#ff9f43';
    case 'A': return '#bb86fc';
    case 'B': return '#58a6ff';
    case 'C': return '#3fb950';
    default: return '#8b949e';
  }
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
        <div className="screener-modal-body" style={{ display: 'flex', flex: 1, flexDirection: 'column', minHeight: 0 }}>
          <div className="screener-modal-chart-shell" style={{ flex: '1 1 auto', minHeight: 0, position: 'relative' }}>
            <div ref={chartContainerRef} className="screener-modal-chart" style={{ height: '100%', minHeight: 0, position: 'relative' }} />
          </div>
          <TimeframeCharts data={data} />
          <ScreenerStockLens activeRegion={activeRegion} data={data} onRegionChange={setActiveRegion} />
        </div>
        {footer}
      </section>
    </div>
  );
};

export default ScreenerModal;
