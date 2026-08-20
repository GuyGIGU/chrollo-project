import { useCallback, useEffect, useState } from 'react';
import { API_BASE } from '../api';
import { toast } from '../components/ui/feedback';
import { SOURCE_FILTERS } from '../utils/archiveTabUtils';

export default function useArchiveData({ sortBy, sortDir, sourceFilter, tierFilter, typeFilter }) {
  const [setups, setSetups] = useState([]);
  const [stats, setStats] = useState(null);
  const [health, setHealth] = useState(null);
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

      const [setupsRes, statsRes, healthRes, calRes, eqRes] = await Promise.all([
        fetch(`${API_BASE}/archive/episodes?${params.toString()}`),
        fetch(`${API_BASE}/archive/stats`),
        fetch(`${API_BASE}/archive/health`),
        fetch(`${API_BASE}/archive/calibration`),
        fetch(`${API_BASE}/archive/calibration/equity-curve`),
      ]);
      if (setupsRes.ok) setSetups(await setupsRes.json());
      if (statsRes.ok) setStats(await statsRes.json());
      if (healthRes.ok) setHealth(await healthRes.json());
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
      const response = await fetch(`${API_BASE}/archive/setups/${id}/label`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ quality_label: label }),
      });
      if (!response.ok) {
        toast(`Label save failed (HTTP ${response.status})`, { tone: 'danger' });
        return;
      }
      setSetups(previous => previous.map(setup =>
        setup.id === id ? { ...setup, quality_label: label } : setup));
    } catch (error) {
      console.error('Failed to update label:', error);
      toast('Label save failed — network error.', { tone: 'danger' });
    }
  }, []);

  // "saw & passed" toggle, keyed to the episode's first-seen (entry) date.
  const togglePassed = useCallback(async (ticker, scanDate) => {
    try {
      const response = await fetch(`${API_BASE}/archive/reviews/toggle`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ticker, scan_date: scanDate }),
      });
      if (!response.ok) return;
      const data = await response.json();
      setSetups(previous => previous.map(setup =>
        (setup.ticker === ticker && setup.first_seen === scanDate)
          ? { ...setup, passed: data.passed, review_note: data.passed ? setup.review_note : null }
          : setup));
    } catch (error) {
      console.error('Failed to toggle passed:', error);
    }
  }, []);

  const markReviewReason = useCallback(async (ticker, scanDate, note) => {
    try {
      const response = await fetch(`${API_BASE}/archive/reviews/mark`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ticker, scan_date: scanDate, note }),
      });
      if (!response.ok) return;
      const data = await response.json();
      setSetups(previous => previous.map(setup =>
        (setup.ticker === ticker && setup.first_seen === scanDate)
          ? { ...setup, passed: true, review_note: data.review_note }
          : setup));
    } catch (error) {
      console.error('Failed to mark review reason:', error);
    }
  }, []);

  return {
    calibration,
    equityCurve,
    fetchAll,
    health,
    loading,
    setSetups,
    setups,
    stats,
    markReviewReason,
    togglePassed,
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
