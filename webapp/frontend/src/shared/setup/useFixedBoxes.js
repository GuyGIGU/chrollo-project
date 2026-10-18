import { useCallback, useEffect, useState } from 'react';
import { API_BASE } from '../../api/base';

// Which charts he has fixed (Sat 18/10/2026, his "add an indicator that this box was edited/fixed"):
// every box fix, loaded once, as a Map of ticker -> the backend's one sentence for its latest fix
// ("fixed 18/10/2026: rails + 2 events: spring, LPS"). The card shows a glyph with that sentence as
// its title; the frontend composes nothing (EC-28). An empty Map is the honest "unknown" when the
// backend lags the frontend (the SPA catch-all answers 200 with HTML, which json() refuses).
export default function useFixedBoxes() {
  const [fixed, setFixed] = useState(() => new Map());

  const refresh = useCallback(() => {
    fetch(`${API_BASE}/calibration/box-fixes`)
      .then((response) => (response.ok ? response.json() : []))
      .then((fixes) => {
        if (!Array.isArray(fixes)) return;
        const latest = new Map();
        for (const fix of [...fixes].sort((a, b) => String(a.scan_day).localeCompare(String(b.scan_day)))) {
          if (fix?.ticker && fix?.summary) latest.set(fix.ticker, fix.summary);
        }
        setFixed(latest);
      })
      .catch(() => {});
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  return { fixed, refresh };
}
