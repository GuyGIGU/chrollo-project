import { useEffect, useState } from 'react';
import { API_BASE } from '../../api';
import { btnPrimary, labelStyle, textareaStyle } from './styles';

export default function PlanTab({ tradeId }) {
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
