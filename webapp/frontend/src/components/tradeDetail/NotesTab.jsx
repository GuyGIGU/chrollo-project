import { useEffect, useState } from 'react';
import { API_BASE } from '../../api';
import { btnPrimary, inputStyle, labelStyle, textareaStyle } from './styles';

export default function NotesTab({ tradeId }) {
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
