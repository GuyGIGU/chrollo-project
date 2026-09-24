import test from 'node:test';
import assert from 'node:assert/strict';
import {
  GLANCE_HEIGHT,
  GLANCE_STATUSES,
  GLANCE_WIDTH,
  glanceAction,
  glanceChartKey,
  glancePlacement,
  isGlanceStatus,
} from './glanceMath.js';

const VIEW = { width: 1536, height: 864 };
// A cursor somewhere in the table, in screen (client) px.
const at = (x, y) => ({ x, y });
const GAP = 16;
const MARGIN = 8;

test('the status vocabulary is one closed tuple (EC-33) with every leg distinct', () => {
  assert.deepEqual(GLANCE_STATUSES, ['closed', 'pending', 'ready', 'empty', 'error']);
  assert.equal(new Set(GLANCE_STATUSES).size, GLANCE_STATUSES.length);
  for (const status of GLANCE_STATUSES) assert.ok(isGlanceStatus(status));
  // EC-27: the refusing legs must not collapse into each other or into ready.
  assert.ok(!isGlanceStatus('loading'));
  assert.ok(!isGlanceStatus('failed'));
  assert.ok(!isGlanceStatus(undefined));
});

test('lands down-and-right of the cursor when there is room', () => {
  // The whole point of the 2026-09-02 change: the glass appears where the
  // operator is looking, not at a fixed spot on the row.
  const place = glancePlacement({ pointer: at(400, 300), viewport: VIEW });
  assert.equal(place.side, 'right');
  assert.equal(place.vertical, 'below');
  assert.equal(place.left, 400 + GAP);
  assert.equal(place.top, 300 + GAP);
});

test('two cursor positions on the SAME row place the glass differently', () => {
  // The regression guard for "static": the old placement read the row's ticker
  // cell, so every point on a row produced one identical position.
  const near = glancePlacement({ pointer: at(200, 300), viewport: VIEW });
  const far = glancePlacement({ pointer: at(900, 300), viewport: VIEW });
  assert.notEqual(near.left, far.left);
  assert.equal(far.left - near.left, 700);
});

test('flips left rather than hanging off the right edge', () => {
  const place = glancePlacement({ pointer: at(1400, 300), viewport: VIEW });
  assert.equal(place.side, 'left');
  assert.equal(place.left, 1400 - GAP - GLANCE_WIDTH);
  assert.ok(place.left >= MARGIN);
});

test('flips above rather than hanging off the bottom edge', () => {
  const place = glancePlacement({ pointer: at(400, 800), viewport: VIEW });
  assert.equal(place.vertical, 'above');
  assert.equal(place.top, 800 - GAP - GLANCE_HEIGHT);
  assert.ok(place.top >= MARGIN);
});

test('a bottom-right cursor flips BOTH axes, so the glass is never under it', () => {
  // Each axis flips against the same point, so the glass retreats diagonally.
  const x = 1500;
  const y = 840;
  const place = glancePlacement({ pointer: at(x, y), viewport: VIEW });
  assert.equal(place.side, 'left');
  assert.equal(place.vertical, 'above');
  assert.ok(place.left + GLANCE_WIDTH < x, 'glass ends left of the cursor');
  assert.ok(place.top + GLANCE_HEIGHT < y, 'glass ends above the cursor');
});

test('clamps into view for a cursor at the very top and bottom', () => {
  const high = glancePlacement({ pointer: at(200, 2), viewport: VIEW });
  assert.equal(high.top, 2 + GAP); // still fits below
  const low = glancePlacement({ pointer: at(200, 862), viewport: VIEW });
  assert.ok(low.top >= MARGIN);
  assert.ok(low.top + GLANCE_HEIGHT <= VIEW.height - MARGIN);
});

test('divides screen coordinates by --ui-scale — the zoom trap', () => {
  // THE bug this test exists for: pointer coordinates answer in screen px
  // (already multiplied by the app's `zoom`), while a fixed child of the zoomed
  // subtree positions in pre-zoom px. At scale 1 the two agree, so an
  // uncorrected version looks perfect on an unzoomed machine and lands ~a
  // quarter-screen away at 1.25.
  const pointer = at(500, 400);
  const at1 = glancePlacement({ pointer, viewport: VIEW, scale: 1 });
  const at125 = glancePlacement({ pointer, viewport: VIEW, scale: 1.25 });
  assert.notDeepEqual(at1, at125);
  assert.equal(at125.left, 500 / 1.25 + GAP);
  assert.equal(at125.top, 400 / 1.25 + GAP);
  // And the VIEWPORT is divided too, never used raw. This pair is the guard:
  // (1200, 700) is a point the raw 1536x864 would happily keep down-and-right,
  // and only the zoomed 1228.8x691.2 pane knows the glass no longer fits there.
  // The bottom-right fixture below cannot do this job — it flips under either
  // viewport, so it returns identical numbers with the division deleted, which
  // is exactly how this half went unguarded until the 2026-09-02 review.
  const flip = glancePlacement({ pointer: at(1200, 700), viewport: VIEW, scale: 1.25 });
  assert.equal(flip.side, 'left');
  assert.equal(flip.vertical, 'above');
  // Bounds corroborate; they would pass under the mutant on their own.
  const edge = glancePlacement({ pointer: at(1500, 800), viewport: VIEW, scale: 1.25 });
  assert.ok(edge.left + GLANCE_WIDTH <= VIEW.width / 1.25 - MARGIN + 0.001);
  assert.ok(edge.top + GLANCE_HEIGHT <= VIEW.height / 1.25 - MARGIN + 0.001);
});

test('a nonsense scale degrades to 1 instead of dividing by zero', () => {
  const expected = glancePlacement({ pointer: at(300, 300), viewport: VIEW, scale: 1 });
  for (const scale of [0, -1, NaN, null, undefined, 'x']) {
    assert.deepEqual(glancePlacement({ pointer: at(300, 300), viewport: VIEW, scale }), expected);
  }
});

test('no cursor, no viewport, or a non-finite point means no placement', () => {
  assert.equal(glancePlacement({ pointer: null, viewport: VIEW }), null);
  assert.equal(glancePlacement({ pointer: at(10, 10), viewport: null }), null);
  // A half-built point must not resolve to the top-left corner: the hook opens
  // the glass on whatever this returns, and NaN coordinates would paint it at 8,8.
  assert.equal(glancePlacement({ pointer: { x: 10 }, viewport: VIEW }), null);
  assert.equal(glancePlacement({ pointer: at(NaN, 10), viewport: VIEW }), null);
});

test('a viewport smaller than the glass still yields an on-screen origin', () => {
  const tiny = glancePlacement({ pointer: at(10, 10), viewport: { width: 320, height: 200 } });
  assert.equal(tiny.left, MARGIN);
  assert.equal(tiny.top, MARGIN);
});

test('the chart key tracks the SCAN, not the payload object', () => {
  assert.equal(glanceChartKey('NVDA', '2026-08-11'), 'NVDA|2026-08-11');
  // Same ticker, same scan -> same key, so a store swap that hands out a fresh
  // chart_data object mid-hover cannot tear down and rebuild the open chart.
  assert.equal(glanceChartKey('NVDA', '2026-08-11'), glanceChartKey('NVDA', '2026-08-11'));
  assert.notEqual(glanceChartKey('NVDA', '2026-08-11'), glanceChartKey('NVDA', '2026-08-12'));
  assert.equal(glanceChartKey(null, null), '?|none');
});

test('a stationary pointer decides nothing — the same anchor never re-arms', () => {
  // A resting cursor sends a move event per frame. If this said 'arm' the timer
  // would restart forever and the glass would never open at all.
  assert.equal(glanceAction({ current: 'NVDA', next: 'NVDA', open: false }), 'none');
  assert.equal(glanceAction({ current: 'NVDA', next: 'NVDA', open: true }), 'none');
  assert.equal(glanceAction({ current: null, next: null, open: false }), 'none');
});

test('a new anchor arms when nothing is up and swaps instantly when it is', () => {
  assert.equal(glanceAction({ current: null, next: 'NVDA', open: false }), 'arm');
  assert.equal(glanceAction({ current: 'AMD', next: 'NVDA', open: false }), 'arm');
  // Already reading: retarget with no delay, or every row would blank and
  // rebuild its chart on the way down the table.
  assert.equal(glanceAction({ current: 'AMD', next: 'NVDA', open: true }), 'swap');
});

test('leaving every anchor closes, and coming back to the same one re-opens', () => {
  assert.equal(glanceAction({ current: 'NVDA', next: null, open: true }), 'close');
  assert.equal(glanceAction({ current: 'NVDA', next: null, open: false }), 'close');
  // After a hard dismissal (scroll, click, Escape) the hook forgets its key
  // while the glass is still up during the grace — the very next sample over
  // the SAME row must be a swap, not silence. This is the wedge the operator
  // hit: an event-driven glass had nothing left to fire.
  assert.equal(glanceAction({ current: null, next: 'NVDA', open: true }), 'swap');
});

test('undefined reads as empty space, never as an anchor named undefined', () => {
  assert.equal(glanceAction({}), 'none');
  assert.equal(glanceAction({ current: 'NVDA' }), 'close');
  assert.equal(glanceAction({ next: 'NVDA' }), 'arm');
});
