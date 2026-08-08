// The chapter strip's presentation contract (TA-grade build task 12).
import test from 'node:test';
import assert from 'node:assert/strict';
import { CHAPTER_REGION, chapterCells, warningItems } from './chapterStrip.js';

const GRADED = {
  ta_grade: 61.2,
  ta_grade_chapters: {
    cause: 18.2, work: 21.0, turn: 2.1, finish: 14.9, trend_context: 5.0,
  },
  ta_grade_chapter_fractions: {
    cause: 0.66, work: 0.55, turn: 0.26, finish: 0.62, trend_context: 0.31,
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
    ['cause', 'work', 'turn', 'finish', 'trend_context']);
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
  const work = cells.find(c => c.key === 'work');
  const cause = cells.find(c => c.key === 'cause');
  assert.match(work.subtext, /not measured/);
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
  const work = chapterCells(zeros).find(c => c.key === 'work');
  assert.match(work.subtext, /no completed rail events/);
  assert.match(work.subtext, /6 bars unreadable/);
});

test('warnings render with their cost — neutral factors visibly costless', () => {
  const items = warningItems({
    ta_grade_warnings: { weak_monthly: 1.0, terminal_drift: 0.8, mystery: 0.5 },
  });
  assert.deepEqual(items.map(i => [i.label, i.cost]), [
    ['Weak monthly', null],
    ['Terminal drift', '−20%'],
    ['mystery', '−50%'],                    // unknown id falls through visibly
  ]);
  assert.deepEqual(warningItems({}), []);
});

test('chapter hover targets map onto the existing chart regions', () => {
  assert.equal(CHAPTER_REGION.finish, 'lps');
  assert.equal(CHAPTER_REGION.turn, 'd');
  assert.equal(CHAPTER_REGION.trend_context, null);
});
