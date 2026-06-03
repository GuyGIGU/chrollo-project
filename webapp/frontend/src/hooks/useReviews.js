import { useCallback, useEffect, useState } from 'react';
import { API_BASE } from '../api';

// Tracks which screener tickers are marked "saw & passed". Mirrors useWatchlist:
// optimistic toggle with rollback, loaded once on mount. The backend resolves a
// bare ticker to its current episode's first-seen date, so the same mark shows
// up on the archive table and in the missed-winners report.
function useReviews() {
  const [passed, setPassed] = useState(() => new Set());

  useEffect(() => {
    fetch(`${API_BASE}/archive/reviews/passed`)
      .then(response => response.ok ? response.json() : { tickers: [] })
      .then(data => setPassed(new Set(data.tickers || [])))
      .catch(() => {});
  }, []);

  const togglePassed = useCallback((ticker) => {
    setPassed(previous => {
      const next = new Set(previous);
      const wasOn = next.has(ticker);
      if (wasOn) next.delete(ticker);
      else next.add(ticker);

      fetch(`${API_BASE}/archive/reviews/toggle`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ticker }),
      })
        .then(response => {
          if (!response.ok) throw new Error('review toggle failed');
        })
        .catch(error => {
          console.error('Pass toggle failed, reverting', error);
          setPassed(current => rollback(current, ticker, wasOn));
        });

      return next;
    });
  }, []);

  return { passed, togglePassed };
}

function rollback(current, ticker, wasOn) {
  const rolled = new Set(current);
  if (wasOn) rolled.add(ticker);
  else rolled.delete(ticker);
  return rolled;
}

export default useReviews;
