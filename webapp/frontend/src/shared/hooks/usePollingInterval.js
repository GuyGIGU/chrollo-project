import { useEffect, useRef } from 'react';

/**
 * Run `callback` on an interval that PAUSES while the tab is hidden and resumes
 * (with an immediate refresh) when it becomes visible again. One shared primitive
 * so the Home zones don't each hand-roll a `setInterval` that keeps hammering the
 * backend on a backgrounded tab.
 *
 * The callback is read through a ref so a changing closure never resets the timer;
 * only `delayMs` / `immediate` do.
 */
export default function usePollingInterval(callback, delayMs, { immediate = true } = {}) {
  const cbRef = useRef(callback);
  cbRef.current = callback;

  useEffect(() => {
    if (!delayMs) return undefined;
    let timer = null;
    const tick = () => cbRef.current && cbRef.current();

    const start = () => {
      if (timer != null || document.hidden) return;
      timer = window.setInterval(tick, delayMs);
    };
    const stop = () => {
      if (timer != null) {
        window.clearInterval(timer);
        timer = null;
      }
    };
    const onVisibility = () => {
      if (document.hidden) {
        stop();
      } else {
        tick();   // refresh immediately on return so the gap is closed
        start();
      }
    };

    if (immediate && !document.hidden) tick();
    start();
    document.addEventListener('visibilitychange', onVisibility);
    return () => {
      document.removeEventListener('visibilitychange', onVisibility);
      stop();
    };
  }, [delayMs, immediate]);
}
