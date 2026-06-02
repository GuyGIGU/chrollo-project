import { useState } from 'react';
import { API_BASE } from '../api';

export default function useArchiveMaintenance() {
  const [historyOpen, setHistoryOpen] = useState(false);
  const [historyRuns, setHistoryRuns] = useState(null);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [analysisOpen, setAnalysisOpen] = useState(false);
  const [analysisText, setAnalysisText] = useState('');
  const [analysisLoading, setAnalysisLoading] = useState(false);
  const [analysisError, setAnalysisError] = useState(null);

  const openHistory = async () => {
    setHistoryOpen(true);
    setHistoryLoading(true);
    try {
      const response = await fetch(`${API_BASE}/scan-status/history?limit=20`);
      const data = await response.json().catch(() => ({}));
      setHistoryRuns(Array.isArray(data.runs) ? data.runs : []);
    } catch (error) {
      console.error('Failed to fetch scan history:', error);
      setHistoryRuns([]);
    } finally {
      setHistoryLoading(false);
    }
  };

  const openAnalysis = async (refresh = false) => {
    setAnalysisOpen(true);
    setAnalysisLoading(true);
    setAnalysisError(null);
    try {
      const response = await fetch(`${API_BASE}/archive/analysis${refresh ? '?refresh=true' : ''}`);
      const data = await response.json().catch(() => ({}));
      if (response.ok) setAnalysisText(data.report || '(empty report)');
      else setAnalysisError((data.detail || `HTTP ${response.status}`).toString());
    } catch (error) {
      setAnalysisError(`Network error: ${error.message || error}`);
    } finally {
      setAnalysisLoading(false);
    }
  };

  return {
    analysisError,
    analysisLoading,
    analysisOpen,
    analysisText,
    closeAnalysis: () => setAnalysisOpen(false),
    closeHistory: () => setHistoryOpen(false),
    historyLoading,
    historyOpen,
    historyRuns,
    openAnalysis,
    openHistory,
  };
}
