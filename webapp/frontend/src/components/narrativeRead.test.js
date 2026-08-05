import { test } from 'node:test';
import assert from 'node:assert/strict';

import {
  ABSENCE_COPY,
  NARRATIVE_STATUS,
  episodeSpans,
  narrativeStatus,
  shapeTrace,
  tapeGlyphs,
} from './narrativeRead.js';

// ── the status enum: NULL ≠ 0 is the load-bearing distinction ───────────────

test('a null family is NOT_MEASURED — never empty', () => {
  assert.equal(narrativeStatus(null), NARRATIVE_STATUS.NOT_MEASURED);
  assert.equal(narrativeStatus({}), NARRATIVE_STATUS.NOT_MEASURED);
  assert.equal(
    narrativeStatus({ event_map_completed_s: null, event_map_completed_r: null }),
    NARRATIVE_STATUS.NOT_MEASURED,
  );
});

test('explicit zeros are EMPTY — a measured finding, distinct from not-measured', () => {
  const row = {
    event_map_completed_s: 0,
    event_map_completed_r: 0,
    event_map_episode_nan_bars: 0,
    event_map_episodes: [],
    event_map_episode_profile: '',
  };
  assert.equal(narrativeStatus(row), NARRATIVE_STATUS.EMPTY);
  assert.notEqual(
    narrativeStatus(row),
    narrativeStatus({}),
  );
  assert.notEqual(ABSENCE_COPY.empty, ABSENCE_COPY.not_measured);
});

test('zero completed tests with OPEN episodes is READY, not empty', () => {
  // 0 completed S-tests is a real engine statement; an open engagement still
  // gives the operator something to read.
  const row = {
    event_map_completed_s: 0,
    event_map_completed_r: 0,
    event_map_episodes: [
      { rail: 'S', outcome: 'open', posture: false, span: ['2026-07-01', '2026-07-08'], knowable: null },
    ],
    event_map_episode_profile: 'S0',
  };
  assert.equal(narrativeStatus(row), NARRATIVE_STATUS.READY);
});

// ── the glyph strip: engine tokens are authoritative ────────────────────────

const READY_ROW = {
  event_map_completed_s: 2,
  event_map_completed_r: 1,
  event_map_episode_profile: 'S+ S+~ R^',
  event_map_episodes: [
    { rail: 'S', outcome: 'completed', posture: false, span: ['2026-05-01', '2026-05-05'], knowable: '2026-05-08' },
    { rail: 'S', outcome: 'completed', posture: false, span: ['2026-06-01', '2026-06-03'], knowable: null },
    { rail: 'R', outcome: 'open', posture: true, span: ['2026-07-01', '2026-07-03'], knowable: null },
  ],
};

test('glyphs zip tokens with tape entries — dates, labels, the ~ mark, the posture', () => {
  const glyphs = tapeGlyphs(READY_ROW);
  assert.equal(glyphs.length, 3);
  assert.equal(glyphs[0].token, 'S+');
  assert.equal(glyphs[0].label, 'completed support test');
  assert.deepEqual(glyphs[0].span, ['2026-05-01', '2026-05-05']);
  assert.equal(glyphs[1].unknowable, true);      // the ~ suffix survives display
  assert.equal(glyphs[2].posture, true);          // terminal R engagement
});

test('a token/tape length mismatch degrades to tokens-only — never throws, never invents spans', () => {
  const glyphs = tapeGlyphs({
    event_map_episode_profile: 'S+ R^',
    event_map_episodes: [{ rail: 'S', outcome: 'completed', span: ['a', 'b'] }],
  });
  assert.equal(glyphs.length, 2);
  assert.equal(glyphs[0].span, null);
  assert.equal(glyphs[0].label, 'S+');            // verbatim fallthrough
});

test('episodeSpans feeds the single activeRegion channel with date anchors only', () => {
  const spans = episodeSpans(READY_ROW);
  assert.equal(spans.length, 3);
  assert.deepEqual(spans[0], {
    id: 'episode-0', from: '2026-05-01', to: '2026-05-05',
    label: 'completed support test',
  });
});

// ── the trace shaper: relabels, never re-judges ─────────────────────────────

test('shapeTrace relabels codes through supplied vocabularies and keeps sentences verbatim', () => {
  const shaped = shapeTrace({
    roots: [{
      climax: '2026-05-05', ar: '2026-05-12', outcome: 'no_box', candidates: 4,
      refused: { width: 3, occupancy: 1 },
      furthest: { passed: false, stage: 'occupancy', sentences: ['time in the lower third 0.10 vs floor 0.15'] },
    }],
    elected: null,
  }, {
    stages: { occupancy: 'occupancy', width: 'box width' },
    outcomes: { no_box: 'no worked range' },
  });
  assert.equal(shaped.roots[0].outcome, 'no worked range');
  assert.deepEqual(shaped.roots[0].refused[0], { stage: 'box width', count: 3 });
  assert.equal(
    shaped.roots[0].furthest.sentences[0],
    'time in the lower third 0.10 vs floor 0.15',
  );
  assert.equal(shaped.elected, null);
});

test('shapeTrace on a null/unreadable trace is null — the surface renders its absence state', () => {
  assert.equal(shapeTrace(null), null);
  assert.equal(shapeTrace(undefined), null);
});
