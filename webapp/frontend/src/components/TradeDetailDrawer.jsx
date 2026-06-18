import { useCallback, useEffect, useRef, useState } from 'react';
import AttachmentUploader from './AttachmentUploader';
import ExecutionsTab from './tradeDetail/ExecutionsTab';
import IntentTab from './tradeDetail/IntentTab';
import NotesTab from './tradeDetail/NotesTab';
import PlanTab from './tradeDetail/PlanTab';
import RiskCockpit from './tradeDetail/RiskCockpit';

const tabStyle = (active) => ({
  padding: '8px 14px',
  fontSize: 11,
  fontWeight: 500,
  cursor: 'pointer',
  color: active ? '#fff' : 'var(--text-muted)',
  borderBottom: active ? '2px solid var(--accent-blue)' : '2px solid transparent',
  textTransform: 'uppercase',
  letterSpacing: '1px',
  userSelect: 'none',
});

export default function TradeDetailDrawer({ trade, onClose }) {
  const [tab, setTab] = useState('plan');
  const overlayRef = useRef(null);

  const handleKey = useCallback((e) => {
    if (e.key === 'Escape') onClose?.();
  }, [onClose]);

  useEffect(() => {
    document.addEventListener('keydown', handleKey);
    return () => document.removeEventListener('keydown', handleKey);
  }, [handleKey]);

  if (!trade) return null;

  return (
    <div
      ref={overlayRef}
      onClick={(e) => { if (e.target === overlayRef.current) onClose?.(); }}
      style={{
        position: 'fixed', inset: 0, zIndex: 1000,
        background: 'rgba(0,0,0,0.5)',
        display: 'flex', justifyContent: 'flex-end',
      }}
    >
      <aside
        style={{
          width: 'min(560px, 100%)',
          height: '100%',
          background: 'var(--bg-panel)',
          borderLeft: '1px solid var(--border-color)',
          boxShadow: '-8px 0 24px rgba(0,0,0,0.3)',
          display: 'flex', flexDirection: 'column',
        }}
      >
        <header style={{ padding: '16px 20px', borderBottom: '1px solid var(--border-color)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <div style={{ fontSize: 10, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '1px' }}>
              Trade #{trade.id} · {trade.opening_date}
            </div>
            <div style={{ fontSize: 18, color: 'var(--accent-blue)', fontWeight: 700, marginTop: 2 }}>
              {trade.ticker} <span style={{ color: 'var(--text-muted)', fontSize: 12, fontWeight: 500 }}>· {trade.direction}</span>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            style={{
              background: 'transparent', border: 'none', color: 'var(--text-muted)',
              fontSize: 24, cursor: 'pointer', lineHeight: 1, padding: 4,
            }}
          >×</button>
        </header>

        <nav style={{ display: 'flex', padding: '0 20px', borderBottom: '1px solid var(--border-color)' }}>
          <div style={tabStyle(tab === 'plan')} onClick={() => setTab('plan')}>Plan</div>
          <div style={tabStyle(tab === 'intent')} onClick={() => setTab('intent')}>Intent</div>
          <div style={tabStyle(tab === 'notes')} onClick={() => setTab('notes')}>Notes</div>
          <div style={tabStyle(tab === 'attachments')} onClick={() => setTab('attachments')}>Charts</div>
          <div style={tabStyle(tab === 'executions')} onClick={() => setTab('executions')}>Executions</div>
        </nav>

        <div style={{ flex: 1, overflowY: 'auto', padding: '20px' }}>
          <RiskCockpit trade={trade} />
          {tab === 'plan' && <PlanTab tradeId={trade.id} />}
          {tab === 'intent' && <IntentTab trade={trade} />}
          {tab === 'notes' && <NotesTab tradeId={trade.id} />}
          {tab === 'attachments' && <AttachmentUploader tradeId={trade.id} />}
          {tab === 'executions' && <ExecutionsTab tradeId={trade.id} />}
        </div>
      </aside>
    </div>
  );
}
