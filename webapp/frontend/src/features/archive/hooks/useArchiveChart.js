import { useRef, useState } from 'react';
import { API_BASE } from '../../../api/base';

export default function useArchiveChart() {
  const [chartData, setChartData] = useState(null);
  const [chartLoading, setChartLoading] = useState(false);
  const [chartTicker, setChartTicker] = useState(null);
  const [chartSetup, setChartSetup] = useState(null);
  const [linkedTrades, setLinkedTrades] = useState([]);
  // Request token (the useDrilldown mold): a stale resolution — success OR
  // failure — must never repaint or close a newer view.
  const requestRef = useRef(0);

  const openChart = async (setup) => {
    const token = ++requestRef.current;
    setChartTicker(setup.ticker);
    setChartSetup(setup);
    setLinkedTrades([]);
    fetchLinkedTrades(setup.id, (linked) => {
      if (token === requestRef.current) setLinkedTrades(linked);
    });

    setChartLoading(true);
    try {
      const response = await fetch(`${API_BASE}/archive/setups/${setup.id}/chart`);
      const data = response.ok ? await response.json() : null;
      if (token !== requestRef.current) return;
      if (data == null) {
        closeChart();
        return;
      }
      setChartData(data);
    } catch (error) {
      if (token !== requestRef.current) return;
      console.error('Error fetching chart data:', error);
      closeChart();
    } finally {
      if (token === requestRef.current) setChartLoading(false);
    }
  };

  // Invalidate any in-flight request so a late response can't reopen the view.
  const closeChart = () => {
    requestRef.current += 1;
    setChartData(null);
    setChartLoading(false);
    setChartTicker(null);
    setChartSetup(null);
  };

  return {
    chartData,
    chartLoading,
    chartSetup,
    chartTicker,
    closeChart,
    linkedTrades,
    openChart,
  };
}

const fetchLinkedTrades = (setupId, setLinkedTrades) => {
  fetch(`${API_BASE}/archive/setups/${setupId}/linked-trades?window_days=7`)
    .then(response => (response.ok ? response.json() : []))
    .then(setLinkedTrades)
    .catch(() => setLinkedTrades([]));
};
