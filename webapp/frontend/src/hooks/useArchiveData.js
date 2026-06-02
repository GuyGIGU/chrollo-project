import { useCallback, useEffect, useState } from 'react';
import { API_BASE } from '../api';
import { SOURCE_FILTERS } from '../utils/archiveTabUtils';

export default function useArchiveData({ sortBy, sortDir, sourceFilter, tierFilter, typeFilter }) {
  const [setups, setSetups] = useState([]);
  const [stats, setStats] = useState(null);
  const [calibration, setCalibration] = useState(null);
  const [equityCurve, setEquityCurve] = useState(null);
  const [loading, setLoading] = useState(true);
  const [updating, setUpdating] = useState(false);
  const [updateMsg, setUpdateMsg] = useState(null);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ limit: '500', sort_by: sortBy, sort_dir: sortDir });
      const sourceParam = SOURCE_FILTERS.find(([key]) => key === sourceFilter)?.[2];
      if (tierFilter !== 'ALL') params.set('tier', tierFilter);
      if (typeFilter !== 'ALL') params.set('setup_type', typeFilter);
      if (sourceParam) params.set('source', sourceParam);

      const [setupsRes, statsRes, calRes, eqRes] = await Promise.all([
        fetch(`${API_BASE}/archive/setups?${params.toString()}`),
        fetch(`${API_BASE}/archive/stats`),
        fetch(`${API_BASE}/archive/calibration`),
        fetch(`${API_BASE}/archive/calibration/equity-curve`),
      ]);
      if (setupsRes.ok) setSetups(await setupsRes.json());
      if (statsRes.ok) setStats(await statsRes.json());
      if (calRes.ok) setCalibration(await calRes.json());
      if (eqRes.ok) setEquityCurve(await eqRes.json());
    } catch (error) {
      console.error('Failed to fetch archive data:', error);
    } finally {
      setLoading(false);
    }
  }, [sortBy, sortDir, sourceFilter, tierFilter, typeFilter]);

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  const updateReturns = async () => {
    setUpdating(true);
    setUpdateMsg(null);
    try {
      const response = await fetch(`${API_BASE}/archive/update-returns`, { method: 'POST' });
      const data = await response.json().catch(() => ({}));
      if (response.ok && data.returncode === 0) {
        setUpdateMsg({ ok: true, text: extractUpdateSummary(data) });
        await fetchAll();
      } else {
        const text = (data.stderr || data.detail || `HTTP ${response.status}`).trim();
        setUpdateMsg({ ok: false, text: text.slice(-300) || 'Update failed.' });
      }
    } catch (error) {
      setUpdateMsg({ ok: false, text: `Network error: ${error.message || error}` });
    } finally {
      setUpdating(false);
      setTimeout(() => setUpdateMsg(null), 8000);
    }
  };

  const updateSetupLabel = useCallback(async (id, label) => {
    try {
      await fetch(`${API_BASE}/archive/setups/${id}/label`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ quality_label: label }),
      });
      setSetups(previous => previous.map(setup =>
        setup.id === id ? { ...setup, quality_label: label } : setup));
    } catch (error) {
      console.error('Failed to update label:', error);
    }
  }, []);

  return {
    calibration,
    equityCurve,
    fetchAll,
    loading,
    setSetups,
    setups,
    stats,
    updateMsg,
    updateReturns,
    updateSetupLabel,
    updating,
  };
}

const extractUpdateSummary = (data) => {
  const combined = `${data.stdout || ''}\n${data.stderr || ''}`.trim();
  const lines = combined.split('\n').filter(Boolean);
  const summary = [...lines].reverse().find(line =>
    /updated|no setups|setups need/i.test(line)) || lines[0] || 'Done.';
  return summary.replace(/^\S+\s+\S+\s+\S+\s+/, '').trim();
};
