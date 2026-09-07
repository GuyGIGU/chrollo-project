import Modal from './ui/Modal';

export const ArchiveAnalysisModal = ({ open, text, loading, error, onRefresh, onClose }) => {
  if (!open) return null;

  return (
    <Modal onClose={onClose} overlayStyle={backdropStyle} contentClassName="glass-panel" contentStyle={analysisPanelStyle} contentProps={{ 'aria-label': 'Archive Analysis' }}>
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
    </Modal>
  );
};

const backdropStyle = {
  position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)', display: 'flex',
  alignItems: 'center', justifyContent: 'center', zIndex: 1000,
};

const analysisPanelStyle = { width: 'min(900px, 94vw)', maxHeight: '85vh', overflow: 'auto', padding: '18px' };
const headerStyle = { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' };
const mutedTextStyle = { color: 'var(--text-muted)', fontSize: '12px' };
const closeButtonStyle = { background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', fontSize: '16px' };
const errorTextStyle = { color: 'var(--danger)', fontSize: '12px', whiteSpace: 'pre-wrap' };
const preStyle = {
  fontSize: '11px', fontFamily: "'JetBrains Mono', monospace", whiteSpace: 'pre',
  overflowX: 'auto', color: 'var(--text-main)', lineHeight: 1.5, margin: 0,
};
const refreshButtonStyle = (loading) => ({
  background: 'transparent', color: 'var(--text-main)', border: '1px solid var(--border-color)',
  padding: '4px 10px', borderRadius: '6px', cursor: loading ? 'not-allowed' : 'pointer', fontSize: '11px',
});
