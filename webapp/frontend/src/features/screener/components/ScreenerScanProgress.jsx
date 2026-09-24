function ScreenerScanProgress({ isScanning, scanProgress, scanPhase, scanLogs, onStop }) {
  if (!isScanning) return null;

  return (
    <div style={panelStyle}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '10px' }}>
        <span style={phaseStyle(scanProgress)}>
          {scanProgress < 100 && <span className="scan-pulse-dot" style={pulseDotStyle} />}
          {scanProgress >= 100 && 'Done '}
          {scanPhase || 'Initializing pipeline...'}
        </span>
        <span style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          {/* The only in-app way to stop a run: the job outlives its reader now,
              so navigating away no longer ends it and a wedged child would hold
              SCAN_LOCK until the service restarts (council review A3). Sits in
              the row that already exists — no new band. */}
          {onStop && <button type="button" style={stopStyle} onClick={onStop}>Stop</button>}
          <span style={percentStyle(scanProgress)}>
            {Math.min(100, Math.round(scanProgress))}%
          </span>
        </span>
      </div>
      <ProgressBar scanProgress={scanProgress} />
      <div style={logPanelStyle}>
        {scanLogs.map((log, index) => (
          <div key={`${index}-${log}`} style={logLineStyle(index, scanLogs.length)}>
            {log}
          </div>
        ))}
      </div>
    </div>
  );
}

function ProgressBar({ scanProgress }) {
  return (
    <div style={trackStyle}>
      <div style={fillStyle(scanProgress)} />
    </div>
  );
}

const panelStyle = {
  background: 'var(--bg-panel)',
  border: '1px solid var(--border-color)',
  borderRadius: '12px',
  padding: '24px',
  display: 'flex',
  flexDirection: 'column',
  gap: '16px',
};
const phaseStyle = (progress) => ({
  fontSize: '13px',
  fontWeight: '600',
  color: progress >= 100 ? 'var(--success)' : 'var(--text-main)',
  display: 'flex',
  alignItems: 'center',
  gap: '8px',
});
const pulseDotStyle = {
  display: 'inline-block',
  width: '8px',
  height: '8px',
  borderRadius: '50%',
  background: 'var(--myth)',
};
const stopStyle = {
  background: 'transparent',
  border: '1px solid var(--border-strong)',
  borderRadius: 'var(--radius-sm)',
  color: 'var(--text-muted)',
  cursor: 'pointer',
  fontFamily: 'inherit',
  fontSize: '11px',
  fontWeight: 600,
  padding: '2px 9px',
};
const percentStyle = (progress) => ({
  fontSize: '13px',
  fontWeight: '700',
  fontFamily: "'JetBrains Mono', monospace",
  color: progress >= 100 ? 'var(--success)' : 'var(--myth)',
});
const trackStyle = {
  width: '100%',
  height: '8px',
  borderRadius: '4px',
  background: 'rgba(255,255,255,0.06)',
  overflow: 'hidden',
  position: 'relative',
};
const fillStyle = (progress) => ({
  height: '100%',
  width: `${Math.min(100, progress)}%`,
  borderRadius: '4px',
  background: progress >= 100 ? 'var(--success)' : 'var(--myth)',
  transition: 'width 0.4s ease-out',
});
const logPanelStyle = {
  fontFamily: "'JetBrains Mono', monospace",
  fontSize: '10px',
  color: 'var(--text-muted)',
  maxHeight: '52px',
  overflow: 'hidden',
  display: 'flex',
  flexDirection: 'column',
  gap: '2px',
};
const logLineStyle = (index, length) => ({
  opacity: index === length - 1 ? 0.7 : 0.35,
  whiteSpace: 'nowrap',
  overflow: 'hidden',
  textOverflow: 'ellipsis',
});

export default ScreenerScanProgress;
