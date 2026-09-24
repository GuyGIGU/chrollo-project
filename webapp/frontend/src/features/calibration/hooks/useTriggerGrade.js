import { useCallback, useEffect, useRef, useState } from 'react';
import { API_BASE } from '../../../api/base';

// On-demand engine test for the rail (Task 12): "test this setup" grades a
// ticker's box marks against the engine and streams the priority-ordered result
// (Box/R/S → LPS → Trigger timing). LAZY — nothing computes until the operator
// clicks Test on a row; the grade reuses the SAME memoized fired replay the
// ledger chip uses (one ~1s pass feeds both), and this hook POLLS while the
// backend reports `computing`, then leaves the settled grades in place. Grades
// are keyed by MARK id and merged across tickers, so testing one ticker never
// drops another's result. Every timer is tracked and cleared on unmount so a
// resolved-after-unmount poll can never setState or reschedule.
const POLL_MS = 2000;

export default function useTriggerGrade() {
  const [grades, setGrades] = useState({});   // { <mark_id>: grade }
  const [testing, setTesting] = useState({}); // { <TICKER>: bool } — in-flight
  const timers = useRef(new Map());           // ticker -> timeout id
  const alive = useRef(true);

  useEffect(() => () => {
    alive.current = false;
    for (const id of timers.current.values()) clearTimeout(id);
    timers.current.clear();
  }, []);

  const test = useCallback((ticker) => {
    if (!ticker) return;
    const key = ticker.toUpperCase();
    const existing = timers.current.get(key);
    if (existing) clearTimeout(existing);       // fold a re-test into one poll loop
    setTesting((s) => ({ ...s, [key]: true }));

    const poll = async () => {
      try {
        const params = new URLSearchParams({ ticker: key });
        const res = await fetch(`${API_BASE}/calibration/trigger-grade?${params}`, {
          headers: { 'X-Chrollo-Client': 'chrollo-dashboard' },
        });
        const body = await res.json().catch(() => null);
        if (!alive.current) return;
        if (res.ok && body?.marks) {
          setGrades((g) => ({ ...g, ...body.marks }));
          if (body.computing) {
            timers.current.set(key, setTimeout(poll, POLL_MS)); // still settling
            return;
          }
        }
        timers.current.delete(key);
        setTesting((s) => ({ ...s, [key]: false }));
      } catch (error) {
        if (!alive.current) return;
        console.error('calibration trigger-grade fetch failed:', error);
        timers.current.delete(key);
        setTesting((s) => ({ ...s, [key]: false }));
      }
    };
    poll();
  }, []);

  return { grades, testing, test };
}
