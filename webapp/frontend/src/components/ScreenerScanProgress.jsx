function ScreenerScanProgress({ isScanning, scanProgress, scanPhase, scanLogs }) {
  if (!isScanning) return null;

  return (
    <div style={panelStyle}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={phaseStyle(scanProgress)}>
          {scanProgress < 100 && <span style={pulseDotStyle} />}
          {scanProgress >= 100 && 'Done '}
          {scanPhase || 'Initializing pipeline...'}
        </span>
        <span style={percentStyle(scanProgress)}>
          {Math.min(100, Math.round(scanProgress))}%
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
      <div style={fillStyle(scanProgress)}>
        {scanProgress < 100 && <div style={shimmerStyle} />}
      </div>
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
  color: progress >= 100 ? '#3fb950' : 'var(--text-main)',
  display: 'flex',
  alignItems: 'center',
  gap: '8px',
});
const pulseDotStyle = {
  display: 'inline-block',
  width: '8px',
  height: '8px',
  borderRadius: '50%',
  background: 'var(--accent-blue)',
  animation: 'pulse-subtle 1.5s ease-in-out infinite',
};
const percentStyle = (progress) => ({
  fontSize: '13px',
  fontWeight: '700',
  fontFamily: "'JetBrains Mono', monospace",
  color: progress >= 100 ? '#3fb950' : 'var(--accent-blue)',
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
  background: progress >= 100
    ? '#3fb950'
    : 'linear-gradient(90deg, var(--accent-blue), var(--accent-pink, #bb86fc))',
  transition: 'width 0.4s ease-out',
  position: 'relative',
  overflow: 'hidden',
});
const shimmerStyle = {
  position: 'absolute',
  top: 0,
  left: 0,
  right: 0,
  bottom: 0,
  background: 'linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.3) 50%, transparent 100%)',
  animation: 'shimmer 1.8s ease-in-out infinite',
};
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
