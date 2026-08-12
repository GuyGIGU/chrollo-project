import test from 'node:test';
import assert from 'node:assert/strict';
import {
  GLANCE_HEIGHT,
  GLANCE_STATUSES,
  GLANCE_WIDTH,
  glanceChartKey,
  glancePlacement,
  isGlanceStatus,
} from './glanceMath.js';

const VIEW = { width: 1536, height: 864 };
// A ticker cell partway down a table on the left of the screen.
const cell = (left, top) => ({ left, right: left + 70, top, bottom: top + 26 });

test('the status vocabulary is one closed tuple (EC-33) with every leg distinct', () => {
  assert.deepEqual(GLANCE_STATUSES, ['closed', 'pending', 'ready', 'empty', 'error']);
  assert.equal(new Set(GLANCE_STATUSES).size, GLANCE_STATUSES.length);
  for (const status of GLANCE_STATUSES) assert.ok(isGlanceStatus(status));
  // EC-27: the refusing legs must not collapse into each other or into ready.
  assert.ok(!isGlanceStatus('loading'));
  assert.ok(!isGlanceStatus('failed'));
  assert.ok(!isGlanceStatus(undefined));
});

test('places the glass to the right of the anchor when there is room', () => {
  const place = glancePlacement({ anchor: cell(120, 400), viewport: VIEW });
  assert.equal(place.side, 'right');
  assert.equal(place.left, 190 + 12);                 // anchor right + gap
  assert.equal(place.top, 413 - GLANCE_HEIGHT / 2);   // centred on the anchor
});

test('flips to the left edge rather than hanging off the right', () => {
  const place = glancePlacement({ anchor: cell(1400, 300), viewport: VIEW });
  assert.equal(place.side, 'left');
  assert.equal(place.left, 1400 - 12 - GLANCE_WIDTH);
  assert.ok(place.left >= 0);
});

test('clamps into view for anchors at the very top and bottom', () => {
  const high = glancePlacement({ anchor: cell(200, 2), viewport: VIEW });
  assert.equal(high.top, 8);
  const low = glancePlacement({ anchor: cell(200, 850), viewport: VIEW });
  assert.equal(low.top, VIEW.height - GLANCE_HEIGHT - 8);
});

test('divides screen coordinates by --ui-scale — the zoom trap', () => {
  // THE bug this test exists for: getBoundingClientRect answers in screen px
  // (already multiplied by the app's `zoom`), while a fixed child of the zoomed
  // subtree positions in pre-zoom px. At scale 1 the two agree, so an
  // uncorrected version looks perfect on an unzoomed machine and lands ~a
  // quarter-screen away at 1.25.
  const anchor = cell(500, 400);
  const at1 = glancePlacement({ anchor, viewport: VIEW, scale: 1 });
  const at125 = glancePlacement({ anchor, viewport: VIEW, scale: 1.25 });
  assert.notDeepEqual(at1, at125);
  assert.equal(at125.left, 570 / 1.25 + 12);
  assert.equal(at125.top, 413 / 1.25 - GLANCE_HEIGHT / 2);
  // And the clamp uses the zoomed viewport too, never the raw one.
  const edge = glancePlacement({ anchor: cell(1500, 800), viewport: VIEW, scale: 1.25 });
  assert.ok(edge.left + GLANCE_WIDTH <= VIEW.width / 1.25 - 8 + 0.001);
  assert.ok(edge.top + GLANCE_HEIGHT <= VIEW.height / 1.25 - 8 + 0.001);
});

test('a nonsense scale degrades to 1 instead of dividing by zero', () => {
  const expected = glancePlacement({ anchor: cell(300, 300), viewport: VIEW, scale: 1 });
  for (const scale of [0, -1, NaN, null, undefined, 'x']) {
    assert.deepEqual(glancePlacement({ anchor: cell(300, 300), viewport: VIEW, scale }), expected);
  }
});

test('no anchor or no viewport means no placement', () => {
  assert.equal(glancePlacement({ anchor: null, viewport: VIEW }), null);
  assert.equal(glancePlacement({ anchor: cell(10, 10), viewport: null }), null);
});

test('a viewport smaller than the glass still yields an on-screen origin', () => {
  const tiny = glancePlacement({ anchor: cell(10, 10), viewport: { width: 320, height: 200 } });
  assert.equal(tiny.left, 8);
  assert.equal(tiny.top, 8);
});

test('the chart key tracks the SCAN, not the payload object', () => {
  assert.equal(glanceChartKey('NVDA', '2026-08-11'), 'NVDA|2026-08-11');
  // Same ticker, same scan -> same key, so a store swap that hands out a fresh
  // chart_data object mid-hover cannot tear down and rebuild the open chart.
  assert.equal(glanceChartKey('NVDA', '2026-08-11'), glanceChartKey('NVDA', '2026-08-11'));
  assert.notEqual(glanceChartKey('NVDA', '2026-08-11'), glanceChartKey('NVDA', '2026-08-12'));
  assert.equal(glanceChartKey(null, null), '?|none');
});
