import { test } from 'node:test';
import assert from 'node:assert/strict';

import {
  ABSENCE_COPY,
  NARRATIVE_STATUS,
  NARRATIVE_WIRE_FIELDS,
  episodeSpans,
  narrativeStatus,
  readabilityCaveat,
  shapeTrace,
  tapeGlyphs,
} from './narrativeRead.js';

// ── the status enum: NULL ≠ 0 is the load-bearing distinction ───────────────

test('key-ABSENCE is NOT_CARRIED — only a wire carrying the family may claim not-measured', () => {
  // Council review 2026-08-05, finding 4: a payload that never carries the
  // family (the old archive chart dict) must not render the "predates the
  // read" diagnosis — that copy was shown on rows measured yesterday.
  assert.equal(narrativeStatus(null), NARRATIVE_STATUS.NOT_CARRIED);
  assert.equal(narrativeStatus({}), NARRATIVE_STATUS.NOT_CARRIED);
  assert.equal(narrativeStatus({ ticker: 'AAA', candles: [] }), NARRATIVE_STATUS.NOT_CARRIED);
});

test('a present-as-NULL family is NOT_MEASURED — never empty, never not-carried', () => {
  assert.equal(
    narrativeStatus({ event_map_completed_s: null, event_map_completed_r: null }),
    NARRATIVE_STATUS.NOT_MEASURED,
  );
});

test('a partial write reads as measured — ANY family scalar carries the proof', () => {
  // The design rule stated in the module header, pinned (council F15/beck):
  // a row where only a non-s/r scalar is non-null must NOT collapse into
  // NOT_MEASURED (and with zero completed tests + no episodes it is the
  // measured-empty state).
  const row = { event_map_terminal_drift: 0, event_map_completed_s: null };
  assert.notEqual(narrativeStatus(row), NARRATIVE_STATUS.NOT_MEASURED);
  assert.equal(narrativeStatus(row), NARRATIVE_STATUS.EMPTY);
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

test('glyphs zip tokens with tape entries — dates, labels, the ~ mark', () => {
  const glyphs = tapeGlyphs(READY_ROW);
  assert.equal(glyphs.length, 3);
  assert.equal(glyphs[0].token, 'S+');
  assert.equal(glyphs[0].label, 'completed support test');
  assert.deepEqual(glyphs[0].span, ['2026-05-01', '2026-05-05']);
  assert.equal(glyphs[1].unknowable, true);      // the ~ suffix survives display
  // Only rendered fields ship (council F14): the speculative rail/outcome/
  // posture fields carried untested wrong fallbacks — a future consumer adds
  // what it needs WITH pinned fallbacks.
  assert.deepEqual(
    Object.keys(glyphs[0]).sort(),
    ['id', 'label', 'span', 'token', 'unknowable'],
  );
});

test('readabilityCaveat surfaces the nan-bars companion — zero-by-unreadable never masquerades', () => {
  // Council F10: the engine archives event_map_episode_nan_bars precisely so
  // an unreadable-bars zero can't pose as the junk-separator zero.
  assert.equal(readabilityCaveat({ event_map_episode_nan_bars: 3 }), '3 bars unreadable');
  assert.equal(readabilityCaveat({ event_map_episode_nan_bars: 1 }), '1 bar unreadable');
  assert.equal(readabilityCaveat({ event_map_episode_nan_bars: 0 }), null);
  assert.equal(readabilityCaveat({ event_map_episode_nan_bars: null }), null);
  assert.equal(readabilityCaveat({}), null);
  assert.equal(readabilityCaveat(null), null);
});

test('the wire-fields list carries every family key a SetupOut row serves', () => {
  // The archive chart merge copies exactly these (council F4); the family
  // scalars the status enum reads must all be on the list.
  for (const key of ['event_map_completed_s', 'event_map_episode_nan_bars',
    'event_map_episodes', 'event_map_episode_profile', 'elected_pool',
    'story_admission_profile', 'election_trace']) {
    assert.ok(NARRATIVE_WIRE_FIELDS.includes(key), key);
  }
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
