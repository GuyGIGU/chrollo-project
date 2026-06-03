import React, { useCallback, useEffect, useRef, useState } from 'react';
import AttachmentUploader from './AttachmentUploader';
import { API_BASE } from '../api';

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

const labelStyle = {
  fontSize: 10,
  color: 'var(--text-muted)',
  textTransform: 'uppercase',
  letterSpacing: '1px',
  fontWeight: 600,
  marginBottom: 4,
  display: 'block',
};

const textareaStyle = {
  width: '100%',
  minHeight: 80,
  padding: 10,
  background: 'var(--bg-main)',
  border: '1px solid var(--border-color)',
  borderRadius: 'var(--radius-md, 6px)',
  color: 'var(--text-main, #e0e0e6)',
  fontSize: 13,
  fontFamily: 'inherit',
  resize: 'vertical',
  boxSizing: 'border-box',
};

const inputStyle = {
  ...textareaStyle,
  minHeight: 'unset',
  padding: '8px 10px',
};

const btnPrimary = {
  padding: '8px 16px',
  fontSize: 11,
  fontWeight: 600,
  color: '#fff',
  background: 'var(--accent-blue)',
  border: 'none',
  borderRadius: 'var(--radius-pill, 999px)',
  cursor: 'pointer',
  textTransform: 'uppercase',
  letterSpacing: '1px',
};

function PlanTab({ tradeId }) {
  const [plan, setPlan] = useState({ thesis: '', entry_plan: '', exit_plan: '', risk_plan: '' });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [savedAt, setSavedAt] = useState(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetch(`${API_BASE}/trades/${tradeId}/plan`)
      .then(r => r.ok ? r.json() : null)
      .then(d => {
        if (cancelled) return;
        if (d) {
          setPlan({
            thesis: d.thesis || '',
            entry_plan: d.entry_plan || '',
            exit_plan: d.exit_plan || '',
            risk_plan: d.risk_plan || '',
          });
        }
        setLoading(false);
      })
      .catch(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [tradeId]);

  const save = async () => {
    setSaving(true);
    try {
      const res = await fetch(`${API_BASE}/trades/${tradeId}/plan`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(plan),
      });
      if (res.ok) setSavedAt(new Date());
    } catch { /* no-op */ }
    setSaving(false);
  };

  if (loading) return <div style={{ color: 'var(--text-muted)', fontSize: 12 }}>Loading…</div>;

  const field = (key, placeholder) => (
    <textarea
      value={plan[key]}
      onChange={(e) => setPlan({ ...plan, [key]: e.target.value })}
      placeholder={placeholder}
      style={textareaStyle}
    />
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <div>
        <label style={labelStyle}>Thesis</label>
        {field('thesis', 'Why this setup? Market context, catalyst, structure…')}
      </div>
      <div>
        <label style={labelStyle}>Entry Plan</label>
        {field('entry_plan', 'Trigger, confirmation, size, timing')}
      </div>
      <div>
        <label style={labelStyle}>Exit Plan</label>
        {field('exit_plan', 'Targets, trailing stop, invalidation signal')}
      </div>
      <div>
        <label style={labelStyle}>Risk Plan</label>
        {field('risk_plan', 'Max loss, position size rationale, scale-in rules')}
      </div>
      <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
        <button type="button" style={btnPrimary} onClick={save} disabled={saving}>
          {saving ? 'Saving…' : 'Save Plan'}
        </button>
        {savedAt && (
          <span style={{ color: 'var(--success)', fontSize: 11 }}>
            Saved at {savedAt.toLocaleTimeString()}
          </span>
        )}
      </div>
    </div>
  );
}

function NotesTab({ tradeId }) {
  const [note, setNote] = useState({ body: '', mood: '' });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [savedAt, setSavedAt] = useState(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetch(`${API_BASE}/trades/${tradeId}/notes`)
      .then(r => r.ok ? r.json() : null)
      .then(d => {
        if (cancelled) return;
        if (d) setNote({ body: d.body || '', mood: d.mood || '' });
        setLoading(false);
      })
      .catch(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [tradeId]);

  const save = async () => {
    setSaving(true);
    try {
      const res = await fetch(`${API_BASE}/trades/${tradeId}/notes`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(note),
      });
      if (res.ok) setSavedAt(new Date());
    } catch { /* no-op */ }
    setSaving(false);
  };

  if (loading) return <div style={{ color: 'var(--text-muted)', fontSize: 12 }}>Loading…</div>;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <div>
        <label style={labelStyle}>Mood / State</label>
        <input
          type="text"
          value={note.mood}
          onChange={(e) => setNote({ ...note, mood: e.target.value })}
          placeholder="focused · tilted · patient · fomo · …"
          style={inputStyle}
        />
      </div>
      <div>
        <label style={labelStyle}>Notes</label>
        <textarea
          value={note.body}
          onChange={(e) => setNote({ ...note, body: e.target.value })}
          placeholder="What happened? What went right? What went wrong? What would you do differently?"
          style={{ ...textareaStyle, minHeight: 180 }}
        />
      </div>
      <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
        <button type="button" style={btnPrimary} onClick={save} disabled={saving}>
          {saving ? 'Saving…' : 'Save Notes'}
        </button>
        {savedAt && (
          <span style={{ color: 'var(--success)', fontSize: 11 }}>
            Saved at {savedAt.toLocaleTimeString()}
          </span>
        )}
      </div>
    </div>
  );
}

function ExecutionsTab({ tradeId }) {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetch(`${API_BASE}/trades/${tradeId}/executions`)
      .then(r => r.ok ? r.json() : [])
      .then(d => { if (!cancelled) { setRows(Array.isArray(d) ? d : []); setLoading(false); } })
      .catch(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [tradeId]);

  if (loading) return <div style={{ color: 'var(--text-muted)', fontSize: 12 }}>Loading…</div>;
  if (rows.length === 0) {
    return (
      <div style={{ color: 'var(--text-muted)', fontSize: 12 }}>
        No linked IBKR executions. Executions appear here once fills from TWS are auto-imported.
      </div>
    );
  }

  const th = { padding: '8px 10px', fontSize: 10, color: 'var(--text-muted)', textAlign: 'left', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px' };
  const td = { padding: '8px 10px', fontSize: 12, color: 'var(--text-main, #e0e0e6)' };

  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr style={{ borderBottom: '1px solid var(--border-color)' }}>
            <th style={th}>Time</th>
            <th style={th}>Side</th>
            <th style={th}>Qty</th>
            <th style={th}>Price</th>
            <th style={th}>Comm</th>
            <th style={th}>Realized</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((e) => {
            const realized = e.realized_pnl;
            const color = realized == null ? 'var(--text-muted)' : (realized > 0 ? 'var(--success)' : realized < 0 ? 'var(--danger)' : 'var(--text-muted)');
            const sideColor = e.side === 'BUY' ? 'var(--success)' : 'var(--danger)';
            return (
              <tr key={e.id} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                <td style={{ ...td, color: 'var(--text-muted)' }}>{e.time ? new Date(e.time).toLocaleString() : '—'}</td>
                <td style={{ ...td, color: sideColor, fontWeight: 600 }}>{e.side}</td>
                <td style={td}>{e.quantity}</td>
                <td style={td}>${Number(e.price).toFixed(2)}</td>
                <td style={{ ...td, color: 'var(--text-muted)' }}>${Number(e.commission).toFixed(2)}</td>
                <td style={{ ...td, color, fontWeight: 600 }}>
                  {realized == null ? '—' : `$${Number(realized).toFixed(2)}`}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

const convBtnBase = {
  flex: 1,
  padding: '8px 0',
  fontSize: 13,
  fontWeight: 700,
  borderRadius: 'var(--radius-md, 6px)',
  border: '1px solid var(--border-color)',
  background: 'var(--bg-main)',
  color: 'var(--text-muted)',
  cursor: 'pointer',
  fontFamily: 'inherit',
};

const convBtnActive = {
  background: 'var(--accent-blue)',
  borderColor: 'var(--accent-blue)',
  color: '#fff',
};

// Minimal per-trade intent capture: conviction (1-3) + one-line exit reason.
// Saved straight onto the TradeLog via PUT /trades/{id} (both fields optional).
function IntentTab({ trade }) {
  const [conviction, setConviction] = useState(trade.conviction || 0);
  const [exitReason, setExitReason] = useState(trade.exit_reason || '');
  const [saving, setSaving] = useState(false);
  const [savedAt, setSavedAt] = useState(null);

  const save = async () => {
    setSaving(true);
    try {
      const res = await fetch(`${API_BASE}/trades/${trade.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          conviction: conviction || null,
          exit_reason: exitReason.trim() || null,
        }),
      });
      if (res.ok) setSavedAt(new Date());
    } catch { /* no-op */ }
    setSaving(false);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <div>
        <label style={labelStyle}>Conviction</label>
        <div style={{ display: 'flex', gap: 8 }}>
          {[1, 2, 3].map(n => (
            <button
              key={n}
              type="button"
              onClick={() => setConviction(conviction === n ? 0 : n)}
              style={{ ...convBtnBase, ...(conviction === n ? convBtnActive : {}) }}
            >
              {n}
            </button>
          ))}
        </div>
        <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 4 }}>
          1 = low · 2 = medium · 3 = high (click again to clear)
        </div>
      </div>
      <div>
        <label style={labelStyle}>Exit Reason</label>
        <input
          type="text"
          value={exitReason}
          onChange={(e) => setExitReason(e.target.value)}
          placeholder="hit target · stopped out · time stop · thesis broke · …"
          style={inputStyle}
        />
      </div>
      <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
        <button type="button" style={btnPrimary} onClick={save} disabled={saving}>
          {saving ? 'Saving…' : 'Save'}
        </button>
        {savedAt && (
          <span style={{ color: 'var(--success)', fontSize: 11 }}>
            Saved at {savedAt.toLocaleTimeString()}
          </span>
        )}
      </div>
    </div>
  );
}

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
