import { useEffect, useMemo, useRef, useState } from 'react';
import { API_BASE } from '../../../api/base';

// Per-mark engine agreement for the ledger "Engine" chip. ONE fetch per ticker
// returns every mark's chip (GET /calibration/agreement?ticker=), so the whole
// ledger lights up from a single call — the column render only READS this map,
// never fetches (the fidelity/replay trap the review flagged).
//
// The fetch is gated on a SIGNATURE of (ticker + each mark's id:revision), not
// the marks array reference (which changes every poll). So it fires when the
// ticker changes or a mark is corrected (revision bumps), and NOT on an
// identity-only refresh. The backend memoizes per (mark id, revision, engine
// manifest) too, so even a refetch only recomputes the mark that actually
// changed. A module-scope cache survives tab hops within a sitting; a request
// generation drops a stale response so the latest ticker always wins.
const cache = new Map(); // signature -> { <mark_id>: chip }

function signatureOf(ticker, marks) {
  if (!ticker || !marks?.length) return null;
  const parts = marks.map((m) => `${m.id}:${m.revision ?? 0}`).sort();
  return `${ticker}|${parts.join(',')}`;
}

export default function useMarkAgreement(ticker, marks) {
  const [agreement, setAgreement] = useState({}); // { <mark_id>: chip }
  const generation = useRef(0);
  const signature = useMemo(() => signatureOf(ticker, marks), [ticker, marks]);

  useEffect(() => {
    // Bump FIRST — before the empty / cache-hit early returns — so switching to
    // a cached (or empty) signature still invalidates an in-flight fetch for the
    // previous ticker; otherwise a slow prior response could overwrite the
    // current ticker's map ("latest ticker always wins").
    const gen = ++generation.current;
    if (!signature) { setAgreement({}); return; }
    const cached = cache.get(signature);
    if (cached) { setAgreement(cached); return; }

    (async () => {
      try {
        const params = new URLSearchParams({ ticker });
        const response = await fetch(`${API_BASE}/calibration/agreement?${params}`, {
          headers: { 'X-Chrollo-Client': 'chrollo-dashboard' },
        });
        const body = await response.json().catch(() => null);
        if (gen !== generation.current) return; // superseded by a newer ticker
        if (response.ok && body?.marks) {
          cache.set(signature, body.marks);
          setAgreement(body.marks);
        }
        // A failure leaves chips absent -> the column renders a neutral dash;
        // the ledger never blocks on the engine read.
      } catch (error) {
        if (gen !== generation.current) return;
        console.error('calibration agreement fetch failed:', error);
      }
    })();
    // ticker is embedded in `signature`; re-run only when the signature moves.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [signature]);

  return agreement;
}
