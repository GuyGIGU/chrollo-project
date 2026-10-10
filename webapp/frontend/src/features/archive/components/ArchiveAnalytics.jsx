import ArchiveCalibrationPanels from './ArchiveCalibrationPanels';
import ArchiveEquityCurve from './ArchiveEquityCurve';
import ArchiveReweightingStrip from './ArchiveReweightingStrip';
import ArchiveTierCards from './ArchiveTierCards';

// The four analytics blocks, folded below the review table. A native <details>:
// the body is not rendered while closed, so its two slow endpoints are not called
// (useArchiveAnalytics). The summary click is never preventDefault-ed, or the
// open attribute and the React state drift apart; a fold mounted open fires one
// 'toggle' after mount, which only re-saves the same '1'.
export default function ArchiveAnalytics({ analytics, onToggle, open }) {
  return (
    <details open={open} onToggle={(event) => onToggle(event.currentTarget.open)}>
      <summary className="focus-ring" style={summaryStyle}>
        <span aria-hidden="true" style={chevronStyle}>{open ? '▾' : '▸'}</span>
        <span style={titleStyle}>Analytics</span>
        <span style={hintStyle}>Tier results, what predicts returns, suggested weights, equity curve</span>
      </summary>
      {open && <AnalyticsBody analytics={analytics} />}
    </details>
  );
}

// The stale panels stay up during a refresh; the message shows only before the
// first answer, or when neither endpoint answered.
function AnalyticsBody({ analytics: { calibration, equityCurve, status } }) {
  if (calibration == null && equityCurve == null) {
    return (
      <div style={messageStyle}>
        {status === 'done' ? 'Analytics could not be loaded.' : 'Loading analytics...'}
      </div>
    );
  }
  return (
    <div style={bodyStyle}>
      <ArchiveTierCards performance={calibration?.tier_performance} />
      <ArchiveCalibrationPanels calibration={calibration} />
      <ArchiveReweightingStrip data={calibration?.suggested_weights} basis={calibration?.weights_basis} />
      {equityCurve && <ArchiveEquityCurve data={equityCurve} />}
    </div>
  );
}

// display:flex also removes Chrome's disclosure marker from the summary.
const summaryStyle = {
  alignItems: 'baseline',
  background: 'var(--bg-panel)',
  border: '1px solid var(--border-color)',
  borderRadius: '8px',
  cursor: 'pointer',
  display: 'flex',
  gap: '10px',
  listStyle: 'none',
  padding: '10px 16px',
  userSelect: 'none',
};
const chevronStyle = { color: 'var(--text-muted)', fontSize: '12px', width: '12px' };
const titleStyle = { color: 'var(--text-main)', fontSize: '13px', fontWeight: 600 };
const hintStyle = { color: 'var(--text-muted)', fontSize: '11px' };
const bodyStyle = { display: 'flex', flexDirection: 'column', gap: '20px', marginTop: '20px' };
const messageStyle = { color: 'var(--text-muted)', fontSize: '12px', padding: '16px', textAlign: 'center' };
