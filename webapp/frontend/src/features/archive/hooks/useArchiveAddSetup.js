import { useState } from 'react';
import { API_BASE } from '../../../api/base';

export default function useArchiveAddSetup(fetchAll) {
  const [open, setOpen] = useState(false);
  const [ticker, setTicker] = useState('');
  const [date, setDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [label, setLabel] = useState('');
  const [notes, setNotes] = useState('');
  const [adding, setAdding] = useState(false);
  const [error, setError] = useState(null);

  const openModal = () => {
    setError(null);
    setOpen(true);
  };

  const addSetup = async () => {
    setAdding(true);
    setError(null);
    try {
      const response = await fetch(`${API_BASE}/archive/add-setup`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ticker: ticker.trim().toUpperCase(),
          scan_date: date,
          quality_label: label || null,
          notes: notes || null,
        }),
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        setError(payload.detail || `HTTP ${response.status}`);
        return;
      }
      setOpen(false);
      setTicker('');
      setNotes('');
      setLabel('');
      await fetchAll();
    } catch (err) {
      setError(String(err));
    } finally {
      setAdding(false);
    }
  };

  return {
    adding,
    addSetup,
    date,
    error,
    label,
    notes,
    open,
    openModal,
    setDate,
    setLabel,
    setNotes,
    setOpen,
    setTicker,
    ticker,
  };
}
