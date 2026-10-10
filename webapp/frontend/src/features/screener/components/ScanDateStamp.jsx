import { useState } from 'react';
import usePollingInterval from '../../../shared/hooks/usePollingInterval';
import { buildScanDateStamp } from '../presentation/scanDateStamp';

// The minute tick only re-renders this chip, so a tab left open turns amber once the
// payload's stale_after passes (not at midnight); usePollingInterval pauses while hidden
// and ticks on return. It fetches nothing.
function ScanDateStamp({ screenerData }) {
  const [now, setNow] = useState(() => new Date());
  usePollingInterval(() => setNow(new Date()), 60000, { immediate: false });
  const stamp = buildScanDateStamp(screenerData, now);
  if (!stamp) return null;
  return (
    <span className={`screener-scan-date${stamp.stale ? ' is-stale' : ''}`} title={stamp.title}>
      {stamp.text}
    </span>
  );
}

export default ScanDateStamp;
