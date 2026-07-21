// Re-mark robustness (Task 6 spec, the operator's non-negotiable Quality bar):
// every element of a setup must be freely re-armable / re-placeable / clearable
// at any time, in any order, non-destructively — the marking state machine is
// the piece most "toyed with", and a re-draw must never corrupt the draft or
// lose work. Targeted cases pin the known re-mark paths; a deterministic fuzz
// hammers arbitrary action orders and asserts the draft invariants always hold.
// (The Trigger's own re-snap-to-a-redrawn-LPS cases are added in Task 9, when
// the reducer learns the Trigger.)
import assert from 'node:assert/strict';
import test from 'node:test';
import {
  emptyDraft, markingReducer, initialMarkingState, draftComplete,
} from './calibrationMarking.js';

const KEYS = Object.keys(emptyDraft());
const bar = (high, low) => ({ high, low });
const click = (date, price, b) => ({ type: 'chart-click', date, price, bar: b });
const arm = (tool) => ({ type: 'tool', tool });

// Every reachable draft must keep the shape + the normalization invariants.
function assertInvariants(state, label) {
  const d = state.draft;
  assert.ok(d && typeof d === 'object', `${label}: draft present`);
  for (const k of KEYS) assert.ok(k in d, `${label}: draft keeps key ${k}`);
  assert.ok(Array.isArray(d.events), `${label}: events is an array`);
  if (d.resistance != null && d.support != null) {
    assert.ok(d.resistance >= d.support, `${label}: R>=S after normalization`);
  }
  if (d.verdict !== 'box') {
    assert.equal(d.resistance, null, `${label}: negative carries no R`);
    assert.equal(d.support, null, `${label}: negative carries no S`);
    assert.equal(d.boxStartDate, null, `${label}: negative carries no span`);
    assert.equal(d.events.length, 0, `${label}: negative carries no events`);
  }
  assert.equal(typeof draftComplete(d), 'boolean', `${label}: draftComplete total`);
}

// ---- targeted re-mark paths -------------------------------------------------

test('re-arming the same tool toggles it off, never a stuck armed state', () => {
  let s = initialMarkingState(null, 'F');
  s = markingReducer(s, arm('rail-r'));
  assert.equal(s.tool, 'rail-r');
  s = markingReducer(s, arm('rail-r'));   // re-arm == disarm
  assert.equal(s.tool, 'idle');
  s = markingReducer(s, arm('rail-r'));
  s = markingReducer(s, arm('span'));     // switching drops any half span anchor
  assert.equal(s.tool, 'span');
  assert.equal(s.spanAnchor, null);
});

test('re-placing a rail replaces it cleanly — last placement wins, one value', () => {
  let s = initialMarkingState(null, 'F');
  for (const p of [10, 11, 12]) {
    s = markingReducer(s, arm('rail-r'));
    s = markingReducer(s, click('2026-01-05', p, bar(p, p - 1)));
  }
  assert.equal(s.draft.resistance, 12);   // only the last survives
  assert.equal(s.draft.rAnchorDate, '2026-01-05');
  assertInvariants(s, 're-place rail');
});

test('rails placed in either order normalize to R>=S with firstRail preserved', () => {
  // support first, then a higher resistance
  let a = initialMarkingState(null, 'F');
  a = markingReducer(a, arm('rail-s'));
  a = markingReducer(a, click('2026-01-02', 8, bar(9, 8)));
  a = markingReducer(a, arm('rail-r'));
  a = markingReducer(a, click('2026-01-06', 12, bar(12, 11)));
  assert.ok(a.draft.resistance >= a.draft.support);
  assert.equal(a.draft.firstRail, 'support');
  // resistance first, but the second click is LOWER — must swap and re-label
  let b = initialMarkingState(null, 'F');
  b = markingReducer(b, arm('rail-r'));
  b = markingReducer(b, click('2026-01-02', 12, bar(12, 11)));
  b = markingReducer(b, arm('rail-s'));
  b = markingReducer(b, click('2026-01-06', 15, bar(16, 15))); // "support" click above R
  assert.ok(b.draft.resistance >= b.draft.support);
  assertInvariants(b, 'inverted-order rails');
});

test('clear returns an empty draft but keeps the frame key (work-loss guard scope)', () => {
  let s = initialMarkingState(null, 'FRAME-1');
  s = markingReducer(s, arm('rail-r'));
  s = markingReducer(s, click('2026-01-05', 12, bar(12, 11)));
  s = markingReducer(s, { type: 'clear' });
  assert.deepEqual(s.draft, emptyDraft());
  assert.equal(s.frameKey, 'FRAME-1');
  assert.equal(s.tool, 'idle');
});

test('verdict box -> negative -> box never resurrects the dropped geometry', () => {
  let s = initialMarkingState(null, 'F');
  s = markingReducer(s, arm('rail-r'));
  s = markingReducer(s, click('2026-01-05', 12, bar(12, 11)));
  s = markingReducer(s, { type: 'verdict', verdict: 'no_structure' });
  assertInvariants(s, 'switched to negative');
  s = markingReducer(s, { type: 'verdict', verdict: 'box' });
  assert.equal(s.draft.resistance, null); // back to box is a FRESH box, no ghost rail
  assertInvariants(s, 'back to box');
});

test('events add then remove-by-index preserves order and never drops the wrong one', () => {
  let s = initialMarkingState(null, 'F');
  const addEvent = (type, a, b2) => {
    s = markingReducer(s, arm(`event:${type}`));
    s = markingReducer(s, click(a, 5, bar(6, 5)));   // start
    s = markingReducer(s, click(b2, 5, bar(6, 5)));  // end
  };
  addEvent('phase_c', '2026-01-02', '2026-01-05');
  addEvent('lps', '2026-01-08', '2026-01-10');
  addEvent('spring_test', '2026-01-11', '2026-01-12');
  assert.deepEqual(s.draft.events.map((e) => e.event_type),
    ['phase_c', 'lps', 'spring_test']);
  s = markingReducer(s, { type: 'remove-event', index: 1 }); // drop the lps
  assert.deepEqual(s.draft.events.map((e) => e.event_type), ['phase_c', 'spring_test']);
  assertInvariants(s, 'after event remove');
});

test('edit-mark then re-edit replaces the draft cleanly, no bleed between marks', () => {
  const markA = { id: 1, verdict: 'box', resistance: 20, support: 18,
    box_start_date: '2026-01-01', box_end_date: '2026-01-10', events: [] };
  const markB = { id: 2, verdict: 'box', resistance: 9, support: 7,
    box_start_date: '2026-02-01', box_end_date: '2026-02-10',
    events: [{ event_type: 'lps', start_date: '2026-02-05', end_date: '2026-02-06' }] };
  let s = initialMarkingState(null, 'F');
  s = markingReducer(s, { type: 'edit-mark', mark: markA });
  assert.equal(s.editingId, 1);
  assert.equal(s.draft.resistance, 20);
  s = markingReducer(s, { type: 'edit-mark', mark: markB }); // switch straight to another
  assert.equal(s.editingId, 2);
  assert.equal(s.draft.resistance, 9);
  assert.equal(s.draft.events.length, 1);
  assertInvariants(s, 'after re-edit');
});

// ---- deterministic fuzz -----------------------------------------------------

function mulberry32(seed) {
  return () => {
    seed |= 0; seed = (seed + 0x6D2B79F5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

test('fuzz: arbitrary re-mark sequences never corrupt the draft (50 seeds x 60 steps)', () => {
  const dates = ['2026-01-02', '2026-01-05', '2026-01-08', '2026-01-10', '2026-01-14'];
  const tools = ['rail-r', 'rail-s', 'span', 'event:phase_c', 'event:lps', 'event:spring_test'];
  const verdicts = ['box', 'no_structure', 'engine_wrong'];
  for (let seed = 1; seed <= 50; seed += 1) {
    const rnd = mulberry32(seed);
    const pick = (arr) => arr[Math.floor(rnd() * arr.length)];
    let s = initialMarkingState(null, 'FUZZ-FRAME');
    for (let step = 0; step < 60; step += 1) {
      const roll = rnd();
      if (roll < 0.35) s = markingReducer(s, arm(pick(tools)));
      else if (roll < 0.75) {
        const p = 5 + Math.floor(rnd() * 20);
        s = markingReducer(s, click(pick(dates), p, bar(p + 1, p - 1)));
      } else if (roll < 0.85) s = markingReducer(s, { type: 'verdict', verdict: pick(verdicts) });
      else if (roll < 0.92) {
        const n = s.draft.events.length;
        if (n) s = markingReducer(s, { type: 'remove-event', index: Math.floor(rnd() * n) });
      } else s = markingReducer(s, { type: 'clear' });
      assert.equal(s.frameKey, 'FUZZ-FRAME', `seed ${seed} step ${step}: frame stable`);
      assertInvariants(s, `seed ${seed} step ${step}`);
    }
  }
});
