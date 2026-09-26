// The chapter strip's presentation contract (TA-grade build task 12).
import test from 'node:test';
import assert from 'node:assert/strict';
import { CHAPTER_REGION, chapterCells, warningItems } from './chapterStrip.js';

const GRADED = {
  ta_grade: 61.2,
  ta_grade_chapters: { consolidation: 41.3, phase_d: 14.9, trend: 5.0 },
  ta_grade_chapter_fractions: { consolidation: 0.66, phase_d: 0.62, trend: 0.31 },
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

test('graded payload yields the three ruled chapters, in story order', () => {
  const cells = chapterCells(GRADED);
  assert.deepEqual(cells.map(c => c.key), ['consolidation', 'phase_d', 'trend']);
  assert.equal(cells[0].points, 41.3);
  assert.equal(cells[0].fraction, 0.66);
  assert.equal(cells.every(c => c.fraction >= 0 && c.fraction <= 1), true);
  // A clean measured story: no honesty caveat on the story chapters.
  assert.equal(cells[0].subtext, null);
  assert.equal(cells[1].subtext, null);
});

test('ungraded payload renders no strip at all', () => {
  assert.deepEqual(chapterCells({ ta_grade: null }), []);
  assert.deepEqual(chapterCells({}), []);
  assert.deepEqual(chapterCells(null), []);
});

test('graded payload WITHOUT chapters renders no strip — never fabricated 0.0 cells', () => {
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
  const cons = chapterCells(notCarried).find(c => c.key === 'consolidation');
  assert.equal(cons.subtext, null);
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
  const cons = cells.find(c => c.key === 'consolidation');
  const trend = cells.find(c => c.key === 'trend');
  assert.match(cons.subtext, /not measured/);
  assert.equal(trend.subtext, null);       // non-story chapters carry none
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
  const cons = chapterCells(zeros).find(c => c.key === 'consolidation');
  assert.match(cons.subtext, /no completed rail events/);
  assert.match(cons.subtext, /6 bars unreadable/);
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

test('every chapter lights the band it grades, and Phase C is not a chapter', () => {
  // Consolidation is Cause and Phase B fused (operator ruling 2026-08-12): it
  // grades the base as a whole and lights the box.
  assert.equal(CHAPTER_REGION.consolidation, 'b');
  assert.equal(CHAPTER_REGION.phase_d, 'd');
  // The trend chapter reads the chart AROUND the base — nothing to light.
  assert.equal(CHAPTER_REGION.trend, null);
  // Phase C is a MARK, not a chapter: it comes off the region list directly, so
  // it must not reappear here as a routable chapter.
  assert.equal('phase_c' in CHAPTER_REGION, false);
  assert.equal('cause' in CHAPTER_REGION, false);
  assert.equal('phase_b' in CHAPTER_REGION, false);
});
