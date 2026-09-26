import { useState } from 'react';
import { API_BASE } from '../../../api/base';

export default function useArchiveMaintenance() {
  const [analysisOpen, setAnalysisOpen] = useState(false);
  const [analysisText, setAnalysisText] = useState('');
  const [analysisLoading, setAnalysisLoading] = useState(false);
  const [analysisError, setAnalysisError] = useState(null);

  const openAnalysis = async (refresh = false) => {
    setAnalysisOpen(true);
    setAnalysisLoading(true);
    setAnalysisError(null);
    try {
      const response = await fetch(`${API_BASE}/archive/analysis${refresh ? '?refresh=true' : ''}`, {
        headers: { 'X-Chrollo-Client': 'chrollo-dashboard' },
      });
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
    openAnalysis,
  };
}
