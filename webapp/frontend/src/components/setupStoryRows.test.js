import test from 'node:test';
import assert from 'node:assert/strict';
import { lpsGrade, storyRows } from './setupStoryRows.js';
import { SUB_SCORE_CAPS } from './setupScoreMath.js';

// A graded payload as the wire serves it: chapters + engine-resolved fractions.
const GRADED = {
  ta_grade: 74.1,
  ta_grade_chapters: { cause: 14.2, phase_b: 27.91, phase_c: 0.94, phase_d: 23.29, trend: 7.73 },
  ta_grade_chapter_fractions: { cause: 0.5518, phase_b: 0.8678, phase_c: 0.2, phase_d: 0.8296, trend: 0.8256 },
  sub_scores: { lps_tightness: 15 },
};

// buildPhaseRegions' shape, trimmed to what the rows read.
const REGIONS = [
  { key: 'a', label: 'A', name: 'Phase A', detail: 'Initial swing setting support/resistance' },
  { key: 'b', label: 'B', name: 'Phase B', detail: 'Two-sided range work' },
  { key: 'c', label: 'C', name: 'Phase C', detail: 'Undercut and recovery' },
  { key: 'd', label: 'D', name: 'Phase D', detail: 'Sign-of-strength reclaim' },
  { key: 'lps', label: 'LPS', name: 'LPS', detail: 'Active support-test zone', color: '#F6D86B' },
];

const keys = (rows) => rows.map((row) => row.key);

test('the fused list reads left to right like the chart', () => {
  assert.deepEqual(
    keys(storyRows(GRADED, REGIONS)),
    ['a', 'cause', 'phase_b', 'phase_c', 'phase_d', 'lps', 'trend'],
  );
});

test('the LPS lands UNDER Phase D, never as a sixth chapter', () => {
  const rows = storyRows(GRADED, REGIONS);
  const lps = rows[keys(rows).indexOf('phase_d') + 1];
  assert.equal(lps.key, 'lps');
  assert.equal(lps.nested, true);
  // Its points are already inside Phase D's 23.29 — printing them again in the
  // points column would stop the column summing to the grade.
  assert.equal(lps.points, null);
  assert.equal(lps.percent, 75);              // 15 of the cap's 20
  assert.equal(lps.fraction, 15 / SUB_SCORE_CAPS.lps_tightness);
});

test('each chapter lights its own phase, and cause keeps its own words', () => {
  const rows = storyRows(GRADED, REGIONS);
  const row = (key) => rows.find((r) => r.key === key);
  assert.equal(row('phase_b').region, 'b');
  assert.equal(row('phase_c').region, 'c');
  assert.equal(row('phase_d').region, 'd');
  assert.equal(row('lps').region, 'lps');
  // Cause lights the base but grades a different question — it must not borrow
  // Phase B's sentence and print it twice under two names.
  assert.equal(row('cause').region, 'b');
  assert.notEqual(row('cause').detail, row('phase_b').detail);
  // A chapter that IS a phase speaks that phase's MEASURED detail, not a gloss.
  assert.equal(row('phase_c').detail, 'Undercut and recovery');
  assert.equal(row('phase_d').detail, 'Sign-of-strength reclaim');
  // Trend has no span at all.
  assert.equal(row('trend').region, null);
});

test('Phase A shows as an ungraded span, never as a graded zero', () => {
  const a = storyRows(GRADED, REGIONS)[0];
  assert.equal(a.key, 'a');
  assert.equal(a.points, null);
  assert.equal(a.fraction, null);
  assert.equal(a.percent, null);
  assert.equal(a.region, 'a');
});

test('spans with no chapters (an archive row) grade nothing and fabricate nothing', () => {
  const rows = storyRows({ ta_grade: 68 }, REGIONS);
  assert.deepEqual(keys(rows), ['a', 'lps']);
  for (const row of rows) {
    assert.equal(row.points, null);
    assert.equal(row.fraction, null);
  }
});

test('chapters with no spans (a weekly pane) still grade, they just light nothing', () => {
  const rows = storyRows(GRADED, []);
  assert.deepEqual(keys(rows), ['cause', 'phase_b', 'phase_c', 'phase_d', 'trend']);
  assert.equal(rows.every((row) => row.region === null), true);
  assert.equal(rows.find((row) => row.key === 'phase_b').points, 27.91);
  // No LPS span means no LPS row — the grade alone has nothing to point at.
  assert.equal(rows.some((row) => row.key === 'lps'), false);
});

test('an unknown wire chapter falls through verbatim instead of vanishing', () => {
  const rows = storyRows({
    ta_grade: 50,
    ta_grade_chapters: { cause: 10, mystery: 4 },
    ta_grade_chapter_fractions: { cause: 0.4, mystery: 0.5 },
  }, REGIONS);
  const mystery = rows.find((row) => row.key === 'mystery');
  assert.ok(mystery);
  assert.equal(mystery.name, 'mystery');
  assert.equal(mystery.points, 4);
  assert.equal(mystery.region, null);
});

test('an unmeasured LPS term is absent, a measured loose one is a real zero', () => {
  assert.equal(lpsGrade({}), null);
  assert.equal(lpsGrade({ sub_scores: {} }), null);
  assert.equal(lpsGrade({ sub_scores: { lps_tightness: null } }), null);
  assert.equal(lpsGrade({ sub_scores: { lps_tightness: 'n/a' } }), null);
  assert.deepEqual(lpsGrade({ sub_scores: { lps_tightness: 0 } }), { fraction: 0, percent: 0 });
});

test('the LPS grade is clamped to its own cap', () => {
  const cap = SUB_SCORE_CAPS.lps_tightness;
  assert.deepEqual(lpsGrade({ sub_scores: { lps_tightness: cap } }), { fraction: 1, percent: 100 });
  // A cap change that lands before the mirror is updated must not print 140%.
  assert.deepEqual(lpsGrade({ sub_scores: { lps_tightness: cap * 1.4 } }), { fraction: 1, percent: 100 });
  assert.deepEqual(lpsGrade({ sub_scores: { lps_tightness: -3 } }), { fraction: 0, percent: 0 });
});

test('a row with no LPS span still carries the ungraded chapters', () => {
  const noLps = REGIONS.filter((region) => region.key !== 'lps');
  const rows = storyRows(GRADED, noLps);
  assert.equal(rows.some((row) => row.key === 'lps'), false);
  assert.deepEqual(keys(rows), ['a', 'cause', 'phase_b', 'phase_c', 'phase_d', 'trend']);
});
