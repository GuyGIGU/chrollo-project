import test from 'node:test';
import assert from 'node:assert/strict';
import {
  chartTimeToIso,
  draftComplete,
  duplicateConflictId,
  effectiveSpan,
  emptyDraft,
  frameKeyOf,
  initialMarkingState,
  markPayloadFromDraft,
  markingReducer,
  snapRailPrice,
  statusText,
} from './calibrationMarking.js';

const click = (date, price) => ({ type: 'chart-click', date, price });

test('rail clicks record price AND anchor bar; the span derives from anchors', () => {
  let s = markingReducer(initialMarkingState(), { type: 'tool', tool: 'rail-r' });
  s = markingReducer(s, click('2026-02-10', 12.4));
  assert.deepEqual([s.draft.resistance, s.draft.rAnchorDate, s.draft.firstRail, s.tool],
                   [12.4, '2026-02-10', 'resistance', 'idle']);
  assert.ok(!draftComplete(s.draft));
  s = markingReducer(s, { type: 'tool', tool: 'rail-s' });
  s = markingReducer(s, click('2026-03-05', 10.15));
  assert.deepEqual([s.draft.support, s.draft.sAnchorDate], [10.15, '2026-03-05']);
  assert.ok(draftComplete(s.draft)); // rails + anchors = derivable span
  // Derived span: earlier anchor -> as-of session; explicit x-span wins.
  assert.deepEqual(effectiveSpan(s.draft, '2026-04-15'),
                   { start: '2026-02-10', end: '2026-04-15' });
  const explicit = { ...s.draft, boxStartDate: '2025-12-12', boxEndDate: '2026-04-01' };
  assert.deepEqual(effectiveSpan(explicit, '2026-04-15'),
                   { start: '2025-12-12', end: '2026-04-01' });
});

test('rails clicked in either order: R is always the upper one, anchors travel with prices', () => {
  // The operator clicks "R" on the LOW swing first (10.15@02-10), then "S"
  // lands on the higher swing — prices normalize, and the anchors plus the
  // first-marked label follow their prices so root-swing intent survives.
  let s = markingReducer(initialMarkingState(), { type: 'tool', tool: 'rail-r' });
  s = markingReducer(s, click('2026-02-10', 10.15));
  s = markingReducer(s, { type: 'tool', tool: 'rail-s' });
  s = markingReducer(s, click('2026-02-11', 12.4));
  assert.deepEqual(
    [s.draft.resistance, s.draft.rAnchorDate, s.draft.support, s.draft.sAnchorDate],
    [12.4, '2026-02-11', 10.15, '2026-02-10']);
  assert.equal(s.draft.firstRail, 'support'); // the first-marked extreme is now S
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

test('re-placing a rail moves its anchor too', () => {
  let s = markingReducer(initialMarkingState(), { type: 'tool', tool: 'rail-r' });
  s = markingReducer(s, click('2026-02-10', 12.4));
  s = markingReducer(s, { type: 'tool', tool: 'rail-r' });
  s = markingReducer(s, click('2026-03-01', 12.55));
  assert.deepEqual([s.draft.resistance, s.draft.rAnchorDate],
                   [12.55, '2026-03-01']);
  assert.equal(s.draft.firstRail, 'resistance'); // first-marked label is sticky
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
  let s = markingReducer(initialMarkingState(), { type: 'tool', tool: 'rail-r' });
  s = markingReducer(s, click('2026-02-10', 12.4));
  s = markingReducer(s, { type: 'verdict', verdict: 'no_structure' });
  assert.equal(s.draft.resistance, null);
  assert.equal(s.draft.rAnchorDate, null);
  assert.equal(s.draft.verdict, 'no_structure');
  assert.ok(draftComplete(s.draft)); // negatives are complete by definition
  const after = markingReducer(markingReducer(s, { type: 'tool', tool: 'rail-r' }),
                               click('2026-02-10', 12.4));
  assert.equal(after.draft.resistance, null); // clicks stay inert
});

test('clear resets the draft but keeps the frame binding', () => {
  let s = initialMarkingState({ ...emptyDraft(), resistance: 12.4 }, 'BODI|2026-04-15|abc');
  s = markingReducer(s, { type: 'clear' });
  assert.deepEqual([s.draft.resistance, s.frameKey], [null, 'BODI|2026-04-15|abc']);
});

test('duplicateConflictId surfaces a create collision for EXPLICIT resolution', () => {
  const dup = { detail: { class: 'duplicate_mark', existing_id: 42,
                          message: 'a mark for (BODI, 2026-04-15, \'\') already exists' } };
  // A blind create (no editingId) that collides yields the existing id — the
  // UI offers a one-click overwrite; it is NEVER applied automatically.
  assert.equal(duplicateConflictId(dup, null), 42);
  // An explicit edit is already a deliberate PUT — never treated as a conflict.
  assert.equal(duplicateConflictId(dup, 7), null);
  // Non-duplicate failures are not conflicts.
  assert.equal(duplicateConflictId({ detail: { class: 'invalid_mark' } }, null), null);
  // A duplicate the backend could not attach an id to is not auto-resolvable.
  assert.equal(duplicateConflictId({ detail: { class: 'duplicate_mark', existing_id: null } }, null), null);
  assert.equal(duplicateConflictId(null, null), null);
});

test('frameKeyOf binds ticker, session and digest', () => {
  assert.equal(
    frameKeyOf({ ticker: 'KLAC', as_of_session: '2025-09-05', frame_digest: 'd1' }),
    'KLAC|2025-09-05|d1');
  assert.equal(frameKeyOf(null), null);
});

test('statusText names the next placement', () => {
  let s = markingReducer(initialMarkingState(), { type: 'tool', tool: 'rail-r' });
  assert.match(statusText(s), /resistance/);
  s = markingReducer(s, { type: 'tool', tool: 'rail-s' });
  assert.match(statusText(s), /support/);
  s = markingReducer(s, { type: 'tool', tool: 'span' });
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

test('a load (frame change) resets editingId to null — a stale id cannot survive a scrub', () => {
  // The second footgun's backstop (Council Review 2026-07-12): after the UI
  // auto-clears on save, scrubbing to a new frame must NOT leave editingId set,
  // or the next save would silently PUT over the just-edited mark on a new frame.
  let s = initialMarkingState(null, 'BODI|2026-04-15|d1');
  s = markingReducer(s, { type: 'edit-mark', mark: { id: 9, verdict: 'box' } });
  assert.equal(s.editingId, 9);
  s = markingReducer(s, { type: 'load', frameKey: 'BODI|2026-04-14|d2', draft: null });
  assert.equal(s.editingId, null);       // the scrub forgot the edit target
  assert.equal(s.frameKey, 'BODI|2026-04-14|d2');
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
    [n.resistance, n.support, n.box_start_date, n.box_end_date,
     n.r_anchor_date, n.s_anchor_date, n.first_rail, n.events],
    [null, null, null, null, null, null, null, []]);
});

test('markPayloadFromDraft derives the span from anchors and echoes them', () => {
  const chartData = {
    ticker: 'YPF', as_of_session: '2026-05-18', data_regime: 'as_traded',
    engine_config_version: 'cfg', anchor_close: 47.48, frame_digest: 'e'.repeat(64),
  };
  const draft = {
    ...emptyDraft(), resistance: 44.0, support: 41.35,
    rAnchorDate: '2026-04-08', sAnchorDate: '2026-04-15', firstRail: 'resistance',
  };
  const p = markPayloadFromDraft(draft, chartData, {});
  // start = the earlier anchor, end = the as-of session (never a hand-drawn
  // sliver again); anchors + first-marked rail ride along as provenance.
  assert.deepEqual([p.box_start_date, p.box_end_date], ['2026-04-08', '2026-05-18']);
  assert.deepEqual([p.r_anchor_date, p.s_anchor_date, p.first_rail],
                   ['2026-04-08', '2026-04-15', 'resistance']);
});
