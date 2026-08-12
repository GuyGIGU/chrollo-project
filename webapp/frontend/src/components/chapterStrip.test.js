// The chapter strip's presentation contract (TA-grade build task 12).
import test from 'node:test';
import assert from 'node:assert/strict';
import { CHAPTER_REGION, chapterCells, warningItems } from './chapterStrip.js';

const GRADED = {
  ta_grade: 61.2,
  ta_grade_chapters: {
    cause: 18.2, phase_b: 21.0, phase_c: 2.1, phase_d: 14.9, trend: 5.0,
  },
  ta_grade_chapter_fractions: {
    cause: 0.66, phase_b: 0.55, phase_c: 0.26, phase_d: 0.62, trend: 0.31,
  },
  // A carried, measured story family (READY): counts present and non-zero.
  event_map_completed_s: 3,
  event_map_completed_r: 2,
  event_map_alternations: 2,
  event_map_terminal_posture: 1,
  event_map_terminal_drift: 0,
  event_map_story_admitted: 0,
  event_map_episode_nan_bars: 0,
  event_map_n_swings: 9,
  event_map_n_labels: 5,
  event_map_n_committed: 5,
  event_map_pre_box_trend: 'up',
  event_map_episode_profile: 'S+ S+ S+',
  event_map_episodes: [],
};

test('graded payload yields the five ruled chapters, in story order', () => {
  const cells = chapterCells(GRADED);
  assert.deepEqual(cells.map(c => c.key),
    ['cause', 'phase_b', 'phase_c', 'phase_d', 'trend']);
  assert.equal(cells[0].points, 18.2);
  assert.equal(cells[0].fraction, 0.66);
  assert.equal(cells.every(c => c.fraction >= 0 && c.fraction <= 1), true);
  // A clean measured story: no honesty caveat on the story chapters.
  assert.equal(cells[1].subtext, null);
  assert.equal(cells[3].subtext, null);
});

test('ungraded payload renders no strip at all', () => {
  assert.deepEqual(chapterCells({ ta_grade: null }), []);
  assert.deepEqual(chapterCells({}), []);
  assert.deepEqual(chapterCells(null), []);
});

test('graded payload WITHOUT chapters renders no strip — never five fabricated 0.0 cells', () => {
  // The SetupOut shape (2026-08-08 review, finding 12): the archive serves
  // ta_grade + fired_tags but no resolved chapters; the old mirror
  // iteration rendered confident measured zeros over it.
  assert.deepEqual(chapterCells({ ta_grade: 61.2, fired_tags: [] }), []);
});

test('unknown wire chapters render verbatim; non-finite points read as a dash, not 0.0', () => {
  const cells = chapterCells({
    ...GRADED,
    ta_grade_chapters: { ...GRADED.ta_grade_chapters, mystery: 'wat' },
  });
  const mystery = cells.find(c => c.key === 'mystery');
  assert.equal(mystery.label, 'mystery');       // visible fallthrough
  assert.equal(mystery.points, null);           // dash downstream, never 0.0
});

test('NOT_CARRIED renders NO subtext — the "predates the read" copy is reserved for wire-carried nulls', () => {
  // A wire that does not carry the family at all (no event_map_* keys):
  // narrativeRead's own law says nothing honest can be said (council F4).
  const notCarried = { ...GRADED };
  Object.keys(notCarried).forEach((k) => {
    if (k.startsWith('event_map_')) delete notCarried[k];
  });
  const phaseB = chapterCells(notCarried).find(c => c.key === 'phase_b');
  assert.equal(phaseB.subtext, null);
});

test('story chapters carry the not-measured honesty wording', () => {
  const preEventMap = {
    ...GRADED,
    event_map_completed_s: null, event_map_completed_r: null,
    event_map_alternations: null, event_map_terminal_posture: null,
    event_map_terminal_drift: null, event_map_story_admitted: null,
    event_map_episode_nan_bars: null, event_map_n_swings: null,
    event_map_n_labels: null, event_map_n_committed: null,
    event_map_pre_box_trend: null, event_map_episode_profile: null,
    event_map_episodes: null,
  };
  const cells = chapterCells(preEventMap);
  const phaseB = cells.find(c => c.key === 'phase_b');
  const cause = cells.find(c => c.key === 'cause');
  assert.match(phaseB.subtext, /not measured/);
  assert.equal(cause.subtext, null);       // non-story chapters carry none
});

test('measured-zero story rows say so, with the readability caveat', () => {
  const zeros = {
    ...GRADED,
    event_map_completed_s: 0, event_map_completed_r: 0,
    event_map_alternations: 0, event_map_terminal_posture: 0,
    event_map_terminal_drift: 0, event_map_story_admitted: 0,
    event_map_n_swings: 0, event_map_n_labels: 0, event_map_n_committed: 0,
    event_map_episode_nan_bars: 6,
  };
  const phaseB = chapterCells(zeros).find(c => c.key === 'phase_b');
  assert.match(phaseB.subtext, /no completed rail events/);
  assert.match(phaseB.subtext, /6 bars unreadable/);
});

test('warnings render with their cost — neutral factors visibly costless', () => {
  const items = warningItems({
    ta_grade_warnings: { weak_monthly: 1.0, terminal_drift: 0.8, mystery: 0.5 },
  });
  assert.deepEqual(items.map(i => [i.label, i.cost]), [
    ['Weak monthly', null],
    ['Ends drifting on support', '−20%'],   // renamed 2026-08-10 (plain words)
    ['mystery', '−50%'],                    // unknown id falls through visibly
  ]);
  assert.deepEqual(warningItems({}), []);
});

test('every chapter lights its OWN phase (identity since the 2026-08-12 fold)', () => {
  // A row labelled Phase C that lights Phase D contradicts its own words now
  // that the fused panel shows each phase's span and grade on one row.
  assert.equal(CHAPTER_REGION.phase_c, 'c');
  assert.equal(CHAPTER_REGION.phase_d, 'd');
  // Cause grades the base as a whole — it lights Phase B's box, deliberately
  // the same target, and keeps its own words (see setupStoryRows).
  assert.equal(CHAPTER_REGION.cause, 'b');
  assert.equal(CHAPTER_REGION.phase_b, 'b');
  // The trend chapter reads the chart AROUND the base — nothing to light.
  assert.equal(CHAPTER_REGION.trend, null);
});
