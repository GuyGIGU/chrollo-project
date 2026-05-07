import React, { useState } from 'react';
import TagPicker from './TagPicker';
import { API_BASE } from '../api';

const LogTradeForm = ({ onSave }) => {
  const [formData, setFormData] = useState({
    opening_date: new Date().toISOString().split('T')[0],
    direction: 'LONG',
    ticker: '',
    entry_price: '',
    stop_loss: '',
    quantity: '',
    position_size: ''
  });
  const [tags, setTags] = useState([]);

  const handleChange = (e) => {
    setFormData({...formData, [e.target.name]: e.target.value});
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      // Clean data types for FastAPI
      const payload = {
        ...formData,
        entry_price: parseFloat(formData.entry_price),
        stop_loss: parseFloat(formData.stop_loss),
        quantity: parseInt(formData.quantity),
        position_size: parseFloat(formData.entry_price) * parseInt(formData.quantity)
      };

      const res = await fetch(`${API_BASE}/trades/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (res.ok) {
        const saved = await res.json();
        if (tags.length > 0 && saved?.id) {
          await fetch(`${API_BASE}/trades/${saved.id}/tags`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ tag_ids: tags.map(t => t.id) }),
          }).catch(() => {});
        }
        if (onSave) onSave();
      } else {
        const err = await res.json();
        alert('Error saving trade: ' + JSON.stringify(err));
      }
    } catch (error) {
      console.error(error);
      alert('Error communicating with backend server.');
    }
  };

  return (
    <div className="glass-panel" style={{gridColumn: "1 / -1"}}>
      <h2 style={{borderBottom: '1px solid var(--border-color)', paddingBottom: '1rem', marginBottom: '1.5rem'}}>Log New Trade</h2>
      <form onSubmit={handleSubmit} style={{display: 'flex', flexDirection: 'column', gap: '1rem'}}>
        
        <div className="grid-cols-4">
          <div className="form-group">
            <label>Ticker</label>
            <input name="ticker" type="text" placeholder="AAPL" value={formData.ticker} onChange={handleChange} required />
          </div>
          <div className="form-group">
            <label>Date</label>
            <input name="opening_date" type="date" value={formData.opening_date} onChange={handleChange} required />
          </div>
          <div className="form-group">
            <label>Direction</label>
            <select name="direction" value={formData.direction} onChange={handleChange}>
              <option value="LONG">Long</option>
              <option value="SHORT">Short</option>
            </select>
          </div>
          <div className="form-group">
            <label>Quantity</label>
            <input name="quantity" type="number" placeholder="Shares" value={formData.quantity} onChange={handleChange} required />
          </div>
        </div>

        <div className="grid-cols-2">
          <div className="form-group">
            <label>Entry Price</label>
            <input name="entry_price" type="number" step="0.01" value={formData.entry_price} onChange={handleChange} required />
          </div>
          <div className="form-group">
            <label>Stop Loss</label>
            <input name="stop_loss" type="number" step="0.01" value={formData.stop_loss} onChange={handleChange} required />
          </div>
        </div>

        <div className="form-group">
          <label>Tags</label>
          <TagPicker value={tags} onChange={setTags} category="setup" />
        </div>

        <div style={{marginTop: '1.5rem', borderTop: '1px solid var(--border-color)', paddingTop: '1.5rem'}}>
          <button type="submit" className="btn btn-primary" style={{width: '200px'}}>Save Trade</button>
        </div>
      </form>
    </div>
  );
};

export default LogTradeForm;
