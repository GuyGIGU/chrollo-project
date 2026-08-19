// The Power-Play register projection (program Task 14): pure, node-tested.
// The wire status is server-derived and passed through (EC-28); unknown slugs
// render verbatim; numbers go through the HOUSE fx null-guard (utils/format —
// the register composes it, never re-declares it: 2026-08-17 review, Dodds);
// absent/malformed context — including a malformed ELEMENT — projects to an
// empty/shorter register, never a throw.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { fx } from '../utils/format.js';
import { powerPlayCounts, powerPlayRows, statusTail } from './powerPlayRegister.js';
import {
  POWER_PLAY_STATUS_LABELS,
  TREND_STATE_LABELS,
  powerPlayStatusLabel,
} from './wireVocabulary.js';

const CANDIDATE = {
  ticker: 'MAN', status: 'watched_ungraded',
  climax: '2026-07-17', ar: '2026-07-24', breakout: '2026-08-13',
  pole_gain: 1.119, depth: 0.122, clock: 10,
  first_legal_look: '2026-08-13',
};

test('absent or malformed context projects to an empty register', () => {
  assert.deepEqual(powerPlayRows(undefined), []);
  assert.deepEqual(powerPlayRows({}), []);
  assert.deepEqual(powerPlayRows({ power_play: { candidates: 'nope' } }), []);
  assert.equal(powerPlayCounts({}), null);
});

test('a malformed candidate ELEMENT drops instead of throwing', () => {
  const rows = powerPlayRows({ power_play: { candidates: [
    null, 'junk', 42, [CANDIDATE], CANDIDATE] } });
  assert.equal(rows.length, 1);
  assert.equal(rows[0].ticker, 'MAN');
});

test('a candidate projects with its signed label, tail, and plain facts', () => {
  const rows = powerPlayRows({ power_play: { candidates: [CANDIDATE] } });
  assert.equal(rows.length, 1);
  assert.equal(rows[0].ticker, 'MAN');
  assert.equal(rows[0].status, 'watched_ungraded');
  assert.equal(rows[0].statusLabel, 'Power Play — watched, ungraded');
  // Register rows open with the ticker, so they carry the label's TAIL —
  // the shared species prefix must not repeat as dead words on every line.
  assert.equal(rows[0].statusTail, 'watched, ungraded');
  assert.match(rows[0].meta, /climax 2026-07-17/);
  assert.match(rows[0].meta, /pole 112%/);
  assert.match(rows[0].meta, /depth 12\.2%/);
  assert.match(rows[0].meta, /clock 10/);
});

test('an unknown status slug renders verbatim, never blank', () => {
  assert.equal(powerPlayStatusLabel('some_future_state'), 'some_future_state');
  const rows = powerPlayRows({ power_play: { candidates: [
    { ...CANDIDATE, status: 'some_future_state' }] } });
  assert.equal(rows[0].statusLabel, 'some_future_state');
  assert.equal(rows[0].statusTail, 'some_future_state');   // no prefix: whole
});

test('null numbers are em-dashes through the house fx guard, never zeros', () => {
  assert.equal(fx(null, 1), '—');
  assert.equal(fx('not-a-number', 1), '—');
  assert.equal(fx(0, 1), '0.0');            // a measured zero SURVIVES
  const rows = powerPlayRows({ power_play: { candidates: [
    { ticker: 'X', status: 'refused_story', pole_gain: null }] } });
  assert.ok(!rows[0].meta.includes('pole'));
});

test('the wire vocabulary covers the server closed set + daily trend states', () => {
  // Mirrors evaluation.PP_WIRE_STATUS and market_structure.TREND_STATES.
  // The Python lane suite pins the wire tuple's EXACT contents, so a server
  // widening forces a conscious two-sided diff that lands HERE in the same
  // change (2026-08-17 review, Dodds/Fowler).
  assert.deepEqual(Object.keys(POWER_PLAY_STATUS_LABELS).sort(), [
    'fired', 'not_watched_clock', 'refused_occupancy', 'refused_story',
    'watched_ungraded']);
  for (const state of ['trending', 'correcting', 'consolidating', 'choppy']) {
    assert.ok(TREND_STATE_LABELS[state], `missing daily state ${state}`);
  }
});

test('counts pass through untouched — facts, never judgments', () => {
  const counts = { pp_watched: 3, pp_admitted_dark: 1 };
  assert.deepEqual(powerPlayCounts({ power_play: { counts } }), counts);
});

test('statusTail strips only the species prefix', () => {
  assert.equal(statusTail('Power Play — fired'), 'fired');
  assert.equal(statusTail('anything else'), 'anything else');
});
