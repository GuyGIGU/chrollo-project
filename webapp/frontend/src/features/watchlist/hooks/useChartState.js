import { useEffect, useState } from 'react';
import { API_BASE } from '../../../api/base';

// One ticker's chart state off the wire (the final method, points 22 and 24):
// the engine's ONE state word for a chart the scan did not list, read on
// demand from the cached frame — "not scanned" with the door's leg named and
// the distance in ranges, or the lines it found and their facts. Null until
// it arrives; a backend hiccup logs and stays null (the card keeps its bare
// candles), never a fabricated word.
export default function useChartState(ticker, enabled = true) {
  const [state, setState] = useState(null);
  useEffect(() => {
    if (!ticker || !enabled) {
      setState(null);
      return undefined;
    }
    let live = true;
    fetch(`${API_BASE}/screener-data/state/${encodeURIComponent(ticker)}`)
      .then((res) => (res.ok ? res.json() : null))
      .then((body) => { if (live) setState(body); })
      .catch((err) => { console.warn('chart state', ticker, err); });
    return () => { live = false; };
  }, [ticker, enabled]);
  return state;
}
