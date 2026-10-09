import { useEffect, useState } from 'react';
import { API_BASE } from '../../../api/base';
import { entryFor, settledEntry } from '../model/chartStateEntry';

// One ticker's chart state off the wire (the final method, points 22 and 24):
// the engine's ONE state word for a chart the scan did not list, read on
// demand from the cached frame — "not scanned" with the door's leg named and
// the distance in ranges, or the lines it found and their facts. The answer is
// kept WITH the ticker it answers (model/chartStateEntry), so a card handed a
// new ticker shows that ticker loading and never the last one's word; a
// backend hiccup is the failed screen state, logged, never a fabricated word.
// Null while disabled, so the card keeps its own copy.
export default function useChartState(ticker, enabled = true) {
  const [entry, setEntry] = useState(null);
  useEffect(() => {
    if (!ticker || !enabled) return undefined;
    let live = true;
    fetch(`${API_BASE}/screener-data/state/${encodeURIComponent(ticker)}`)
      .then((res) => (res.ok ? res.json() : null))
      .then((body) => { if (live) setEntry(settledEntry(ticker, body)); })
      .catch((err) => {
        console.warn('chart state', ticker, err);
        if (live) setEntry(settledEntry(ticker, null));
      });
    return () => { live = false; };
  }, [ticker, enabled]);
  if (!ticker || !enabled) return null;
  return entryFor(entry, ticker);
}
