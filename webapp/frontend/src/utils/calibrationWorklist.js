// Worklist parsing for the calibration marking loop (Task 12) — pure.
// The operator pastes entries like "KLAC 2025-09-11", one per line OR
// semicolon-separated (within an entry, ticker and date split on space,
// comma, pipe or tab); junk entries are dropped, duplicates folded, tickers
// case-folded. The queue feeds the mark → save → auto-advance loop.

const LINE_RE = /^([A-Za-z][A-Za-z0-9.-]{0,9})[\s,|]+(\d{4}-\d{2}-\d{2})\s*$/;

export function parseWorklist(text) {
  const items = [];
  const seen = new Set();
  for (const rawLine of String(text || '').split(/[\n;]/)) {
    const m = LINE_RE.exec(rawLine.trim());
    if (!m) continue;
    const ticker = m[1].toUpperCase();
    const key = `${ticker}|${m[2]}`;
    if (seen.has(key)) continue;
    seen.add(key);
    items.push({ ticker, asOf: m[2] });
  }
  return items;
}

export function worklistLabel(items, index) {
  if (!items.length) return '';
  const i = Math.min(Math.max(index, 0), items.length - 1);
  return `${i + 1}/${items.length} · ${items[i].ticker} ${items[i].asOf}`;
}
