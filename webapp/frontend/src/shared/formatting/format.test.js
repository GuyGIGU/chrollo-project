import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  EMPTY,
  finiteOrNull,
  fx,
  fmtNum,
  fmtInt,
  fmtMoneyUsd,
  fmtPct,
  fmtPctFrac,
  fmtSignedPctFrac,
  fmtRound,
  dateTimeShort,
  fmtDateShort,
  fmtDay,
} from './format.js';

test('finiteOrNull: the one guard — null/undefined/NaN/Infinity -> null', () => {
  assert.equal(finiteOrNull(null), null);
  assert.equal(finiteOrNull(undefined), null);
  assert.equal(finiteOrNull(NaN), null);
  assert.equal(finiteOrNull(Infinity), null);
  assert.equal(finiteOrNull('abc'), null);
  assert.equal(finiteOrNull(0), 0); // 0 is a value, not a hole
  assert.equal(finiteOrNull('12.5'), 12.5); // numeric strings coerce
  assert.equal(finiteOrNull(''), 0); // '' coerces to 0 (legacy dialect behavior, kept)
});

test('fx: fixed decimals with the canonical empty glyph', () => {
  assert.equal(fx(null), EMPTY);
  assert.equal(fx(undefined, 2), EMPTY);
  assert.equal(fx('x', 2), EMPTY);
  assert.equal(fx(1.005, 1), '1.0');
  assert.equal(fx(2, 3), '2.000');
  assert.equal(fx(null, 2, '0.00'), '0.00'); // dashboard zero-copy override
});

test('fmtNum / fmtInt: locale-grouped, guarded', () => {
  assert.equal(fmtNum(null), EMPTY);
  assert.equal(fmtNum(1234.5), '1,234.50');
  assert.equal(fmtNum(1234.567, 1), '1,234.6');
  assert.equal(fmtInt(null), EMPTY);
  assert.equal(fmtInt(12345.6), '12,346');
});

test('fmtMoneyUsd: sign placement and currency suffix', () => {
  assert.equal(fmtMoneyUsd(null), EMPTY);
  assert.equal(fmtMoneyUsd(1234.5), '$1,234.50');
  assert.equal(fmtMoneyUsd(-1234.5), '-$1,234.50'); // sign OUTSIDE the $
  assert.equal(fmtMoneyUsd(10, 'CAD'), '$10.00 CAD');
  assert.equal(fmtMoneyUsd(10, 'USD'), '$10.00'); // USD suffix suppressed
});

test('fmtPct: value already in percent units (no multiply)', () => {
  assert.equal(fmtPct(null), EMPTY);
  assert.equal(fmtPct(12.34), '12.3%');
  assert.equal(fmtPct(12.34, 2), '12.34%');
});

test('fmtPctFrac: fraction in, percent out (multiply)', () => {
  assert.equal(fmtPctFrac(null), EMPTY);
  assert.equal(fmtPctFrac(0.0728, 2), '7.28%');
  assert.equal(fmtPctFrac(0.0728, 0), '7%');
  assert.equal(fmtPctFrac(null, 1, 'n/a'), 'n/a'); // regime glyph override
  assert.equal(fmtPctFrac(null, 1, null), null); // home caller-owned fallback
});

test('fmtSignedPctFrac: explicit +, typographic minus', () => {
  assert.equal(fmtSignedPctFrac(null), EMPTY);
  assert.equal(fmtSignedPctFrac(0.05), '+5.0%');
  assert.equal(fmtSignedPctFrac(-0.021), '−2.1%'); // U+2212, not hyphen
  assert.equal(fmtSignedPctFrac(0), '+0.0%');
});

test('fmtRound: whole-number string', () => {
  assert.equal(fmtRound(null), EMPTY);
  assert.equal(fmtRound(6.6), '7');
  assert.equal(fmtRound(null, 'n/a'), 'n/a');
});

test('dateTimeShort: formatted or null (callers own the fallback)', () => {
  assert.equal(dateTimeShort('not-a-date'), null);
  const out = dateTimeShort('2026-07-03T12:30:00Z');
  assert.equal(typeof out, 'string');
  assert.ok(out.length > 0);
});

test('fmtDateShort: ISO prefix -> "Mon D", non-dates pass through', () => {
  assert.equal(fmtDateShort(null), EMPTY);
  assert.equal(fmtDateShort('2026-07-03'), 'Jul 3');
  assert.equal(fmtDateShort('2026-01-09T10:00:00'), 'Jan 9');
  assert.equal(fmtDateShort('pending'), 'pending');
});

test('fmtDay: the operator date, weekday dd/mm/yyyy, read in UTC', () => {
  assert.equal(fmtDay('2026-02-11'), 'Wed 11/02/2026');
  assert.equal(fmtDay('2026-02-12T21:00:00'), 'Thu 12/02/2026');
  assert.equal(fmtDay('2026-09-19'), 'Sat 19/09/2026');
  assert.equal(fmtDay(null), EMPTY);
  assert.equal(fmtDay('pending'), 'pending');
});
