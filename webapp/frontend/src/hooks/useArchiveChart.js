import { useState } from 'react';
import { API_BASE } from '../api';

export default function useArchiveChart() {
  const [chartData, setChartData] = useState(null);
  const [chartLoading, setChartLoading] = useState(false);
  const [chartTicker, setChartTicker] = useState(null);
  const [chartSetup, setChartSetup] = useState(null);
  const [linkedTrades, setLinkedTrades] = useState([]);

  const openChart = async (setup, bulkCharts) => {
    setChartTicker(setup.ticker);
    setChartSetup(setup);
    setLinkedTrades([]);
    fetchLinkedTrades(setup.id, setLinkedTrades);

    if (bulkCharts[setup.id]) {
      setChartData(bulkCharts[setup.id]);
      return;
    }

    setChartLoading(true);
    try {
      const response = await fetch(`${API_BASE}/archive/setups/${setup.id}/chart`);
      if (!response.ok) {
        closeChart();
        return;
      }
      setChartData(await response.json());
    } catch (error) {
      console.error('Error fetching chart data:', error);
      closeChart();
    } finally {
      setChartLoading(false);
    }
  };

  const closeChart = () => {
    setChartData(null);
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
