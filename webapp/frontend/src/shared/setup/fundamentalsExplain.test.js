import { test } from 'node:test';
import assert from 'node:assert/strict';
import { checkExplain, gradeExplain, labelExplain, lineExplain, sectionExplain } from './fundamentalsExplain.js';

const RULES = {
  letters: [[0.9, 'A'], [0.6, 'B'], [0.4, 'C']],
  min_checks: 6,
  reports: 5,
  beats_min: 4,
  reaction: { ranges: 2.5, volume: 3, adr_days: 15, volume_days: 40 },
  eps_growth_min: 0.3,
  sales_growth_min: 0.2,
  flags: { stock_pay_share: 0.15, one_time_share: 0.33, share_drop: 0.05, acquisition_share: 0.12 },
};
const withRules = { grade: { rules: RULES } };

test('the explanations quote the cut points the grade carried, never their own (EC-28)', () => {
  assert.match(gradeExplain(withRules), /A = 90%\+, B = 60%\+, C = 40%\+, D = less\. Fewer than 6 checks/);
  assert.match(labelExplain(withRules), /EPS up 30%\+ and sales up 20%\+/);
  assert.match(lineExplain('Flags', withRules), /over 15% of sales.*33%\+.*5%\+.*12%\+/);
  const checks = checkExplain(withRules);
  assert.match(checks.eps_steady, /last 5 reports/);
  assert.match(checks.beats, /last 5 reports\. Passes on 4\+ beats/);
  assert.match(checks.reaction, /15-day ADR.*40-day average.*up 2\.5\+ ranges on 3x\+ volume/);
  assert.match(sectionExplain(withRules).reports, /last 5 earnings reports/);
  assert.match(sectionExplain(withRules).quarters, /last 5 fiscal quarters/);
});

test('a sheet from before the rules rode the wire is explained without numbers', () => {
  for (const text of [gradeExplain({}), labelExplain({}), lineExplain('Flags', {})]) {
    assert.doesNotMatch(text, /\d+%/, text);
  }
  const checks = checkExplain({});
  const sections = sectionExplain({});
  for (const text of [checks.eps_steady, checks.beats, checks.reaction, sections.reports, sections.quarters]) {
    assert.doesNotMatch(text, /\d/, text);
  }
});

test('every check the scan grades has its explanation', () => {
  // core/fundamentals/grade.py CHECKS, in order.
  const keys = ['eps_growth', 'eps_accel', 'eps_steady', 'sales_growth', 'margins', 'beats', 'estimates', 'reaction', 'quality'];
  for (const sheet of [withRules, {}]) {
    const checks = checkExplain(sheet);
    for (const key of keys) assert.ok(checks[key], `no explanation for ${key}`);
    assert.deepEqual(Object.keys(checks).sort(), [...keys].sort());
  }
});

test('every line of the read has its explanation', () => {
  for (const k of ['Trend', 'Estimates', 'Quality', 'Flags', 'Code 33']) assert.ok(lineExplain(k, withRules), k);
});
