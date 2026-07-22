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
  emptyDraft, markingReducer, initialMarkingState, draftComplete, saveNeeds,
  snapTrigger, draftFromMark, markPayloadFromDraft, draftStarted,
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
    assert.equal(d.triggerDate, null, `${label}: negative carries no trigger`);
  }
  if (d.triggerDate != null) {
    assert.equal(d.verdict, 'box', `${label}: trigger only on a box`);
    assert.ok(Number.isFinite(d.triggerPrice), `${label}: trigger has a finite price`);
  }
  assert.equal(typeof draftComplete(d), 'boolean', `${label}: draftComplete total`);
}

// ---- targeted re-mark paths -------------------------------------------------

test('draftStarted: false on a pristine/just-saved draft, true once anything is drawn', () => {
  // The empty draft (fresh frame, or the reset a save leaves) is NOT started —
  // so the "needs resistance/support/span" readout stays silent and a saved
  // setup never reads as incomplete.
  assert.equal(draftStarted(emptyDraft()), false);
  // Each element that can be placed flips it on, one at a time.
  assert.equal(draftStarted({ ...emptyDraft(), resistance: 12 }), true);
  assert.equal(draftStarted({ ...emptyDraft(), support: 10 }), true);
  assert.equal(draftStarted({ ...emptyDraft(), rAnchorDate: '2026-01-02' }), true);
  assert.equal(draftStarted({ ...emptyDraft(), boxStartDate: '2026-01-02' }), true);
  assert.equal(draftStarted({ ...emptyDraft(),
    events: [{ event_type: 'lps', start_date: '2026-01-02', end_date: '2026-01-03' }] }), true);
  assert.equal(draftStarted({ ...emptyDraft(), triggerDate: '2026-01-09' }), true);
  // After a clear, back to not-started (drives the readout going silent again).
  const cleared = markingReducer(
    initialMarkingState({ ...emptyDraft(), resistance: 12 }, 'F'), { type: 'clear' });
  assert.equal(draftStarted(cleared.draft), false);
});

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

// ---- saveNeeds: the itemized draftComplete (command-band readout) -----------

test('saveNeeds is empty exactly when draftComplete is true (box)', () => {
  const empty = emptyDraft();
  assert.deepEqual(saveNeeds(empty), ['resistance', 'support', 'span']);
  assert.equal(draftComplete(empty), false);
  // rails placed with anchors -> span is derivable, so only rails were needed.
  const withRails = { ...empty, resistance: 12, support: 10,
    rAnchorDate: '2026-01-05', sAnchorDate: '2026-01-02' };
  assert.deepEqual(saveNeeds(withRails), []);
  assert.equal(draftComplete(withRails), true);
  // rails but no anchors and no explicit span -> still needs span.
  const noSpan = { ...empty, resistance: 12, support: 10 };
  assert.deepEqual(saveNeeds(noSpan), ['span']);
  assert.equal(draftComplete(noSpan), false);
});

test('saveNeeds is empty for negatives (no geometry to require)', () => {
  assert.deepEqual(saveNeeds({ ...emptyDraft(), verdict: 'no_structure' }), []);
  assert.deepEqual(saveNeeds({ ...emptyDraft(), verdict: 'engine_wrong' }), []);
});

// ---- the Trigger (buy): assisted snap, manual override, re-mark -------------

// A draft that already carries an LPS ending 2026-04-14 (the anchor for the
// trigger). Frozen forward bars clear the 10.5 LPS-high on 2026-04-16.
const lpsDraft = () => ({
  ...emptyDraft(),
  events: [{ event_type: 'lps', start_date: '2026-04-08', end_date: '2026-04-14',
             tip_date: null, tip_price: null, source: 'operator' }],
});
const CANDLES = [
  { time: '2026-04-08', high: 10.0, low: 9.6 },
  { time: '2026-04-14', high: 10.5, low: 10.1 }, // LPS END -> level 10.5
  { time: '2026-04-15', high: 10.4, low: 10.0 }, // as-of, below the level
  { time: '2026-04-16', high: 10.7, low: 10.2 }, // first bar clearing 10.5
  { time: '2026-04-17', high: 11.0, low: 10.5 },
];

test('snapTrigger: LPS end-bar High is the level; first clearing bar is the date', () => {
  assert.deepEqual(snapTrigger(lpsDraft(), CANDLES),
    { date: '2026-04-16', price: 10.5 });
});

test('snapTrigger: no as-of floor — a breakout BEFORE the snapshot still snaps (relaxed)', () => {
  // The breakout clears the LPS high on 2026-04-16, well before this late as-of.
  // Old behavior skipped pre-as-of bars; now the snap lands on the real breakout.
  const lateBars = [...CANDLES, { time: '2026-05-01', high: 12.0, low: 11.0 }];
  assert.deepEqual(snapTrigger(lpsDraft(), lateBars),
    { date: '2026-04-16', price: 10.5 });
});

test('snapTrigger returns null without an LPS, or with no bar clearing the level', () => {
  assert.equal(snapTrigger(emptyDraft(), CANDLES), null); // no LPS
  // A level nothing clears (raise the LPS high above every forward High).
  const highLps = { ...lpsDraft(),
    events: [{ event_type: 'lps', start_date: '2026-04-08', end_date: '2026-04-14' }] };
  const flat = CANDLES.map((b) => (b.time === '2026-04-14' ? { ...b, high: 99 } : b));
  assert.equal(snapTrigger(highLps, flat), null);
});

test('the Trigger tool is inert until an LPS exists, armable once it does', () => {
  let s = initialMarkingState(emptyDraft(), 'F');
  s = markingReducer(s, { type: 'tool', tool: 'trigger' });
  assert.equal(s.tool, 'idle');                 // no LPS -> stays idle
  s = initialMarkingState(lpsDraft(), 'F');
  s = markingReducer(s, { type: 'tool', tool: 'trigger' });
  assert.equal(s.tool, 'trigger');              // with an LPS -> arms
});

test('set-trigger stores/clears; it is box-only', () => {
  let s = initialMarkingState(lpsDraft(), 'F');
  s = markingReducer(s, { type: 'set-trigger', date: '2026-04-16', price: 10.5 });
  assert.equal(s.draft.triggerDate, '2026-04-16');
  assert.equal(s.draft.triggerPrice, 10.5);
  assert.equal(s.draft.triggerSource, 'assisted');
  s = markingReducer(s, { type: 'set-trigger', date: null });   // clear
  assert.equal(s.draft.triggerDate, null);
  assert.equal(s.draft.triggerSource, null);
  // A negative draft refuses a trigger entirely.
  const neg = markingReducer(initialMarkingState({ ...emptyDraft(), verdict: 'no_structure' }, 'F'),
    { type: 'set-trigger', date: '2026-04-16', price: 10.5 });
  assert.equal(neg.draft.triggerDate, null);
});

test('a manual click on the armed Trigger tool places the buy and disarms', () => {
  let s = initialMarkingState(lpsDraft(), 'F');
  s = markingReducer(s, { type: 'tool', tool: 'trigger' });
  s = markingReducer(s, { type: 'chart-click', date: '2026-04-17', price: 10.9,
                          bar: { high: 11.0, low: 10.5 } });
  assert.equal(s.draft.triggerDate, '2026-04-17');
  assert.equal(s.draft.triggerPrice, 11.0);      // snaps to the clicked bar's High
  assert.equal(s.draft.triggerSource, 'manual');
  assert.equal(s.tool, 'idle');
});

test('re-arming the Trigger tool is idempotent (toggles off cleanly)', () => {
  let s = initialMarkingState(lpsDraft(), 'F');
  s = markingReducer(s, { type: 'tool', tool: 'trigger' });
  s = markingReducer(s, { type: 'tool', tool: 'trigger' }); // re-arm == disarm
  assert.equal(s.tool, 'idle');
});

test('draftFromMark loads a saved trigger as MANUAL; markPayloadFromDraft echoes it', () => {
  const mark = { verdict: 'box', resistance: 12, support: 10,
    box_start_date: '2026-03-01', box_end_date: '2026-04-15',
    trigger_date: '2026-04-16', trigger_price: 10.5,
    events: [{ event_type: 'lps', start_date: '2026-04-08', end_date: '2026-04-14' }] };
  const draft = draftFromMark(mark);
  assert.equal(draft.triggerDate, '2026-04-16');
  assert.equal(draft.triggerPrice, 10.5);
  assert.equal(draft.triggerSource, 'manual'); // never silently re-derived on edit
  const chart = { ticker: 'X', as_of_session: '2026-04-15', data_regime: 'as_traded',
    engine_config_version: 'cfg', anchor_close: 11, frame_digest: 'd' };
  const payload = markPayloadFromDraft(draft, chart);
  assert.equal(payload.trigger_date, '2026-04-16');
  assert.equal(payload.trigger_price, 10.5);
  // A negative draft persists NO trigger, even if fields lingered.
  const negPayload = markPayloadFromDraft(
    { ...draft, verdict: 'no_structure' }, chart);
  assert.equal(negPayload.trigger_date, null);
  assert.equal(negPayload.trigger_price, null);
});

test('switching a triggered box to a negative drops the trigger', () => {
  let s = initialMarkingState(lpsDraft(), 'F');
  s = markingReducer(s, { type: 'set-trigger', date: '2026-04-16', price: 10.5 });
  s = markingReducer(s, { type: 'verdict', verdict: 'engine_wrong' });
  assert.equal(s.draft.triggerDate, null);
  assertInvariants(s, 'triggered box -> negative');
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
  const tools = ['rail-r', 'rail-s', 'span', 'event:phase_c', 'event:lps',
                 'event:spring_test', 'trigger'];
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
