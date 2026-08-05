import React, { useEffect, useRef, useState } from 'react';
import ScreenerStockLens from './ScreenerStockLens';
import TimeframeMainChart from './TimeframeMainChart';
import useScreenerModalChart from '../hooks/useScreenerModalChart';
import { tierColor, signColor } from '../theme';
import { fx, fmtSignedPctFrac } from '../utils/format';
import { dailyChangeFrac } from '../utils/screenerCardData';

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

const INTERVAL_TABS = [
  { key: 'D', label: 'D', name: 'Daily' },
  { key: 'W', label: 'W', name: 'Weekly' },
  { key: 'M', label: 'M', name: 'Monthly' },
];

// TradingView-style D/W/M timeframe switcher. Weekly/Monthly are disabled when
// the row predates the higher-timeframe read (no resampled candles in payload).
function IntervalTabs({ interval, onIntervalChange, hasWeekly, hasMonthly }) {
  const enabled = { D: true, W: hasWeekly, M: hasMonthly };
  return (
    <div
      role="tablist"
      aria-label="Chart timeframe"
      style={{
        alignItems: 'stretch',
        border: '1px solid var(--border-color)',
        borderRadius: 6,
        display: 'flex',
        height: 28,
        overflow: 'hidden',
      }}
    >
      {INTERVAL_TABS.map((tab, index) => {
        const active = interval === tab.key;
        const ok = enabled[tab.key];
        return (
          <button
            key={tab.key}
            type="button"
            role="tab"
            aria-selected={active}
            disabled={!ok}
            onClick={() => ok && onIntervalChange(tab.key)}
            title={ok ? `${tab.name} chart` : `${tab.name} — needs more history`}
            style={{
              background: active ? 'var(--myth-soft)' : 'transparent',
              border: 'none',
              borderLeft: index === 0 ? 'none' : '1px solid var(--border-color)',
              color: !ok ? 'var(--text-faint)' : active ? 'var(--myth)' : 'var(--text-muted)',
              cursor: ok ? 'pointer' : 'default',
              fontFamily: 'inherit',
              fontSize: 12,
              fontWeight: 700,
              minWidth: 30,
              padding: '0 10px',
            }}
          >
            {tab.label}
          </button>
        );
      })}
    </div>
  );
}

function ModalToolbar({ data, onClose, onNext, onPrev, ticker, interval, onIntervalChange, hasWeekly, hasMonthly }) {
  const changePct = dailyChangeFrac(data?.candles);
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
        <IntervalTabs
          hasMonthly={hasMonthly}
          hasWeekly={hasWeekly}
          interval={interval}
          onIntervalChange={onIntervalChange}
        />
        <span style={{ color: 'var(--text-main)', fontFamily: "'JetBrains Mono', monospace", fontSize: 16, fontWeight: 700 }}>
          ${fx(data.price, 2)}
        </span>
        {changePct != null && (
          <span style={{ color: signColor(changePct) || 'var(--text-muted)', fontFamily: "'JetBrains Mono', monospace", fontSize: 13, fontWeight: 700 }}>
            {fmtSignedPctFrac(changePct, 1)}
          </span>
        )}
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

const ScreenerModal = ({ ticker, data, earnings, scanDate = null, onClose, onPrev, onNext, footer = null }) => {
  const chartContainerRef = useRef(null);
  const [activeRegion, setActiveRegion] = useState(null);
  const [interval, selectInterval] = useState('D');

  const hasWeekly = data?.weekly_candles?.length > 0;
  const hasMonthly = data?.monthly_candles?.length > 0;

  // Reset overlays and snap back to the daily chart on every ticker change.
  useEffect(() => {
    setActiveRegion(null);
    selectInterval('D');
  }, [ticker]);

  useEffect(() => {
    if (interval !== 'D') setActiveRegion(null);
  }, [interval]);

  // Escape closes the lens from every mount (not all parents wire it).
  useEffect(() => {
    const onKey = (event) => { if (event.key === 'Escape') onClose?.(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  useScreenerModalChart(chartContainerRef, ticker, data, activeRegion, interval);

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
        role="dialog"
        aria-modal="true"
        aria-label={`${ticker} chart lens`}
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
        <ModalToolbar
          data={data}
          hasMonthly={hasMonthly}
          hasWeekly={hasWeekly}
          interval={interval}
          onClose={onClose}
          onIntervalChange={selectInterval}
          onNext={onNext}
          onPrev={onPrev}
          ticker={ticker}
        />
        <div className="screener-modal-body" style={{ display: 'flex', flex: 1, flexDirection: 'column', minHeight: 0 }}>
          <div className="screener-modal-chart-shell" style={{ flex: '1 1 auto', minHeight: 0, position: 'relative' }}>
            {interval === 'D' ? (
              <div ref={chartContainerRef} className="screener-modal-chart" style={{ height: '100%', minHeight: 0, position: 'relative' }} />
            ) : (
              <TimeframeMainChart
                key={interval}
                box={interval === 'W' ? data.weekly_box : data.monthly_box}
                candles={interval === 'W' ? data.weekly_candles : data.monthly_candles}
                label={interval === 'W' ? 'WEEKLY' : 'MONTHLY'}
                volumes={interval === 'W' ? data.weekly_volumes : data.monthly_volumes}
              />
            )}
          </div>
          <ScreenerStockLens
            activeRegion={activeRegion}
            data={data}
            earnings={earnings}
            interval={interval}
            onRegionChange={setActiveRegion}
            scanDate={scanDate}
            ticker={ticker}
          />
        </div>
        {footer}
      </section>
    </div>
  );
};

export default ScreenerModal;
