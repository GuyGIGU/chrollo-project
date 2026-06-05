import { useState } from 'react';
import { API_BASE } from '../../api';
import { btnPrimary, convBtnActive, convBtnBase, inputStyle, labelStyle } from './styles';

// Minimal per-trade intent capture: conviction (1-3) + one-line exit reason.
// Saved straight onto the TradeLog via PUT /trades/{id} (both fields optional).
export default function IntentTab({ trade }) {
  const [conviction, setConviction] = useState(trade.conviction || 0);
  const [exitReason, setExitReason] = useState(trade.exit_reason || '');
  const [saving, setSaving] = useState(false);
  const [savedAt, setSavedAt] = useState(null);
  const [error, setError] = useState(false);

  const save = async () => {
    setSaving(true);
    setError(false);
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
      else setError(true);
    } catch { setError(true); }
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
        {savedAt && !error && (
          <span style={{ color: 'var(--success)', fontSize: 11 }}>
            Saved at {savedAt.toLocaleTimeString()}
          </span>
        )}
        {error && (
          <span style={{ color: 'var(--danger)', fontSize: 11 }}>Save failed — try again</span>
        )}
      </div>
    </div>
  );
}
