// Council review 2026-09-07, finding 8: in-app navigation destroyed unsaved
// calibration marks — the guard covered reload and tab close, not a click on the
// top nav — and it was armed only on a COMPLETE box, so a placed rail with the
// LPS still pending was unprotected even on a real reload.
import { test, beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import {
  armLeaveGuard,
  confirmLeave,
  confirmLeaveWithDialog,
  disarmLeaveGuard,
  leaveGuardMessage,
  shouldInterceptNavClick,
} from './leaveGuard.js';
import { getFeedbackState, settleConfirm } from '../components/feedback.js';
import {
  draftComplete,
  draftFromMark,
  draftHasUnsavedWork,
  emptyDraft,
  initialMarkingState,
  markingReducer,
} from '../../features/calibration/model/calibrationMarking.js';

const click = (over = {}) => ({
  defaultPrevented: false, button: 0, metaKey: false, ctrlKey: false,
  shiftKey: false, altKey: false, ...over,
});

beforeEach(() => disarmLeaveGuard());

test('an unarmed guard never touches a navigation', async () => {
  assert.equal(leaveGuardMessage(), null);
  assert.equal(shouldInterceptNavClick(click()), false);
  let asked = 0;
  assert.equal(await confirmLeave(() => { asked += 1; return false; }), true);
  assert.equal(asked, 0, 'an unarmed guard must not prompt');
});

test('an armed guard intercepts the click and a "Stay" answer blocks the nav', async () => {
  armLeaveGuard('marks unsaved');
  assert.equal(shouldInterceptNavClick(click()), true);
  const seen = [];
  assert.equal(await confirmLeave((message) => { seen.push(message); return false; }), false);
  assert.deepEqual(seen, ['marks unsaved'], 'the operator is told what he would lose');
});

test('an armed guard lets the nav through once the operator confirms', async () => {
  armLeaveGuard('marks unsaved');
  assert.equal(await confirmLeave(() => true), true);
  // …and an async dialog (the app uses a promise-based confirm) works too.
  assert.equal(await confirmLeave(() => Promise.resolve(true)), true);
});

test('modified and non-primary clicks are left alone', () => {
  armLeaveGuard('marks unsaved');
  for (const over of [
    { metaKey: true }, { ctrlKey: true }, { shiftKey: true }, { altKey: true },
    { button: 1 }, { defaultPrevented: true },
  ]) {
    assert.equal(shouldInterceptNavClick(click(over)), false, JSON.stringify(over));
  }
});

test('the tab you are already on is not an exit, so it never prompts', () => {
  // Answering "Leave and discard" there discarded nothing and navigated
  // nowhere — a prompt with no consequence teaches the operator to dismiss the
  // one that matters (council review 2026-09-07, A9).
  armLeaveGuard('marks unsaved');
  assert.equal(shouldInterceptNavClick(click(), '/calibration', '/calibration'), false);
  assert.equal(shouldInterceptNavClick(click(), '/calibration/', '/calibration'), false);
  assert.equal(shouldInterceptNavClick(click(), '/screener', '/calibration'), true);
  // The route is optional — an exit that cannot name it still gets guarded.
  assert.equal(shouldInterceptNavClick(click(), null, '/calibration'), true);
});

test('the bound form asks through the app dialog and honours the answer', async () => {
  armLeaveGuard('marks unsaved');
  const answer = confirmLeaveWithDialog();
  const pending = getFeedbackState().confirm;
  assert.ok(pending, 'no dialog was raised — the exit would discard silently');
  assert.equal(pending.message, 'marks unsaved');
  settleConfirm(false);
  assert.equal(await answer, false);
});

test('BOTH exits out of a route go through that one bound form', () => {
  // A wiring pin, not a behaviour test: `+ New trade` navigates to the journal
  // and shipped with no guard at all, so one click inches from the nav tabs
  // still discarded hand-drawn marks (council review 2026-09-07, A2). There is
  // no renderer in this suite, so the check is on the source — a real one is
  // the operator clicking the button.
  const src = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
  for (const file of [['app', 'components', 'AppTopbar.jsx'], ['app', 'components', 'AppShell.jsx']]) {
    const text = fs.readFileSync(path.join(src, ...file), 'utf8');
    assert.match(text, /confirmLeaveWithDialog\(\)/, `${file[1]} navigates without asking`);
  }
});

test('disarming releases the guard', async () => {
  armLeaveGuard('marks unsaved');
  disarmLeaveGuard();
  assert.equal(shouldInterceptNavClick(click()), false);
  assert.equal(await confirmLeave(() => false), true);
});

const railClick = (date, price) => ({
  type: 'chart-click', date, price, bar: { high: price, low: price },
});

test('a rails-placed, LPS-pending draft is drawn work the old arming missed', () => {
  // The old guard armed on draftComplete, so rails-placed-but-span-pending was
  // unprotected even on a real reload. Drive it through the real reducer.
  let state = markingReducer(initialMarkingState(), { type: 'tool', tool: 'rail-r' });
  assert.equal(draftHasUnsavedWork(state), false, 'arming a tool is not drawn work');
  state = markingReducer(state, railClick('2026-02-10', 101.5));

  assert.equal(draftComplete(state.draft), false);   // the old condition: unguarded
  assert.equal(draftHasUnsavedWork(state), true);    // the new one: guarded
});

test('a pristine page arms nothing, so the guard never nags', () => {
  assert.equal(draftHasUnsavedWork(initialMarkingState()), false);
  assert.equal(draftHasUnsavedWork(null), false);
});

test('a saved mark auto-loaded for correction is not unsaved work until it is touched', () => {
  // Opening any already-marked setup populates a full draft. Arming on that
  // would nag on every hop of a marking sitting, so `pristine` gates it.
  const mark = { id: 9, verdict: 'box', resistance: 12.4, support: 10.15,
                 r_anchor_date: '2026-02-10', s_anchor_date: '2026-03-05', events: [] };
  let state = markingReducer(initialMarkingState(), { type: 'edit-mark', mark });
  assert.deepEqual(state.draft, draftFromMark(mark));
  assert.equal(draftComplete(state.draft), true);    // the old condition: nagged
  assert.equal(draftHasUnsavedWork(state), false);   // the new one: silent

  // …and the moment the operator moves a rail it becomes unsaved work.
  state = markingReducer(state, { type: 'tool', tool: 'rail-s' });
  assert.equal(draftHasUnsavedWork(state), false, 'a tool switch is not an edit');
  state = markingReducer(state, railClick('2026-03-06', 10.3));
  assert.equal(draftHasUnsavedWork(state), true);
});

test('the app re-deriving the assisted trigger is not the operator touching it', () => {
  // Opening a saved mark whose stored assisted trigger disagrees with a fresh
  // snap makes the app dispatch set-trigger on its own. Without `auto` that
  // moved the draft and armed the guard on a mark he never touched — the exact
  // nagging `pristine` exists to prevent (council review 2026-09-07, A9).
  const mark = { id: 9, verdict: 'box', resistance: 12.4, support: 10.15,
                 r_anchor_date: '2026-02-10', s_anchor_date: '2026-03-05', events: [] };
  let state = markingReducer(initialMarkingState(), { type: 'edit-mark', mark });

  state = markingReducer(state, { type: 'set-trigger', date: '2026-03-09',
                                  price: 12.5, source: 'assisted', auto: true });
  assert.equal(state.draft.triggerDate, '2026-03-09', 'the re-derive still lands');
  assert.equal(draftHasUnsavedWork(state), false, 'a machine re-derive must not nag');

  // The same action from the operator's own hand (he armed the trigger tool)
  // IS unsaved work.
  state = markingReducer(state, { type: 'set-trigger', date: '2026-03-10',
                                  price: 12.6, source: 'assisted' });
  assert.equal(draftHasUnsavedWork(state), true);
});

test('a chosen negative verdict is unsaved work too', () => {
  // It carries no geometry, so draftStarted alone would let it go silently.
  const state = markingReducer(initialMarkingState(), { type: 'verdict', verdict: 'no_structure' });
  assert.equal(state.draft.verdict, 'no_structure');
  assert.equal(draftHasUnsavedWork(state), true);
  assert.equal(emptyDraft().verdict, 'box');   // the default is never "work"
});

test('a draft stashed on one frame is still unsaved work when the eye comes back', () => {
  let state = markingReducer(initialMarkingState(), { type: 'tool', tool: 'rail-r' });
  state = markingReducer(state, railClick('2026-02-10', 101.5));
  const stashed = { draft: state.draft, editingId: state.editingId, pristine: state.pristine };

  const elsewhere = markingReducer(state, { type: 'load', frameKey: 'OTHER', draft: null });
  assert.equal(draftHasUnsavedWork(elsewhere), false);

  const back = markingReducer(elsewhere, {
    type: 'load', frameKey: 'HOME', draft: stashed.draft,
    editingId: stashed.editingId, pristine: stashed.pristine,
  });
  assert.equal(draftHasUnsavedWork(back), true);
});
