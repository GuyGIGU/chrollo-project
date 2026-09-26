import { useEffect, useRef, useState } from 'react';

/**
 * Subscribe to a Server-Sent Events endpoint and expose the last parsed JSON payload.
 *
 * Resilience features:
 * - Preserves last-known data across reconnects (no flash of empty state).
 * - Distinguishes between transient errors (EventSource auto-retrying) and
 *   permanent failures (EventSource gave up).
 * - Pauses the connection when the browser tab is hidden to save resources.
 * - Manual reconnect with backoff if EventSource gives up entirely.
 * - Accepts a synchronous onMessage callback for side effects.
 */
export default function useSSE(url, { onMessage, enabled = true } = {}) {
  const [data, setData] = useState(null);
  const [status, setStatus] = useState('idle'); // 'idle' | 'open' | 'reconnecting' | 'error' | 'closed'
  const onMessageRef = useRef(onMessage);
  const retryTimerRef = useRef(null);
  const esRef = useRef(null);
  onMessageRef.current = onMessage;

  useEffect(() => {
    if (!enabled || !url) {
      setStatus('idle');
      return;
    }

    let retryCount = 0;
    const maxRetryDelay = 15000;

    const connect = () => {
      if (document.hidden) {
        setStatus('closed');
        return;
      }

      // Clear any pending retry
      if (retryTimerRef.current) {
        clearTimeout(retryTimerRef.current);
        retryTimerRef.current = null;
      }

      try {
        const es = new EventSource(url);
        esRef.current = es;

        es.onopen = () => {
          retryCount = 0;
          setStatus('open');
        };

        es.onerror = () => {
          // EventSource auto-reconnects when readyState is CONNECTING.
          // Only flag as 'error' when it has fully given up (CLOSED).
          if (es.readyState === EventSource.CLOSED) {
            setStatus('error');
            esRef.current = null;
            // Manual reconnect with exponential backoff
            const delay = Math.min(1000 * Math.pow(2, retryCount), maxRetryDelay);
            retryCount++;
            retryTimerRef.current = setTimeout(connect, delay);
          } else {
            // CONNECTING — auto-retrying; show softer status
            setStatus('reconnecting');
          }
        };

        es.onmessage = (ev) => {
          if (!ev.data) return;
          // Skip comment-only keep-alives (they start with ':')
          if (ev.data.startsWith(':')) return;
          let parsed;
          try { parsed = JSON.parse(ev.data); }
          catch { parsed = ev.data; }
          // Always update data — never reset to null on reconnect
          setData(parsed);
          if (onMessageRef.current) onMessageRef.current(parsed);
        };
      } catch {
        setStatus('error');
        const delay = Math.min(1000 * Math.pow(2, retryCount), maxRetryDelay);
        retryCount++;
        retryTimerRef.current = setTimeout(connect, delay);
      }
    };

    const disconnect = () => {
      if (retryTimerRef.current) {
        clearTimeout(retryTimerRef.current);
        retryTimerRef.current = null;
      }
      if (esRef.current) {
        esRef.current.close();
        esRef.current = null;
      }
      setStatus('closed');
    };

    connect();

    const visibilityHandler = () => {
      if (document.hidden) {
        disconnect();
      } else if (!esRef.current) {
        connect();
      }
    };
    document.addEventListener('visibilitychange', visibilityHandler);

    return () => {
      document.removeEventListener('visibilitychange', visibilityHandler);
      disconnect();
    };
  }, [url, enabled]);

  return { data, status };
}
