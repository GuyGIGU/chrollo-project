import React from 'react';

export const ScanHistoryModal = ({ open, runs, loading, onClose }) => {
  if (!open) return null;

  return (
    <div
      onClick={onClose}
      style={backdropStyle}
    >
      <div onClick={e => e.stopPropagation()} className="glass-panel" style={historyPanelStyle}>
        <div style={headerStyle}>
          <div style={{ fontWeight: 700 }}>🕒 Scan History</div>
          <button onClick={onClose} style={closeButtonStyle}>✕</button>
        </div>
        {loading ? (
          <div style={mutedTextStyle}>Loading…</div>
        ) : (runs && runs.length) ? (
          <table style={tableStyle}>
            <thead>
              <tr style={{ color: 'var(--text-muted)', borderBottom: '1px solid var(--border-color)' }}>
                <th style={leftCellStyle}>Finished</th>
                <th style={leftCellStyle}>Trigger</th>
                <th style={rightCellStyle}>Setups</th>
                <th style={leftCellStyle}>Status</th>
              </tr>
            </thead>
            <tbody>
              {runs.map(run => (
                <tr key={run.id} style={{ borderBottom: '1px solid rgba(255,255,255,0.03)' }}>
                  <td style={leftCellStyle}>{formatRunTime(run)}</td>
                  <td style={leftCellStyle}>{run.trigger || '—'}</td>
                  <td style={rightCellStyle}>{run.n_setups ?? '—'}</td>
                  <td style={{ ...leftCellStyle, color: statusColor(run.status) }}>
                    {run.status}{run.error ? ` · ${String(run.error).slice(0, 60)}` : ''}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div style={mutedTextStyle}>No scan runs recorded yet.</div>
        )}
      </div>
    </div>
  );
};

export const ArchiveAnalysisModal = ({ open, text, loading, error, onRefresh, onClose }) => {
  if (!open) return null;

  return (
    <div
      onClick={onClose}
      style={backdropStyle}
    >
      <div onClick={e => e.stopPropagation()} className="glass-panel" style={analysisPanelStyle}>
        <div style={headerStyle}>
          <div style={{ fontWeight: 700 }}>📊 Archive Analysis</div>
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
            <button onClick={onRefresh} disabled={loading} style={refreshButtonStyle(loading)}>↻ Refresh</button>
            <button onClick={onClose} style={closeButtonStyle}>✕</button>
          </div>
        </div>
        {loading ? (
          <div style={mutedTextStyle}>Running analysis… (a few seconds)</div>
        ) : error ? (
          <div style={errorTextStyle}>{error}</div>
        ) : (
          <pre style={preStyle}>{text}</pre>
        )}
      </div>
    </div>
  );
};

const formatRunTime = (run) => (run.finished_at || run.started_at || '—').replace('T', ' ').slice(0, 19);

const statusColor = (status) => {
  if (status === 'ok') return 'var(--success)';
  if (status === 'running') return 'var(--accent-blue)';
  return 'var(--danger)';
};

const backdropStyle = {
  position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)', display: 'flex',
  alignItems: 'center', justifyContent: 'center', zIndex: 1000,
};

const historyPanelStyle = { width: 'min(680px, 92vw)', maxHeight: '80vh', overflow: 'auto', padding: '18px' };
const analysisPanelStyle = { width: 'min(900px, 94vw)', maxHeight: '85vh', overflow: 'auto', padding: '18px' };
const headerStyle = { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' };
const mutedTextStyle = { color: 'var(--text-muted)', fontSize: '12px' };
const closeButtonStyle = { background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', fontSize: '16px' };
const tableStyle = { width: '100%', fontSize: '11px', fontFamily: "'JetBrains Mono', monospace" };
const leftCellStyle = { textAlign: 'left', padding: '4px 6px' };
const rightCellStyle = { textAlign: 'right', padding: '4px 6px' };
const errorTextStyle = { color: 'var(--danger)', fontSize: '12px', whiteSpace: 'pre-wrap' };
const preStyle = {
  fontSize: '11px', fontFamily: "'JetBrains Mono', monospace", whiteSpace: 'pre',
  overflowX: 'auto', color: 'var(--text-main)', lineHeight: 1.5, margin: 0,
};
const refreshButtonStyle = (loading) => ({
  background: 'transparent', color: 'var(--text-main)', border: '1px solid var(--border-color)',
  padding: '4px 10px', borderRadius: '6px', cursor: loading ? 'not-allowed' : 'pointer', fontSize: '11px',
});
