import { useCallback, useEffect, useState } from 'react';
import { API_BASE } from '../api';

function useWatchlist() {
  const [watchlist, setWatchlist] = useState(() => new Set());

  useEffect(() => {
    fetch(`${API_BASE}/watchlist/`)
      .then(response => response.ok ? response.json() : [])
      .then(items => setWatchlist(new Set(items.map(item => item.ticker))))
      .catch(() => {});
  }, []);

  const toggleWatchlist = useCallback((ticker) => {
    setWatchlist(previous => {
      const next = new Set(previous);
      const isOn = next.has(ticker);
      if (isOn) next.delete(ticker);
      else next.add(ticker);

      fetch(`${API_BASE}/watchlist/${encodeURIComponent(ticker)}`, {
        method: isOn ? 'DELETE' : 'POST',
      })
        .then(response => {
          if (!response.ok) throw new Error('watchlist write failed');
        })
        .catch(error => {
          console.error('Watchlist toggle failed, reverting', error);
          setWatchlist(current => rollbackWatchlist(current, ticker, isOn));
        });

      return next;
    });
  }, []);

  return { watchlist, toggleWatchlist };
}

function rollbackWatchlist(current, ticker, wasOn) {
  const rolled = new Set(current);
  if (wasOn) rolled.add(ticker);
  else rolled.delete(ticker);
  return rolled;
}

export default useWatchlist;
