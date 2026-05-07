import React, { useState } from 'react';
import TagPicker from './TagPicker';
import { API_BASE } from '../api';

const EditTradeModal = ({ trade, onClose, onSave }) => {
  const [tags, setTags] = useState(Array.isArray(trade.tags) ? trade.tags : []);

  const initActions = () => {
    const first = {
      id: 1,
      type: trade.direction === 'LONG' ? 'BUY' : 'SELL',
      date: trade.opening_date || '',
      quantity: trade.quantity || '',
      price: trade.entry_price || '',
      fee: trade.commissions || 0,
    };
    if (trade.actions_json) {
      try {
        const extra = JSON.parse(trade.actions_json);
        return [first, ...extra];
      } catch {
        // actions_json was malformed — fall through to the default leg-only list
      }
    }
    return [first];
  };

  const [actions, setActions] = useState(initActions);

  const [formData, setFormData] = useState({
    direction: trade.direction || 'LONG',
    ticker: trade.ticker || '',
    stop_loss: trade.stop_loss || '',
    target_r: trade.target_r || 3.0,
    position_size: trade.position_size || '',
  });

  const [activeTab, setActiveTab] = useState('General');
  const [busy, setBusy] = useState(false);

  const handleChange = (e) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  const handleToggleSide = () => {
    setFormData(prev => ({
      ...prev,
      direction: prev.direction === 'LONG' ? 'SHORT' : 'LONG'
    }));
  };

  const addAction = () => {
    setActions(prev => [...prev, {
      id: Date.now(),
      type: 'BUY',
      date: '',
      quantity: '',
      price: '',
      fee: 0,
    }]);
  };

  const removeAction = (id) => {
    setActions(prev => prev.filter(a => a.id !== id));
  };

  const updateAction = (id, field, value) => {
    setActions(prev => prev.map(a => a.id === id ? { ...a, [field]: value } : a));
  };

  const toggleActionType = (id) => {
    setActions(prev => prev.map(a => a.id === id ? { ...a, type: a.type === 'BUY' ? 'SELL' : 'BUY' } : a));
  };

  const computePnl = () => {
    const closingType = formData.direction === 'LONG' ? 'SELL' : 'BUY';
    const hasClosing = actions.some(a => a.type === closingType && parseFloat(a.quantity) > 0);
    if (!hasClosing) return null;

    let cashFlow = 0;
    let totalFees = 0;
    for (const a of actions) {
      const qty = parseFloat(a.quantity) || 0;
      const price = parseFloat(a.price) || 0;
      const fee = parseFloat(a.fee) || 0;
      if (a.type === 'SELL') cashFlow += qty * price;
      else if (a.type === 'BUY') cashFlow -= qty * price;
      totalFees += fee;
    }
    return cashFlow - totalFees;
  };

  const deriveClosing = () => {
    const closingType = formData.direction === 'LONG' ? 'SELL' : 'BUY';
    for (let i = actions.length - 1; i >= 0; i--) {
      const a = actions[i];
      if (a.type === closingType && parseFloat(a.quantity) > 0) {
        return {
          exit_price: parseFloat(a.price) || null,
          closing_date: a.date || null,
        };
      }
    }
    return { exit_price: null, closing_date: null };
  };

  const handleSave = async () => {
    if (busy) return;
    setBusy(true);
    const firstAction = actions[0] || {};
    const additionalActions = actions.slice(1);
    const { exit_price, closing_date } = deriveClosing();

    try {
      const payload = {
        ...formData,
        opening_date: firstAction.date || '',
        entry_price: parseFloat(firstAction.price) || 0,
        quantity: parseInt(firstAction.quantity) || 0,
        commissions: parseFloat(firstAction.fee) || 0,
        stop_loss: parseFloat(formData.stop_loss) || 0,
        target_r: parseFloat(formData.target_r) || 3.0,
        exit_price,
        pnl: computePnl(),
        closing_date,
        actions_json: additionalActions.length > 0 ? JSON.stringify(additionalActions) : null,
      };

      const res = await fetch(`${API_BASE}/trades/${trade.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      if (res.ok) {
        await fetch(`${API_BASE}/trades/${trade.id}/tags`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ tag_ids: tags.map(t => t.id) }),
        }).catch(() => {});
        onSave();
      } else {
        const err = await res.json();
        alert('Failed to update trade: ' + JSON.stringify(err));
      }
    } catch (err) {
      console.error(err);
      alert('Error connecting to backend.');
    } finally {
      setBusy(false);
    }
  };

  const handleDelete = async () => {
    if (busy) return;
    if (!window.confirm("Are you sure you want to delete this trade?")) return;
    setBusy(true);
    try {
      const res = await fetch(`${API_BASE}/trades/${trade.id}`, {
        method: 'DELETE'
      });
      if (res.ok) {
        onSave();
      } else {
        alert('Failed to delete trade.');
      }
    } catch (err) {
      console.error(err);
      alert('Error connecting to backend.');
    } finally {
      setBusy(false);
    }
  };

  const inputStyle = {
    background: '#2b2b36',
    border: 'none',
    borderRadius: '4px',
    padding: '8px 12px',
    color: '#e0e0e6',
    fontFamily: 'inherit',
    fontSize: '13px',
    width: '100%',
    outline: 'none',
    boxShadow: 'inset 0 1px 3px rgba(0,0,0,0.2)'
  };

  const labelStyle = {
    fontSize: '11px',
    color: '#8b8b9c',
    marginBottom: '6px',
    display: 'block'
  };

  return (
    <div className="modal-overlay" onClick={onClose} style={{ zIndex: 10000 }}>
      <div className="modal-content" onClick={e => e.stopPropagation()} style={{
        background: '#242430',
        padding: 0,
        borderRadius: '12px',
        maxWidth: '800px',
        width: '100%',
        boxShadow: '0 25px 50px rgba(0,0,0,0.5)',
        border: '1px solid #3f3f52'
      }}>

        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '16px 20px', borderBottom: '1px solid #3f3f52', background: '#2b2b36', borderTopLeftRadius: '12px', borderTopRightRadius: '12px' }}>
          <h3 style={{ margin: 0, fontSize: '14px', color: '#e0e0e6', fontWeight: '500' }}>Edit Trade</h3>
          <button onClick={onClose} style={{ background: 'transparent', border: 'none', color: '#8b8b9c', fontSize: '20px', cursor: 'pointer' }}>×</button>
        </div>

        <div style={{ display: 'flex', padding: '0', borderBottom: '1px solid #3f3f52', background: '#242430' }}>
          <div
            onClick={() => setActiveTab('General')}
            style={{ flex: 1, textAlign: 'center', padding: '12px', cursor: 'pointer', color: activeTab === 'General' ? '#e0e0e6' : '#8b8b9c', borderBottom: activeTab === 'General' ? '2px solid var(--accent-blue)' : '2px solid transparent', fontSize: '13px' }}
          >General</div>
          <div
            onClick={() => setActiveTab('Journal')}
            style={{ flex: 1, textAlign: 'center', padding: '12px', cursor: 'pointer', color: activeTab === 'Journal' ? '#e0e0e6' : '#8b8b9c', borderBottom: activeTab === 'Journal' ? '2px solid var(--accent-blue)' : '2px solid transparent', fontSize: '13px' }}
          >Journal</div>
        </div>

        <div style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '20px' }}>

          <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1.5fr 1fr 1fr 0.8fr', gap: '16px', alignItems: 'end' }}>
            <div>
              <label style={labelStyle}>Market</label>
              <select style={inputStyle}>
                <option>STOCK</option>
              </select>
            </div>
            <div>
              <label style={labelStyle}>Symbol</label>
              <input name="ticker" style={inputStyle} value={formData.ticker} onChange={handleChange} />
            </div>
            <div>
              <label style={labelStyle}>Target (R)</label>
              <input name="target_r" style={inputStyle} value={formData.target_r} onChange={handleChange} placeholder="3" type="number" step="0.5" />
            </div>
            <div>
              <label style={labelStyle}>Stop-Loss</label>
              <input name="stop_loss" style={inputStyle} value={formData.stop_loss} onChange={handleChange} />
            </div>
            <div>
              <button onClick={handleToggleSide} style={{
                width: '100%', padding: '8px', border: 'none', borderRadius: '4px', color: '#fff', fontSize: '12px', fontWeight: 'bold', cursor: 'pointer',
                background: formData.direction === 'LONG' ? 'var(--success)' : 'var(--danger)'
              }}>
                {formData.direction}
              </button>
            </div>
          </div>

          <div>
            <label style={labelStyle}>Tags</label>
            <TagPicker value={tags} onChange={setTags} category="setup" />
          </div>

          <div style={{
            background: 'rgba(0,0,0,0.1)', border: '1px solid #3f3f52', borderRadius: '8px', padding: '16px',
            display: 'flex', flexDirection: 'column', gap: '12px'
          }}>
            {/* Column headers */}
            <div style={{ display: 'grid', gridTemplateColumns: '32px 80px 2fr 1fr 1fr 1fr', gap: '10px', alignItems: 'center' }}>
              <div></div>
              <div style={{ color: '#8b8b9c', fontSize: '11px' }}>Action</div>
              <div style={{ color: '#8b8b9c', fontSize: '11px' }}>Date/Time</div>
              <div style={{ color: '#8b8b9c', fontSize: '11px' }}>Quantity</div>
              <div style={{ color: '#8b8b9c', fontSize: '11px' }}>Price</div>
              <div style={{ color: '#8b8b9c', fontSize: '11px' }}>Fee</div>
            </div>

            {/* Dynamic action rows */}
            {actions.map((action) => (
              <div key={action.id} style={{ display: 'grid', gridTemplateColumns: '32px 80px 2fr 1fr 1fr 1fr', gap: '10px', alignItems: 'center' }}>
                <button
                  onClick={() => removeAction(action.id)}
                  style={{ width: '28px', height: '28px', borderRadius: '4px', background: 'var(--danger)', color: '#fff', border: 'none', cursor: 'pointer', display: 'flex', justifyContent: 'center', alignItems: 'center', fontSize: '14px', flexShrink: 0 }}
                >×</button>
                <button
                  onClick={() => toggleActionType(action.id)}
                  style={{
                    background: action.type === 'BUY' ? 'var(--success)' : 'var(--danger)',
                    color: '#fff', border: 'none', borderRadius: '4px', padding: '6px 4px',
                    fontSize: '11px', fontWeight: 'bold', cursor: 'pointer', width: '100%'
                  }}
                >
                  {action.type}
                </button>
                <input
                  type="date"
                  value={action.date}
                  onChange={e => updateAction(action.id, 'date', e.target.value)}
                  style={inputStyle}
                />
                <input
                  type="number"
                  value={action.quantity}
                  onChange={e => updateAction(action.id, 'quantity', e.target.value)}
                  style={inputStyle}
                  placeholder="0"
                />
                <input
                  type="number"
                  step="0.01"
                  value={action.price}
                  onChange={e => updateAction(action.id, 'price', e.target.value)}
                  style={inputStyle}
                  placeholder="0.00"
                />
                <input
                  type="number"
                  step="0.01"
                  value={action.fee}
                  onChange={e => updateAction(action.id, 'fee', e.target.value)}
                  style={inputStyle}
                  placeholder="0"
                />
              </div>
            ))}

            {/* Add action button */}
            <div style={{ display: 'flex', justifyContent: 'center', marginTop: '4px' }}>
              <button
                onClick={addAction}
                style={{ background: 'var(--accent-blue)', color: '#fff', border: 'none', width: '32px', height: '32px', borderRadius: '50%', fontSize: '18px', cursor: 'pointer', display: 'flex', justifyContent: 'center', alignItems: 'center' }}
              >+</button>
            </div>

          </div>

        </div>

        <div style={{ display: 'flex', justifyContent: 'space-between', padding: '16px 24px', background: '#242430', borderTop: '1px solid #3f3f52', borderBottomLeftRadius: '12px', borderBottomRightRadius: '12px' }}>
          <button onClick={handleDelete} disabled={busy} style={{ background: 'var(--danger)', color: '#fff', border: 'none', padding: '8px 24px', borderRadius: '20px', cursor: busy ? 'not-allowed' : 'pointer', fontWeight: '500', opacity: busy ? 0.6 : 1 }}>{busy ? '…' : 'Delete'}</button>
          <button onClick={handleSave} disabled={busy} style={{ background: 'var(--accent-blue)', color: '#fff', border: 'none', padding: '8px 24px', borderRadius: '20px', cursor: busy ? 'not-allowed' : 'pointer', fontWeight: '500', opacity: busy ? 0.6 : 1 }}>{busy ? 'Saving…' : 'Save'}</button>
        </div>

      </div>
    </div>
  );
};

export default EditTradeModal;
