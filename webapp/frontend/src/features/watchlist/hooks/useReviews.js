import { useCallback, useEffect, useRef, useState } from 'react';
import { API_BASE } from '../../../api/base';
import { toast } from '../../../shared/components/feedback.js';

// The operator's two verdicts on a setup, both rows in `setup_reviews`:
//   LIKED  — "this is the kind of setup I want more of" (the screener card's
//            heart; a preference signal for ranking, 2026-09-02)
//   PASSED — "saw it and skipped it" (the archive table; the missed-winners
//            negative, and the class that makes a like INFORMATIVE — without it
//            an unliked card cannot be told from one that was never looked at)
// They are mutually exclusive server-side (one review row per setup), so a set
// can never hold the same ticker twice; the two sets are kept apart here for the
// same reason.
//
// Mirrors useWatchlist: optimistic toggle with rollback, loaded once on mount.
// The backend resolves a bare ticker to its current episode's first-seen date,
// so the same mark shows up on the archive table and in the reports.
function useReviews() {
  const [passed, setPassed] = useState(() => new Set());
  const [liked, setLiked] = useState(() => new Set());
  const [likesStatus, setLikesStatus] = useState('loading');
  const pendingLikes = useRef(new Set());

  const reloadLiked = useCallback(async () => {
    setLikesStatus('loading');
    try {
      const response = await fetch(`${API_BASE}/archive/reviews/liked`);
      if (!response.ok) throw new Error(`liked setups ${response.status}`);
      const body = await response.json();
      if (!Array.isArray(body?.tickers)) throw new Error('Unreadable liked setups');
      setLiked(new Set(body.tickers));
      setLikesStatus('ready');
    } catch (error) {
      console.error('Could not load liked setups', error);
      setLikesStatus('error');
    }
  }, []);

  useEffect(() => {
    // `response.ok` is NOT proof the API answered: the backend serves the SPA
    // from a catch-all, so an unknown route comes back 200 with index.html — a
    // deploy that lags the frontend looks like success. json() throws on that
    // HTML and the catch swallows it (an empty set, which is the honest
    // "unknown"), and Array.isArray keeps any other 200-shaped body from
    // becoming a Set of characters.
    const load = (verdict, apply) => fetch(`${API_BASE}/archive/reviews/${verdict}`)
      .then(response => response.ok ? response.json() : { tickers: [] })
      .then(data => apply(new Set(Array.isArray(data?.tickers) ? data.tickers : [])))
      .catch(() => {});
    load('passed', setPassed);
    reloadLiked();
  }, [reloadLiked]);

  // The POST fires OUTSIDE the updater — React updaters must stay pure (a
  // strict-mode double invocation would double-toggle the server state).
  const togglePassed = useCallback((ticker) => {
    const wasOn = passed.has(ticker);
    setPassed(previous => {
      const next = new Set(previous);
      if (wasOn) next.delete(ticker);
      else next.add(ticker);
      return next;
    });

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
  }, [passed]);

  // The like's own toggle. It drops the ticker from `passed` on success because
  // the server keeps ONE row per setup: liking a setup you had passed replaces
  // the verdict, and a stale local `passed` would leave both marks lit.
  const toggleLiked = useCallback((ticker) => {
    if (pendingLikes.current.has(ticker)) return;
    if (likesStatus !== 'ready') {
      toast('Likes have not loaded. Open the Liked view to retry before editing.', { tone: 'warning' });
      return;
    }
    pendingLikes.current.add(ticker);
    const wasOn = liked.has(ticker);
    setLiked(previous => {
      const next = new Set(previous);
      if (wasOn) next.delete(ticker);
      else next.add(ticker);
      return next;
    });

    fetch(`${API_BASE}/archive/reviews/like`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ticker }),
    })
      .then(response => {
        if (!response.ok) throw new Error('like toggle failed');
        return response.json();
      })
      .then(result => {
        if (result?.liked) {
          setPassed(current => {
            if (!current.has(ticker)) return current;
            const next = new Set(current);
            next.delete(ticker);
            return next;
          });
        }
      })
      .catch(error => {
        console.error('Like toggle failed, reverting', error);
        setLiked(current => rollback(current, ticker, wasOn));
        toast(`${ticker}: your like change did not save. The previous heart was restored.`, { tone: 'danger' });
      })
      .finally(() => pendingLikes.current.delete(ticker));
  }, [liked, likesStatus]);

  return { passed, togglePassed, liked, toggleLiked, likesStatus, reloadLiked };
}

function rollback(current, ticker, wasOn) {
  const rolled = new Set(current);
  if (wasOn) rolled.add(ticker);
  else rolled.delete(ticker);
  return rolled;
}

export default useReviews;
