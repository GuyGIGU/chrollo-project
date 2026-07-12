import { useRef, useState } from 'react';
import { API_BASE } from '../api';
import { duplicateConflictId } from '../utils/calibrationMarking';
import { buildCoverageRows } from '../utils/calibrationTables';

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
  // A create that collided with an existing identity, parked for the operator
  // to resolve EXPLICITLY (never auto-overwritten): {payload, existingId}.
  const [conflict, setConflict] = useState(null);
  // Every ticker calibrated so far: [{ticker, count, boxes, negatives,
  // latestAsOf}] — the operator's "what have I covered" list, aggregated from
  // ALL marks by the tested pure helper. Unsorted here; the coverage table
  // owns its (controlled) sort, same as the watchlist.
  const [summary, setSummary] = useState([]);
  // Monotonic marks-fetch generation: fast ticker switches (coverage clicks,
  // worklist steps, post-save refresh) race, and only the LAST requested
  // ticker's response may win setMarks — a stale one would paint the previous
  // ticker's marks over the current frame, and an edit/delete in that window
  // would act on the wrong ticker. Mirrors useCalibrationChart's guard.
  const marksReqGen = useRef(0);

  const refreshSummary = async () => {
    try {
      const response = await fetch(`${API_BASE}/calibration/marks`);
      const body = await response.json().catch(() => null);
      if (!response.ok || !Array.isArray(body)) return;
      setSummary(buildCoverageRows(body));
    } catch (error) {
      console.error('calibration summary failed:', error);
    }
  };

  const refresh = async (ticker) => {
    const gen = (marksReqGen.current += 1);  // supersede any in-flight marks fetch
    if (!ticker) {
      setMarks([]);
      return;
    }
    try {
      const response = await fetch(
        `${API_BASE}/calibration/marks?ticker=${encodeURIComponent(ticker)}`);
      const body = await response.json().catch(() => null);
      if (gen !== marksReqGen.current) return;  // a newer refresh won — drop this stale response
      setMarks(response.ok && Array.isArray(body) ? body : []);
    } catch (error) {
      if (gen !== marksReqGen.current) return;
      console.error('calibration marks list failed:', error);
      setMarks([]);
    }
  };

  const writeMark = (payload, id) => fetch(
    id ? `${API_BASE}/calibration/marks/${id}` : `${API_BASE}/calibration/marks`,
    { method: id ? 'PUT' : 'POST', headers: WRITE_HEADERS,
      body: JSON.stringify(payload) });

  // The one write path (create when id is null, update otherwise). On a
  // duplicate-identity create it PARKS a conflict instead of overwriting — the
  // operator resolves it deliberately via resolveConflict(). Returns the
  // persisted row, or null (error/conflict; the draft is never lost).
  const persist = async (payload, id) => {
    const response = await writeMark(payload, id);
    const body = await response.json().catch(() => null);
    if (!response.ok) {
      const existingId = duplicateConflictId(body, id);
      if (existingId != null) {
        setConflict({ payload, existingId });
        setSaveError({ class: 'duplicate_mark', existingId,
          message: 'a mark already exists for this frame + label — '
            + 'click Update existing to overwrite it, or add a label to keep both' });
      } else {
        setSaveError(detailToError(body, response.status));
      }
      return null;
    }
    setConflict(null);
    setTally((t) => t + 1);
    await refresh(payload.ticker);
    await refreshSummary();
    return body; // the row AS PERSISTED (echo contract)
  };

  const saveMark = async (payload, editingId = null) => {
    setSaving(true);
    setSaveError(null);
    try {
      return await persist(payload, editingId);
    } catch (error) {
      console.error('calibration mark save failed:', error);
      setSaveError({ class: 'network', message: 'backend unreachable — mark NOT saved' });
      return null;
    } finally {
      setSaving(false);
    }
  };

  // Drop a parked conflict when it no longer applies — the operator scrubbed
  // to another frame, or added a label to keep both marks. Clears the paired
  // duplicate error with it so the "Update existing" affordance disappears.
  const clearConflict = () => {
    setConflict(null);
    setSaveError((e) => (e?.class === 'duplicate_mark' ? null : e));
  };

  // Explicit overwrite of the existing mark a create just collided with — the
  // operator's confirmed "yes, update that one". Never fires on its own.
  const resolveConflict = async () => {
    if (!conflict) return null;
    setSaving(true);
    setSaveError(null);
    try {
      return await persist(conflict.payload, conflict.existingId);
    } catch (error) {
      console.error('calibration mark conflict-resolve failed:', error);
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
      if (response.ok) {
        await refresh(ticker);
        await refreshSummary();
      }
      return response.ok;
    } catch (error) {
      console.error('calibration mark delete failed:', error);
      return false;
    }
  };

  return { marks, saving, saveError, tally, summary, conflict,
           refresh, refreshSummary, saveMark, resolveConflict,
           clearConflict, removeMark };
}
