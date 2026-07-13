import { useEffect, useRef, useState } from 'react';
import { API_BASE } from '../api';

// The downsampled preview for ONE frozen frame's ledger thumbnail. Keyed on the
// content digest ALONE (pure price geometry — a restatement is a new digest, so
// the cache invalidates by construction; the same frame across rows shares one
// fetch). A module-scope cache + in-flight dedupe means dozens of thumbnails on
// screen never re-read a parquet, and never fetch inside a render (the fidelity
// trap the watchlist sparkline was cut for — here the backend pre-downsamples).
const cache = new Map();    // frame_digest -> preview { series, lo, hi, n }
const inflight = new Map(); // frame_digest -> pending promise

async function fetchThumb(ticker, asOf, digest) {
  const params = new URLSearchParams({ ticker, as_of: asOf, frame_digest: digest });
  const response = await fetch(`${API_BASE}/calibration/frame-thumb?${params}`, {
    headers: { 'X-Chrollo-Client': 'chrollo-dashboard' },
  });
  const body = await response.json().catch(() => null);
  return response.ok && Array.isArray(body?.series) ? body : null;
}

export default function useFrameThumb(ticker, asOf, digest) {
  const [preview, setPreview] = useState(() => (digest ? cache.get(digest) : null) ?? null);
  const generation = useRef(0);

  useEffect(() => {
    // Bump FIRST — before the early returns — so a coverage row whose digest
    // reverts to a cached one (e.g. its newest mark was deleted) still drops any
    // in-flight fetch for the superseded digest; otherwise a slow prior response
    // could draw one frame's price line under another mark's box overlay.
    const gen = ++generation.current;
    if (!ticker || !asOf || !digest) { setPreview(null); return; }
    const cached = cache.get(digest);
    if (cached) { setPreview(cached); return; }

    let pending = inflight.get(digest);
    if (!pending) {
      pending = fetchThumb(ticker, asOf, digest).finally(() => inflight.delete(digest));
      inflight.set(digest, pending);
    }
    pending
      .then((result) => {
        if (gen !== generation.current) return; // superseded (row reused for another mark)
        if (result) { cache.set(digest, result); setPreview(result); }
      })
      .catch((error) => {
        if (gen !== generation.current) return;
        console.error('calibration frame-thumb fetch failed:', error);
      });
  }, [ticker, asOf, digest]);

  return preview;
}
