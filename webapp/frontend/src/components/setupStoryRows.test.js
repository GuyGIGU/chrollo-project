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

// The 2026-08-12 review's P1: on 212 of 302 live setups the engine detects NO
// Phase C, and the row printed "Support shakeout or test" anyway — the same
// words the 16 real ones use, with a full bar and a real grade beside them.
test('a chapter whose band is absent says so, and never prints the event', () => {
  const noSpring = REGIONS.filter((region) => region.key !== 'c');
  const c = storyRows(GRADED, noSpring).find((row) => row.key === 'phase_c');
  assert.equal(c.spanState, 'absent');
  assert.equal(c.detail, 'No Phase C on this chart');
  assert.ok(!/shakeout|undercut|spring below/i.test(c.detail));
  // The grade is still real and still shown — absence of the BAND is not
  // absence of the chapter's points.
  assert.equal(c.points, 0.94);
  assert.equal(c.fraction, 0.2);
  assert.equal(c.region, null);
  // ...and the row can still say what earned those points, without an event.
  assert.match(c.grades, /spring below support, or rising support/);
});

// The token chip is coloured by this, and the colour is what ties a row to its
// band on the chart. Keyed off the chapter key it emitted `phase-bin-phase_b`
// against a stylesheet defining only `.phase-bin-b`, so the three middle phases
// rendered uncoloured (review 2026-08-12).
test('every phase row carries the phase key the token colours are defined on', () => {
  const rows = storyRows(GRADED, REGIONS);
  const phase = (key) => rows.find((row) => row.key === key).phase;
  assert.equal(phase('a'), 'a');
  assert.equal(phase('phase_b'), 'b');
  assert.equal(phase('phase_c'), 'c');
  assert.equal(phase('phase_d'), 'd');
  assert.equal(phase('lps'), 'lps');
  // Not phases, so no phase tint — Cause and Trend are chapters only.
  assert.equal(phase('cause'), null);
  assert.equal(phase('trend'), null);
});

test('a phase keeps its colour even when its band is absent', () => {
  const c = storyRows(GRADED, REGIONS.filter((r) => r.key !== 'c'))
    .find((row) => row.key === 'phase_c');
  assert.equal(c.phase, 'c');   // pink is Phase C's identity, not the band's
  assert.equal(c.region, null); // ...but there is still nothing to light
});

test('a measured band keeps its own measured words', () => {
  const c = storyRows(GRADED, REGIONS).find((row) => row.key === 'phase_c');
  assert.equal(c.spanState, 'measured');
  assert.equal(c.detail, 'Undercut and recovery');
  assert.equal(c.region, 'c');
});

test('where no band was READ, absence is not reported either', () => {
  // A weekly pane passes no regions. "No Phase B on this chart" would be the
  // same lie pointing the other way — nobody looked for a daily band there.
  for (const row of storyRows(GRADED, [])) {
    assert.equal(row.spanState, 'none');
    assert.ok(!/^No /.test(row.detail), `${row.key} reported an absence nobody measured`);
  }
  const b = storyRows(GRADED, []).find((row) => row.key === 'phase_b');
  assert.match(b.detail, /touches, traversal, contraction/);
});

test('the two span-less chapters are "none", never "absent"', () => {
  const rows = storyRows(GRADED, REGIONS);
  assert.equal(rows.find((r) => r.key === 'cause').spanState, 'none');
  assert.equal(rows.find((r) => r.key === 'trend').spanState, 'none');
  // An unknown wire chapter owns no band either.
  const odd = storyRows({
    ta_grade: 50,
    ta_grade_chapters: { mystery: 4 },
    ta_grade_chapter_fractions: { mystery: 0.5 },
  }, REGIONS).find((r) => r.key === 'mystery');
  assert.equal(odd.spanState, 'none');
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
