// The app's ONE null guard for rendered numbers, plus the shared formatter
// family built on it. The surface dialects (tradeTableUtils, tradeDetailFormat,
// archiveTabUtils, marketRegimeFormat, homeFormat, portfolioFormat) compose
// these primitives instead of re-implementing the guard, so a null/NaN can
// never crash one surface's private variant.
//
// Guard semantics (kept compatible with the copies this folds): value == null
// OR Number(value) non-finite -> the empty glyph. Note '' coerces to 0
// (Number('') === 0), matching every prior dialect. The canonical empty glyph
// is the em dash; surfaces with deliberate copy ('n/a' in regime prose, '0.00'
// on the dashboard zeros, null for caller-owned fallbacks) pass their own.

export const EMPTY = '—'; // —

// The canonical guard: a finite number, or null.
export const finiteOrNull = (value) =>
  value == null || !Number.isFinite(Number(value)) ? null : Number(value);

// Total-order comparators that never return NaN — a NaN comparator leaves
// Array.sort order unspecified (the flicker the dense ledgers avoid). A missing
// number coalesces to -Infinity so it stays ORDERED (sinks under asc); strings
// compare via localeCompare on '' (ISO dates sort chronologically under it).
// One home shared by watchlistTable + calibrationTables (EC-3 — no forked twin).
export const numAsc = (a, b) => {
  const na = a == null ? -Infinity : a;
  const nb = b == null ? -Infinity : b;
  return na < nb ? -1 : na > nb ? 1 : 0;
};
export const strAsc = (a, b) => String(a ?? '').localeCompare(String(b ?? ''));

// Fixed-decimal (the house `fx` guard).
export const fx = (value, digits = 2, empty = EMPTY) => {
  const n = finiteOrNull(value);
  return n == null ? empty : n.toFixed(digits);
};

// Locale-grouped fixed-decimal (money amounts, share counts).
export const fmtNum = (value, digits = 2, empty = EMPTY) => {
  const n = finiteOrNull(value);
  if (n == null) return empty;
  return n.toLocaleString('en-US', { minimumFractionDigits: digits, maximumFractionDigits: digits });
};

// Locale-grouped whole number.
export const fmtInt = (value, empty = EMPTY) => {
  const n = finiteOrNull(value);
  if (n == null) return empty;
  return n.toLocaleString('en-US', { maximumFractionDigits: 0 });
};

// Signed dollar amount with an optional non-USD suffix (portfolio dialect).
export const fmtMoneyUsd = (value, currency = 'USD', empty = EMPTY) => {
  const n = finiteOrNull(value);
  if (n == null) return empty;
  const sign = n < 0 ? '-' : '';
  const abs = Math.abs(n).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  return `${sign}$${abs}${currency && currency !== 'USD' ? ` ${currency}` : ''}`;
};

// Percent where the value is ALREADY in percent units (12.3 -> "12.3%").
export const fmtPct = (value, digits = 1, empty = EMPTY) => {
  const n = finiteOrNull(value);
  if (n == null) return empty;
  return `${n.toLocaleString('en-US', { minimumFractionDigits: digits, maximumFractionDigits: digits })}%`;
};

// Percent where the value is a FRACTION (0.0728 -> "7.28%").
export const fmtPctFrac = (value, digits = 1, empty = EMPTY) => {
  const n = finiteOrNull(value);
  return n == null ? empty : `${(n * 100).toFixed(digits)}%`;
};

// Signed fraction percent ("+7.3%" / "−2.1%", typographic minus).
export const fmtSignedPctFrac = (value, digits = 1, empty = EMPTY) => {
  const n = finiteOrNull(value);
  if (n == null) return empty;
  const v = n * 100;
  return `${v >= 0 ? '+' : '−'}${Math.abs(v).toFixed(digits)}%`;
};

// Whole-number string, no grouping (regime counts).
export const fmtRound = (value, empty = EMPTY) => {
  const n = finiteOrNull(value);
  return n == null ? empty : String(Math.round(n));
};

// Short "Mon D, HH:MM" date-time, or null when unparseable — callers own their
// fallback glyph ('none' on the topbar, 'n/a' in regime rows, raw passthrough).
export const dateTimeShort = (value) => {
  const dt = new Date(value);
  if (Number.isNaN(dt.getTime())) return null;
  return dt.toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
};

// "Jan 5" from an ISO-date-prefixed string; non-date strings pass through.
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
export const fmtDateShort = (value, empty = EMPTY) => {
  if (!value) return empty;
  const match = String(value).match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (!match) return value;
  return `${MONTHS[Number(match[2]) - 1]} ${Number(match[3])}`;
};
