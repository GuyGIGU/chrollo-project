// THE one score formatter (TA-grade build task 11): absence renders as a
// dash, NEVER 0 — ActionCenter's inline `Math.round(Number(x) || 0)`
// rendered a row's missing score as 0, a lie about the grade. And the two
// score scales are incommensurable: the 0-100 ta_grade must NEVER be
// coalesced with the legacy raw-point score in any column — a row without
// one shows the dash, not the other scale's number.
export function formatScore(value, digits = 0) {
  const n = Number(value);
  if (value == null || !Number.isFinite(n)) return '—';
  return n.toFixed(digits);
}
