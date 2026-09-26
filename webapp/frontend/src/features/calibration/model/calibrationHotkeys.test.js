import test from 'node:test';
import assert from 'node:assert/strict';
import { HOTKEY_TOOLS, isMarkingKeystroke } from './calibrationHotkeys.js';
import { MARK_EVENT_TYPES } from './calibrationMarking.js';

test('HOTKEY_TOOLS: the marking vocabulary, key for key', () => {
  assert.deepEqual(HOTKEY_TOOLS, {
    r: 'rail-r', s: 'rail-s', x: 'span',
    c: 'event:phase_c', l: 'event:lps', t: 'event:spring_test',
    o: 'event:sos', m: 'event:mini_consolidation', u: 'event:last_supper',
    b: 'trigger',
  });
});

test('HOTKEY_TOOLS: every event key arms an event type the reducer knows', () => {
  const events = Object.values(HOTKEY_TOOLS).filter((t) => t.startsWith('event:'));
  for (const tool of events) {
    assert.ok(MARK_EVENT_TYPES.includes(tool.slice('event:'.length)), tool);
  }
});

test('HOTKEY_TOOLS: e, Enter and Escape are not tools (engine peek, save, disarm)', () => {
  for (const k of ['e', 'enter', 'escape']) assert.equal(HOTKEY_TOOLS[k], undefined, k);
});

const press = (over = {}) => ({ key: 'r', target: { tagName: 'DIV' },
                                metaKey: false, ctrlKey: false, altKey: false, ...over });

test('isMarkingKeystroke: a bare key on the page is a marking command', () => {
  assert.equal(isMarkingKeystroke(press()), true);
  assert.equal(isMarkingKeystroke(press({ target: null })), true);
  assert.equal(isMarkingKeystroke(press({ target: { tagName: 'BUTTON' } })), true);
  assert.equal(isMarkingKeystroke(press({ shiftKey: true })), true); // Shift+R still arms R
});

test('isMarkingKeystroke: typing in a field is never a command', () => {
  for (const tagName of ['INPUT', 'SELECT', 'TEXTAREA']) {
    assert.equal(isMarkingKeystroke(press({ target: { tagName } })), false, tagName);
  }
});

test('isMarkingKeystroke: a modified key is a browser/OS shortcut, not a command', () => {
  assert.equal(isMarkingKeystroke(press({ metaKey: true })), false);
  assert.equal(isMarkingKeystroke(press({ ctrlKey: true })), false);
  assert.equal(isMarkingKeystroke(press({ altKey: true })), false);
});
