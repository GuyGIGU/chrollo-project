import { useEffect, useMemo, useRef, useState } from 'react';
import { API_BASE } from '../api';

// Per-mark FIRED grade for the ledger chip — the sharper "pops-up-live" verdict.
// The backend runs the full scoring pipeline per box mark (slow), so it answers
// with cached chips + 'pending' for the rest and a `computing` flag; this hook
// POLLS until it settles, then caches the settled map. Gated on the same
// (ticker + id:revision) signature as the agreement hook, so a correction
// re-grades but a re-render never re-fetches. The generation ref is bumped
// FIRST (before the early returns) and the poll timer is cleared on every dep
// change / unmount, so a superseded ticker can never write or keep polling.
// signature -> { policy, marks } (settled). Entries are served instantly but
// ALWAYS revalidated once per mount: the grading policy/engine can change
// under an open tab (service restart mid lever-program), and a chip graded
// under a previous policy must never keep rendering as current.
const cache = new Map();
const POLL_MS = 2000;

function signatureOf(ticker, marks) {
  if (!ticker || !marks?.length) return null;
  const parts = marks.map((m) => `${m.id}:${m.revision ?? 0}`).sort();
  return `${ticker}|${parts.join(',')}`;
}

export default function useMarkFired(ticker, marks) {
  const [fired, setFired] = useState({}); // { <mark_id>: chip }
  const generation = useRef(0);
  const timer = useRef(null);
  const signature = useMemo(() => signatureOf(ticker, marks), [ticker, marks]);

  useEffect(() => {
    const gen = ++generation.current;               // invalidate any in-flight poll
    if (timer.current) { clearTimeout(timer.current); timer.current = null; }
    if (!signature) { setFired({}); return undefined; }
    const cached = cache.get(signature);
    if (cached) setFired(cached.marks); // instant paint; still revalidate below

    const poll = async () => {
      try {
        const params = new URLSearchParams({ ticker });
        const response = await fetch(`${API_BASE}/calibration/fired?${params}`, {
          headers: { 'X-Chrollo-Client': 'chrollo-dashboard' },
        });
        const body = await response.json().catch(() => null);
        if (gen !== generation.current) return;     // superseded by a newer ticker
        if (response.ok && body?.marks) {
          setFired(body.marks);
          if (body.computing) {
            timer.current = setTimeout(poll, POLL_MS); // keep polling until settled
          } else {
            // settled -> cache, keyed with the served grading-policy token so
            // a policy/engine change on the server replaces the entry rather
            // than being masked by it
            cache.set(signature, { policy: body.policy ?? null, marks: body.marks });
          }
        }
        // a failure just stops the poll; the Engine column falls back to concordance
      } catch (error) {
        if (gen !== generation.current) return;
        console.error('calibration fired fetch failed:', error);
      }
    };
    poll();
    return () => {
      // Bump the generation so an in-flight poll that resolves AFTER unmount
      // trips its own `gen !== generation.current` guard — otherwise it would
      // setState + reschedule a setTimeout that no cleanup can ever clear (a
      // self-perpetuating orphaned poll). Clearing the timer alone is not
      // enough: at unmount the timer may be null because a fetch is mid-flight.
      generation.current += 1;
      if (timer.current) { clearTimeout(timer.current); timer.current = null; }
    };
    // ticker is embedded in `signature`; re-run only when the signature moves.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [signature]);

  return fired;
}
