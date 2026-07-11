import { useState } from 'react';
import { API_BASE } from '../api';

// Marks CRUD for the calibration page (Task 12). Writes carry the same-app
// header (the backend's cross-app write guard) and echo the server's named
// failure classes into saveError so the page can render something actionable.
// The tally counts saves THIS sitting — the "am I making progress" number.
const WRITE_HEADERS = {
  'Content-Type': 'application/json',
  'X-Chrollo-Client': 'chrollo-dashboard',
};

function detailToError(body, status) {
  const detail = body?.detail;
  if (detail?.problems) {
    return { class: detail.class, message: detail.problems.join('; ') };
  }
  if (detail?.class) return detail;
  return { class: 'unknown', message: `save failed (${status})` };
}

export default function useCalibrationMarks() {
  const [marks, setMarks] = useState([]);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState(null); // {class, message} | null
  const [tally, setTally] = useState(0);

  const refresh = async (ticker) => {
    if (!ticker) {
      setMarks([]);
      return;
    }
    try {
      const response = await fetch(
        `${API_BASE}/calibration/marks?ticker=${encodeURIComponent(ticker)}`);
      const body = await response.json().catch(() => null);
      setMarks(response.ok && Array.isArray(body) ? body : []);
    } catch (error) {
      console.error('calibration marks list failed:', error);
      setMarks([]);
    }
  };

  const saveMark = async (payload, editingId = null) => {
    setSaving(true);
    setSaveError(null);
    try {
      const url = editingId
        ? `${API_BASE}/calibration/marks/${editingId}`
        : `${API_BASE}/calibration/marks`;
      const response = await fetch(url, {
        method: editingId ? 'PUT' : 'POST',
        headers: WRITE_HEADERS,
        body: JSON.stringify(payload),
      });
      const body = await response.json().catch(() => null);
      if (!response.ok) {
        setSaveError(detailToError(body, response.status));
        return null;
      }
      setTally((t) => t + 1);
      await refresh(payload.ticker);
      return body; // the row AS PERSISTED (echo contract)
    } catch (error) {
      console.error('calibration mark save failed:', error);
      setSaveError({ class: 'network', message: 'backend unreachable — mark NOT saved' });
      return null;
    } finally {
      setSaving(false);
    }
  };

  const removeMark = async (id, ticker) => {
    try {
      const response = await fetch(`${API_BASE}/calibration/marks/${id}`, {
        method: 'DELETE',
        headers: WRITE_HEADERS,
      });
      if (response.ok) await refresh(ticker);
      return response.ok;
    } catch (error) {
      console.error('calibration mark delete failed:', error);
      return false;
    }
  };

  return { marks, saving, saveError, tally, refresh, saveMark, removeMark };
}
