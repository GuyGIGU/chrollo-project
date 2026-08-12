import test from 'node:test';
import assert from 'node:assert/strict';
import { lpsGrade, storyRows } from './setupStoryRows.js';
import { SUB_SCORE_CAPS } from './setupScoreMath.js';

// A graded payload as the wire serves it: chapters + engine-resolved fractions.
// Three chapters since the 2026-08-12 re-partition — Cause and Phase B fused to
// `consolidation`, Phase C retired as a chapter and demoted to a mark.
const GRADED = {
  ta_grade: 74.1,
  ta_grade_chapters: { consolidation: 43.05, phase_d: 23.29, trend: 7.73 },
  ta_grade_chapter_fractions: { consolidation: 0.7218, phase_d: 0.8296, trend: 0.8256 },
  sub_scores: { lps_tightness: 15 },
};

// buildPhaseRegions' shape, trimmed to what the rows read.
const REGIONS = [
  { key: 'a', label: 'A', name: 'Phase A', detail: 'Initial swing setting support/resistance' },
  { key: 'b', label: 'B', name: 'Phase B', detail: 'Two-sided range work' },
  { key: 'c', label: 'C', name: 'Phase C', detail: 'Support shakeout or test' },
  { key: 'd', label: 'D', name: 'Phase D', detail: 'Right-side tightening range' },
  { key: 'lps', label: 'LPS', name: 'LPS', detail: 'Last support-test zone', color: '#F6D86B' },
];

const keys = (rows) => rows.map((row) => row.key);
const row = (rows, key) => rows.find((r) => r.key === key);

test('the fused list reads left to right like the chart', () => {
  assert.deepEqual(
    keys(storyRows(GRADED, REGIONS)),
    ['a', 'consolidation', 'c', 'phase_d', 'lps', 'trend'],
  );
});

// The 2026-08-12 ruling: "Phase C also shouldn't be graded… it's more important
// for the engine to FIND Phase C just to put a mark on where the right-most side
// of the consolidation is." A mark with a number would be the ungrading undone.
test('Phase A and Phase C are MARKS — found, placed, never graded', () => {
  const rows = storyRows(GRADED, REGIONS);
  for (const key of ['a', 'c']) {
    const mark = row(rows, key);
    assert.equal(mark.mark, true);
    assert.equal(mark.points, null);
    assert.equal(mark.fraction, null);
    assert.equal(mark.percent, null);
    // It still points at the chart — locating the event is its whole job.
    assert.equal(mark.region, key);
  }
  // ...and no graded chapter is ever a mark.
  for (const key of ['consolidation', 'phase_d', 'trend']) {
    assert.equal(row(rows, key).mark, false);
  }
});

test('a chart with no Phase C simply carries no mark — no absence is typed', () => {
  // 212 of 302 live setups have no spring. The retired chapter printed "Support
  // shakeout or test" on all of them (review 2026-08-12); its replacement must
  // not print "No Phase C on this chart" on all of them either.
  const rows = storyRows(GRADED, REGIONS.filter((r) => r.key !== 'c'));
  assert.deepEqual(keys(rows), ['a', 'consolidation', 'phase_d', 'lps', 'trend']);
  for (const r of rows) assert.ok(!/Phase C/.test(r.detail), `${r.key} mentions Phase C`);
});

test('the LPS lands UNDER Phase D, never as a chapter', () => {
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

test('each chapter carries the hue of the band it lights', () => {
  const rows = storyRows(GRADED, REGIONS);
  // Consolidation grades the base as a whole and lights the box: purple, like
  // the band. Phase D blue. Trend reads around the base and lights nothing.
  assert.equal(row(rows, 'consolidation').phase, 'b');
  assert.equal(row(rows, 'consolidation').region, 'b');
  assert.equal(row(rows, 'phase_d').phase, 'd');
  assert.equal(row(rows, 'trend').phase, null);
  assert.equal(row(rows, 'trend').region, null);
  // Marks wear their own phase.
  assert.equal(row(rows, 'a').phase, 'a');
  assert.equal(row(rows, 'c').phase, 'c');
  assert.equal(row(rows, 'lps').phase, 'lps');
});

test('consolidation speaks what it GRADES, not the B band', () => {
  const rows = storyRows(GRADED, REGIONS);
  const cons = rows.find((r) => r.key === 'consolidation');
  // It lights band B but grades tightness, age, touches, traversal,
  // contraction, the rising floor and the story — "Two-sided range work" would
  // under-describe it by most of its own terms.
  assert.notEqual(cons.detail, 'Two-sided range work');
  assert.match(cons.detail, /base itself/);
  assert.equal(cons.spanState, 'none');
  // A chapter that DOES own its band keeps that band's measured words.
  assert.equal(row(rows, 'phase_d').detail, 'Right-side tightening range');
  assert.equal(row(rows, 'phase_d').spanState, 'measured');
});

test('spans with no chapters (an archive row) grade nothing and fabricate nothing', () => {
  const rows = storyRows({ ta_grade: 68 }, REGIONS);
  assert.deepEqual(keys(rows), ['a', 'c', 'lps']);   // still chart order
  for (const r of rows) {
    assert.equal(r.points, null);
    assert.equal(r.fraction, null);
  }
});

test('chapters with no spans (a weekly pane) still grade, they just light nothing', () => {
  const rows = storyRows(GRADED, []);
  assert.deepEqual(keys(rows), ['consolidation', 'phase_d', 'trend']);
  assert.equal(rows.every((r) => r.region === null), true);
  assert.equal(row(rows, 'phase_d').points, 23.29);
  // No LPS span means no LPS row — the grade alone has nothing to point at.
  assert.equal(rows.some((r) => r.key === 'lps'), false);
});

test('an unknown wire chapter falls through verbatim instead of vanishing', () => {
  const rows = storyRows({
    ta_grade: 50,
    ta_grade_chapters: { consolidation: 10, mystery: 4 },
    ta_grade_chapter_fractions: { consolidation: 0.4, mystery: 0.5 },
  }, REGIONS);
  const mystery = row(rows, 'mystery');
  assert.ok(mystery);
  assert.equal(mystery.name, 'mystery');
  assert.equal(mystery.points, 4);
  assert.equal(mystery.region, null);
  assert.equal(mystery.phase, null);
});

// The 2026-08-12 review's P1, in its surviving form: a chapter that OWNS a band
// must never print the band's event when the engine found no band.
test('a chapter whose band is absent says so, and never prints the event', () => {
  const noD = REGIONS.filter((region) => region.key !== 'd');
  const d = row(storyRows(GRADED, noD), 'phase_d');
  assert.equal(d.spanState, 'absent');
  assert.equal(d.detail, 'No Phase D on this chart');
  assert.ok(!/tightening|reclaim/i.test(d.detail));
  // The grade is still real and still shown — absence of the BAND is not
  // absence of the chapter's points.
  assert.equal(d.points, 23.29);
  assert.equal(d.fraction, 0.8296);
  assert.equal(d.region, null);
  // ...and the row can still say what earned those points, without an event.
  assert.match(d.grades, /LPS, volume dry-up, the squeeze/);
  // The colour is the phase's identity, not the band's presence.
  assert.equal(d.phase, 'd');
});

test('where no band was READ, absence is not reported either', () => {
  // A weekly pane passes no regions. "No Phase D on this chart" would be the
  // same lie pointing the other way — nobody looked for a daily band there.
  for (const r of storyRows(GRADED, [])) {
    assert.equal(r.spanState, 'none');
    assert.ok(!/^No /.test(r.detail), `${r.key} reported an absence nobody measured`);
  }
  const d = row(storyRows(GRADED, []), 'phase_d');
  assert.match(d.detail, /LPS, volume dry-up, the squeeze/);
});

test('the span-less chapters are "none", never "absent"', () => {
  const rows = storyRows(GRADED, REGIONS);
  assert.equal(row(rows, 'consolidation').spanState, 'none');
  assert.equal(row(rows, 'trend').spanState, 'none');
  // An unknown wire chapter owns no band either.
  const odd = row(storyRows({
    ta_grade: 50,
    ta_grade_chapters: { mystery: 4 },
    ta_grade_chapter_fractions: { mystery: 0.5 },
  }, REGIONS), 'mystery');
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

test('a row with no LPS span still carries the marks and the chapters', () => {
  const noLps = REGIONS.filter((region) => region.key !== 'lps');
  const rows = storyRows(GRADED, noLps);
  assert.equal(rows.some((r) => r.key === 'lps'), false);
  assert.deepEqual(keys(rows), ['a', 'consolidation', 'c', 'phase_d', 'trend']);
});
