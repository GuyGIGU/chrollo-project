import { useEffect, useState } from 'react';
import { API_BASE } from '../../api/base';

export default function usePositionChartData(symbol) {
  const [state, setState] = useState({ loading: false, error: '', data: null });

  useEffect(() => {
    if (!symbol) return undefined;
    const controller = new AbortController();
    setState({ loading: true, error: '', data: null });

    fetch(`${API_BASE}/market-data/chart/${encodeURIComponent(symbol)}?days=180`, {
      signal: controller.signal,
    })
      .then((response) => {
        if (!response.ok) throw new Error('Chart data unavailable');
        if (!response.headers.get('content-type')?.includes('application/json')) {
          throw new Error('Restart the backend to enable live chart data.');
        }
        return response.json();
      })
      .then((data) => {
        if (!data?.candles?.length) throw new Error('Chart data unavailable');
        setState({ loading: false, error: '', data });
      })
      .catch((error) => {
        if (error.name !== 'AbortError') {
          setState({ loading: false, error: error.message, data: null });
        }
      });

    return () => controller.abort();
  }, [symbol]);

  return state;
}
