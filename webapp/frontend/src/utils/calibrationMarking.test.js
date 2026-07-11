import test from 'node:test';
import assert from 'node:assert/strict';
import {
  chartTimeToIso,
  draftComplete,
  emptyDraft,
  frameKeyOf,
  initialMarkingState,
  markPayloadFromDraft,
  markingReducer,
  nextBoxNeed,
  snapRailPrice,
  statusText,
} from './calibrationMarking.js';

const click = (date, price) => ({ type: 'chart-click', date, price });

test('progressive box tool: R, S, span start, span end — then idle', () => {
  let s = markingReducer(initialMarkingState(), { type: 'tool', tool: 'box' });
  s = markingReducer(s, click('2026-02-10', 12.4));
  assert.equal(s.draft.resistance, 12.4);
  assert.equal(nextBoxNeed(s.draft), 'support');
  s = markingReducer(s, click('2026-02-11', 10.15));
  assert.equal(s.draft.support, 10.15);
  s = markingReducer(s, click('2025-12-12', 11));
  assert.equal(s.spanAnchor, '2025-12-12');
  s = markingReducer(s, click('2026-04-15', 11));
  assert.deepEqual(
    [s.draft.boxStartDate, s.draft.boxEndDate, s.tool, s.spanAnchor],
    ['2025-12-12', '2026-04-15', 'idle', null]);
  assert.ok(draftComplete(s.draft));
});

test('rails clicked in either order: R is always the upper one', () => {
  let s = markingReducer(initialMarkingState(), { type: 'tool', tool: 'box' });
  s = markingReducer(s, click('2026-02-10', 10.15)); // lower first
  s = markingReducer(s, click('2026-02-11', 12.4));
  assert.equal(s.draft.resistance, 12.4);
  assert.equal(s.draft.support, 10.15);
});

test('span clicked backwards is ordered', () => {
  let s = markingReducer(initialMarkingState(), { type: 'tool', tool: 'span' });
  s = markingReducer(s, click('2026-04-15', 11));
  s = markingReducer(s, click('2025-12-12', 11));
  assert.equal(s.draft.boxStartDate, '2025-12-12');
  assert.equal(s.draft.boxEndDate, '2026-04-15');
});

test('single-rail tools re-place one rail and disarm', () => {
  let s = initialMarkingState({ ...emptyDraft(), resistance: 12.4, support: 10.15 });
  s = markingReducer(s, { type: 'tool', tool: 'rail-s' });
  s = markingReducer(s, click('2026-03-01', 10.3));
  assert.deepEqual([s.draft.support, s.tool], [10.3, 'idle']);
});

test('event tool: two ordered clicks append a typed event', () => {
  let s = markingReducer(initialMarkingState(), { type: 'tool', tool: 'event:phase_c' });
  s = markingReducer(s, click('2026-03-20', 7));
  s = markingReducer(s, click('2026-02-10', 8));
  assert.equal(s.draft.events.length, 1);
  const e = s.draft.events[0];
  assert.deepEqual(
    [e.event_type, e.start_date, e.end_date, e.source],
    ['phase_c', '2026-02-10', '2026-03-20', 'operator']);
  const removed = markingReducer(s, { type: 'remove-event', index: 0 });
  assert.equal(removed.draft.events.length, 0);
});

test('idle clicks are no-ops; re-selecting a tool disarms it', () => {
  const s0 = initialMarkingState();
  assert.equal(markingReducer(s0, click('2026-01-05', 10)), s0);
  let s = markingReducer(s0, { type: 'tool', tool: 'span' });
  s = markingReducer(s, { type: 'tool', tool: 'span' });
  assert.equal(s.tool, 'idle');
});

test('switching tools drops a half-placed span anchor', () => {
  let s = markingReducer(initialMarkingState(), { type: 'tool', tool: 'span' });
  s = markingReducer(s, click('2026-01-05', 10));
  assert.equal(s.spanAnchor, '2026-01-05');
  s = markingReducer(s, { type: 'tool', tool: 'rail-r' });
  assert.equal(s.spanAnchor, null);
});

test('negative verdict drops all geometry and ignores chart clicks', () => {
  let s = markingReducer(initialMarkingState(), { type: 'tool', tool: 'box' });
  s = markingReducer(s, click('2026-02-10', 12.4));
  s = markingReducer(s, { type: 'verdict', verdict: 'no_structure' });
  assert.equal(s.draft.resistance, null);
  assert.equal(s.draft.verdict, 'no_structure');
  assert.ok(draftComplete(s.draft)); // negatives are complete by definition
  const after = markingReducer(markingReducer(s, { type: 'tool', tool: 'box' }),
                               click('2026-02-10', 12.4));
  assert.equal(after.draft.resistance, null); // clicks stay inert
});

test('clear resets the draft but keeps the frame binding', () => {
  let s = initialMarkingState({ ...emptyDraft(), resistance: 12.4 }, 'BODI|2026-04-15|abc');
  s = markingReducer(s, { type: 'clear' });
  assert.deepEqual([s.draft.resistance, s.frameKey], [null, 'BODI|2026-04-15|abc']);
});

test('frameKeyOf binds ticker, session and digest', () => {
  assert.equal(
    frameKeyOf({ ticker: 'KLAC', as_of_session: '2025-09-05', frame_digest: 'd1' }),
    'KLAC|2025-09-05|d1');
  assert.equal(frameKeyOf(null), null);
});

test('statusText names the next placement', () => {
  let s = markingReducer(initialMarkingState(), { type: 'tool', tool: 'box' });
  assert.match(statusText(s), /resistance/);
  s = markingReducer(s, click('2026-02-10', 12.4));
  assert.match(statusText(s), /support/);
  s = markingReducer(s, click('2026-02-11', 10.15));
  assert.match(statusText(s), /START bar/);
  s = markingReducer(s, click('2025-12-12', 11));
  assert.match(statusText(s), /END bar/);
});

test('chartTimeToIso accepts string, business day and unix forms', () => {
  assert.equal(chartTimeToIso('2026-04-15'), '2026-04-15');
  assert.equal(chartTimeToIso({ year: 2026, month: 4, day: 5 }), '2026-04-05');
  assert.equal(chartTimeToIso(1765497600), '2025-12-12');
  assert.equal(chartTimeToIso(undefined), null);
});

test('rails snap to the clicked bar extreme (wick to wick)', () => {
  const bar = { high: 96.2, low: 92.8 };
  assert.equal(snapRailPrice(95.7, bar), 96.2);  // nearer the high
  assert.equal(snapRailPrice(93.9, bar), 92.8);  // nearer the low
  assert.equal(snapRailPrice(95.7, null), 95.7); // no bar data: raw stands
  let s = markingReducer(initialMarkingState(), { type: 'tool', tool: 'rail-r' });
  s = markingReducer(s, { type: 'chart-click', date: '2026-02-10',
                          price: 95.7, bar });
  assert.equal(s.draft.resistance, 96.2);
});

test('edit-mark loads a saved mark and remembers its id; clear forgets it', () => {
  const mark = {
    id: 7, verdict: 'box', resistance: 12.4, support: 10.15,
    box_start_date: '2025-12-12', box_end_date: '2026-04-15',
    events: [{ event_type: 'lps', start_date: '2026-04-09',
               end_date: '2026-04-15', tip_date: null, tip_price: null,
               source: 'operator' }],
  };
  let s = initialMarkingState(null, 'BODI|2026-04-15|d1');
  s = markingReducer(s, { type: 'edit-mark', mark });
  assert.equal(s.editingId, 7);
  assert.equal(s.draft.resistance, 12.4);
  assert.equal(s.draft.events[0].event_type, 'lps');
  assert.equal(s.frameKey, 'BODI|2026-04-15|d1'); // still bound to the frame
  s = markingReducer(s, { type: 'clear' });
  assert.equal(s.editingId, null);
});

test('markPayloadFromDraft echoes identity and provenance from the chart payload', () => {
  const chartData = {
    ticker: 'KLAC', as_of_session: '2025-09-05', data_regime: 'as_traded',
    engine_config_version: 'cfg', anchor_close: 90.51, frame_digest: 'd'.repeat(64),
  };
  const draft = {
    verdict: 'box', resistance: 96.2, support: 87.7,
    boxStartDate: '2025-07-18', boxEndDate: '2025-09-05',
    events: [],
  };
  const p = markPayloadFromDraft(draft, chartData, { label: ' LPS ', note: ' x ' });
  assert.equal(p.as_of_date, '2025-09-05'); // the RESOLVED session — never raw input
  assert.equal(p.frame_digest, 'd'.repeat(64));
  assert.equal(p.label, 'lps');
  assert.equal(p.note, 'x');
  assert.equal(p.rails_source, 'operator');
  // A negative payload carries NO geometry, whatever the draft held.
  const n = markPayloadFromDraft({ ...draft, verdict: 'no_structure' }, chartData, {});
  assert.deepEqual(
    [n.resistance, n.support, n.box_start_date, n.box_end_date, n.events],
    [null, null, null, null, []]);
});
