import { useEffect, useRef, useState } from 'react';
import { API_BASE } from '../../../api/base';
import { frameKeyOf } from '../model/calibrationMarking';

// The engine's read of the loaded frozen frame (operator ask 2026-07-11:
// "no option to see what the engine thinks"). Fetches only while the toggle
// is ON — the overlay is default-OFF by design: the operator marks FIRST,
// peeks after (anchoring on the engine's read corrupts the ground truth).
// Cached per frame identity for the sitting: one structure read per frame,
// module scope on purpose (single-operator localhost, survives tab hops).
const engineReadCache = new Map(); // frameKey -> engine-read payload

export default function useEngineRead(chartData, enabled) {
  const [read, setRead] = useState(null);   // payload | null
  const [status, setStatus] = useState(null); // 'loading' | failure text | null
  const generation = useRef(0);

  useEffect(() => {
    generation.current += 1; // any change invalidates an in-flight response
    if (!enabled || !chartData) {
      setRead(null);
      setStatus(null);
      return;
    }
    const key = frameKeyOf(chartData);
    if (engineReadCache.has(key)) {
      setRead(engineReadCache.get(key));
      setStatus(null);
      return;
    }
    const gen = generation.current;
    setRead(null);
    setStatus('loading');
    const params = new URLSearchParams({
      ticker: chartData.ticker,
      as_of: chartData.as_of_session,
      frame_digest: chartData.frame_digest,
    });
    fetch(`${API_BASE}/calibration/engine-read?${params}`, {
      headers: { 'X-Chrollo-Client': 'chrollo-dashboard' },
    })
      .then(async (response) => {
        const body = await response.json().catch(() => null);
        if (gen !== generation.current) return; // a newer frame took over
        if (!response.ok || typeof body?.elected !== 'boolean') {
          // Named backend class when there is one; the catch-all covers the
          // old service answering unknown API paths (or plain 404).
          setStatus(body?.detail?.message
            ?? 'engine read unavailable — run update_dashboard.bat to load the new backend');
          return;
        }
        engineReadCache.set(key, body);
        setRead(body);
        setStatus(null);
      })
      .catch((error) => {
        console.error('calibration engine read failed:', error);
        if (gen === generation.current) {
          setStatus('engine read failed — backend unreachable');
        }
      });
  }, [chartData, enabled]);

  return { engineRead: read, engineStatus: status };
}
