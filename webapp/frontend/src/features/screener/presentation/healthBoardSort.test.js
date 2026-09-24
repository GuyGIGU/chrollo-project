import { test } from 'node:test';
import assert from 'node:assert/strict';

import {
  compareHealthMembers,
  sortHealthMembers,
  groupHealthMembers,
  KNOWN_STATE_COUNT,
} from './healthBoardSort.js';
import { HEALTH_STATE_ORDER } from './healthStateData.js';

const m = (ticker, state, extra = {}) => ({ ticker, state, ...extra });

test('full seven-bucket decision-proximity order', () => {
  // Deliberately shuffled input; one member per state.
  const members = [
    m('E', 'trending'),
    m('G', 'no_structure'),
    m('A', 'near_resistance', { box_pos: 0.9 }),
    m('F', 'deep_correction'),
    m('C', 'near_support', { box_pos: 0.1 }),
    m('B', 'post_breakout_markup', { breakout_extension: 0.02 }),
    m('D', 'consolidating'),
  ];
  const order = sortHealthMembers(members).map((x) => x.state);
  assert.deepEqual(order, [
    'near_resistance', 'post_breakout_markup', 'near_support',
    'consolidating', 'trending', 'deep_correction', 'no_structure',
  ]);
  // The comparator's bucket order is exactly the engine's closed-set order.
  assert.deepEqual(order, [...HEALTH_STATE_ORDER]);
  assert.equal(KNOWN_STATE_COUNT, 7);
});

test('near_resistance tiebreak: closest to the ceiling first', () => {
  const members = [
    m('LOW', 'near_resistance', { box_pos: 0.72 }),
    m('HIGH', 'near_resistance', { box_pos: 0.98 }),
    m('MID', 'near_resistance', { box_pos: 0.85 }),
  ];
  assert.deepEqual(sortHealthMembers(members).map((x) => x.ticker), ['HIGH', 'MID', 'LOW']);
});

test('near_support tiebreak: closest to the floor first', () => {
  const members = [
    m('HIGH', 'near_support', { box_pos: 0.28 }),
    m('LOW', 'near_support', { box_pos: 0.02 }),
    m('MID', 'near_support', { box_pos: 0.15 }),
  ];
  assert.deepEqual(sortHealthMembers(members).map((x) => x.ticker), ['LOW', 'MID', 'HIGH']);
});

test('post_breakout_markup tiebreak: freshest (smallest extension) first', () => {
  const members = [
    m('STALE', 'post_breakout_markup', { breakout_extension: 0.12 }),
    m('FRESH', 'post_breakout_markup', { breakout_extension: 0.01 }),
    m('MID', 'post_breakout_markup', { breakout_extension: 0.05 }),
  ];
  assert.deepEqual(sortHealthMembers(members).map((x) => x.ticker), ['FRESH', 'MID', 'STALE']);
});

test('missing tiebreak value sorts to the back of its own bucket, not another', () => {
  const members = [
    m('NULL', 'near_resistance', { box_pos: null }),
    m('REAL', 'near_resistance', { box_pos: 0.8 }),
  ];
  assert.deepEqual(sortHealthMembers(members).map((x) => x.ticker), ['REAL', 'NULL']);
});

test('unknown / missing state lands in the fallback bucket, after all known states', () => {
  const members = [
    m('MADE_UP', 'buy_now'),          // not in the closed set
    m('NONE', undefined),             // missing entirely
    m('REAL', 'near_resistance', { box_pos: 0.9 }),
  ];
  const order = sortHealthMembers(members).map((x) => x.ticker);
  assert.equal(order[0], 'REAL');                 // the known state leads
  assert.deepEqual(order.slice(1).sort(), ['MADE_UP', 'NONE']); // unknowns trail (ticker-stable)
});

test('final tiebreak is the ticker, so equal members are stable', () => {
  const members = [
    m('ZZZ', 'consolidating'),
    m('AAA', 'consolidating'),
    m('MMM', 'consolidating'),
  ];
  assert.deepEqual(sortHealthMembers(members).map((x) => x.ticker), ['AAA', 'MMM', 'ZZZ']);
  // Comparator is antisymmetric on the ticker tiebreak.
  assert.ok(compareHealthMembers(members[1], members[0]) < 0);
});

test('distinct unknown states collapse into ONE fallback band (stable key, no fragmentation)', () => {
  // Defense-in-depth: even if two unrecognized states reach the FE, they must not
  // fragment into multiple "Unrecognized" bands with colliding React keys.
  const members = [
    m('A', 'future_x'),
    m('B', 'future_y'),
    m('C', 'future_x'),
    m('R', 'near_resistance', { box_pos: 0.9 }),
  ];
  const bands = groupHealthMembers(members);
  const unknownBands = bands.filter((b) => b.key === 'unknown');
  assert.equal(unknownBands.length, 1);                 // one band, not three
  assert.equal(unknownBands[0].members.length, 3);      // all unknowns together
  const keys = bands.map((b) => b.key);
  assert.equal(new Set(keys).size, keys.length);        // no duplicate React keys
});

test('groupHealthMembers yields ordered bands with counts', () => {
  const members = [
    m('A', 'near_resistance', { box_pos: 0.9 }),
    m('B', 'near_resistance', { box_pos: 0.95 }),
    m('C', 'deep_correction'),
  ];
  const bands = groupHealthMembers(members);
  assert.deepEqual(bands.map((b) => [b.key, b.members.length]), [
    ['near_resistance', 2],
    ['deep_correction', 1],
  ]);
  // Within-band order follows the rail-proximity tiebreak.
  assert.deepEqual(bands[0].members.map((x) => x.ticker), ['B', 'A']);
});
