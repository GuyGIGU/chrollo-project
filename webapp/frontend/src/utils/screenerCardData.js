// Shared read-helpers for the screener card + the click-through detail lens, so
// the two surfaces derive the same daily change, as-of date, and weekly/monthly
// state from one place (EC-3: fold twin logic, never copy it).
import { finiteOrNull, fmtDateShort, EMPTY } from './format.js';

// Daily % change as a FRACTION from the last two closes of a candle series. The
// engine payload carries no 1-day change, but the mini-chart candles do. Null-
// safe: needs two finite closes and a non-zero base, else null → caller shows —.
export const dailyChangeFrac = (candles) => {
  if (!Array.isArray(candles) || candles.length < 2) return null;
  const last = finiteOrNull(candles[candles.length - 1]?.close);
  const prev = finiteOrNull(candles[candles.length - 2]?.close);
  if (last == null || prev == null || prev === 0) return null;
  return (last - prev) / prev;
};

// As-of date = the last candle's date (YYYY-MM-DD → "Jul 8").
export const asOfDate = (candles) => fmtDateShort(candles?.[candles.length - 1]?.time, EMPTY);

// One timeframe's structural state → { label, tone }, from the engine's
// htf_{w,m}_* fields. Re-accumulation is the premium case (S-tier amber); a
// worked box in progress is context blue; a bare Stage-2 uptrend is green.
export function htfStateLabel({ stage2, trendState, inConsol, phase, reaccum }) {
  if (reaccum) return { label: `Re-accum${phase ? ` ${phase}` : ''}`, tone: 'var(--tier-s)' };
  if (inConsol) return { label: `Consol${phase ? ` ${phase}` : ''}`, tone: 'var(--tier-b)' };
  if (stage2) return { label: 'Uptrend', tone: 'var(--success)' };
  if (trendState == null || trendState === 'unknown') return { label: 'no data', tone: 'var(--text-faint)' };
  if (trendState === 'down') return { label: 'downtrend', tone: 'var(--danger)' };
  return { label: '—', tone: 'var(--text-faint)' };
}

// The trend arrow (symbol + color) for a timeframe's trend state.
export const htfTrendArrow = (trendState) => (
  trendState === 'up' ? { sym: '▲', col: 'var(--success)' }
    : trendState === 'down' ? { sym: '▼', col: 'var(--danger)' }
      : trendState === 'neutral' ? { sym: '▬', col: '#8b949e' }
        : { sym: '·', col: 'var(--text-faint)' }
);
