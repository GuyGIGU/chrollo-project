import { test } from 'node:test';
import assert from 'node:assert/strict';
import { CHECK_EXPLAIN, gradeExplain, labelExplain, lineExplain } from './fundamentalsExplain.js';

const RULES = {
  letters: [[0.9, 'A'], [0.6, 'B'], [0.4, 'C']],
  min_checks: 6,
  eps_growth_min: 0.3,
  sales_growth_min: 0.2,
  flags: { stock_pay_share: 0.15, one_time_share: 0.33, share_drop: 0.05, acquisition_share: 0.12 },
};
const withRules = { grade: { rules: RULES } };

test('the explanations quote the cut points the grade carried, never their own (EC-28)', () => {
  assert.match(gradeExplain(withRules), /A = 90%\+, B = 60%\+, C = 40%\+, D = less\. Fewer than 6 checks/);
  assert.match(labelExplain(withRules), /EPS up 30%\+ and sales up 20%\+/);
  assert.match(lineExplain('Flags', withRules), /over 15% of sales.*33%\+.*5%\+.*12%\+/);
});

test('a sheet from before the rules rode the wire is explained without numbers', () => {
  for (const text of [gradeExplain({}), labelExplain({}), lineExplain('Flags', {})]) {
    assert.doesNotMatch(text, /\d+%/, text);
  }
});

test('every check the scan grades has its explanation', () => {
  // core/fundamentals/grade.py CHECKS, in order.
  const keys = ['eps_growth', 'eps_accel', 'eps_steady', 'sales_growth', 'margins', 'beats', 'estimates', 'reaction', 'quality'];
  for (const key of keys) assert.ok(CHECK_EXPLAIN[key], `no explanation for ${key}`);
  assert.deepEqual(Object.keys(CHECK_EXPLAIN).sort(), [...keys].sort());
});

test('every line of the read has its explanation', () => {
  for (const k of ['Trend', 'Estimates', 'Quality', 'Flags', 'Code 33']) assert.ok(lineExplain(k, withRules), k);
});
