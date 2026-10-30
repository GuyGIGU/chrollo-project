// The page-level key guard (item 7): the '?' sheet, '/', the screener card keys
// and the calibration list's Up/Down all ask it before acting.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  dialogOpen,
  dialogOpenOutside,
  hasCommandModifier,
  isPageKeystroke,
  isTypingTarget,
} from './keyboardGuard.js';

const ev = (over = {}) => ({
  key: 'j', target: { tagName: 'DIV' },
  ctrlKey: false, metaKey: false, altKey: false, shiftKey: false, ...over,
});

// A fake document that answers whether a dialog is up and records what it was asked.
const docWith = (hasDialog) => {
  const asked = [];
  return {
    asked,
    querySelector(selector) {
      asked.push(selector);
      return hasDialog ? { role: 'dialog' } : null;
    },
  };
};

test('isTypingTarget: fields and editable text are typing', () => {
  for (const tagName of ['INPUT', 'TEXTAREA', 'SELECT']) {
    assert.equal(isTypingTarget({ tagName }), true, tagName);
  }
  assert.equal(isTypingTarget({ tagName: 'DIV', isContentEditable: true }), true, 'contentEditable');
  // A focused card is a DIV/BUTTON-like target: its keys must stay live.
  for (const tagName of ['DIV', 'BUTTON', 'TR']) {
    assert.equal(isTypingTarget({ tagName }), false, tagName);
  }
  assert.equal(isTypingTarget(null), false);
  assert.equal(isTypingTarget(undefined), false);
});

test('hasCommandModifier: Ctrl/Cmd/Alt are shortcuts; Shift is not', () => {
  assert.equal(hasCommandModifier(ev({ ctrlKey: true })), true);
  assert.equal(hasCommandModifier(ev({ metaKey: true })), true);
  assert.equal(hasCommandModifier(ev({ altKey: true })), true);
  assert.equal(hasCommandModifier(ev({ shiftKey: true })), false, "'?' is Shift+/");
});

test('isPageKeystroke: false while typing, with a modifier, or with any dialog open', () => {
  assert.equal(isPageKeystroke(ev(), docWith(false)), true);
  assert.equal(isPageKeystroke(ev({ target: { tagName: 'INPUT' } }), docWith(false)), false);
  assert.equal(isPageKeystroke(ev({ ctrlKey: true }), docWith(false)), false);
  assert.equal(isPageKeystroke(ev({ key: 'J', shiftKey: true }), docWith(false)), true);
  const doc = docWith(true);
  assert.equal(isPageKeystroke(ev(), doc), false, 'a dialog owns its keys');
  assert.deepEqual(doc.asked, ['[role="dialog"]']);
});

test('dialogOpen: no document at all is no dialog', () => {
  assert.equal(dialogOpen(null), false);
  assert.equal(dialogOpen(docWith(false)), false);
  assert.equal(dialogOpen(docWith(true)), true);
});

// A fake document holding dialogs that each answer whether they contain an element.
// Each is MODAL (the lens, a Modal, the trade drawer) unless wrapped in nonModal()
// (the command bar's Filters/Data popovers, the Scale popover); it answers the
// selector the way a real document would.
const nonModal = (inside) => ({ inside, modal: false });
const docWithDialogs = (...members) => ({
  querySelectorAll(selector) {
    const modalOnly = selector === '[role="dialog"][aria-modal="true"]';
    assert.ok(modalOnly || selector === '[role="dialog"]', selector);
    return members
      .map((m) => (Array.isArray(m) ? { inside: m, modal: true } : m))
      .filter((m) => m.modal || !modalOnly)
      .map((m) => ({ contains: (el) => m.inside.includes(el) }));
  },
});

test('dialogOpenOutside: a card behind the big chart stands down; one inside a dialog does not', () => {
  const card = { tagName: 'DIV' };
  assert.equal(dialogOpenOutside(card, docWithDialogs()), false, 'no dialog');
  assert.equal(dialogOpenOutside(card, docWithDialogs([])), true, 'the lens is up, the card is behind it');
  assert.equal(dialogOpenOutside(card, docWithDialogs([card])), false, 'the card is inside the dialog');
  assert.equal(dialogOpenOutside(card, docWithDialogs([card], [])), true, 'a second dialog the card is not in');
  assert.equal(dialogOpenOutside(card, null), false, 'no document');
});

test('dialogOpenOutside: an open non-modal popover does not silence a card reached by Tab', () => {
  const card = { tagName: 'DIV' };
  assert.equal(dialogOpenOutside(card, docWithDialogs(nonModal([]))), false, 'the Filters popover is open');
  assert.equal(dialogOpenOutside(card, docWithDialogs(nonModal([]), [])), true, 'the popover AND the lens');
});

// The page keys stand down only for overlays that SAY they are dialogs. The trade
// drawer opens over every page from the alerts strip; unmarked, Down scrolled a
// screener card behind its scrim and '/' typed into the hidden search (review
// 2026-10-03). Pinned on the source, the way screenerModalPager pins the lens hosts.
test('the full-screen overlays that hold the keyboard are dialogs', async () => {
  const { readFileSync } = await import('node:fs');
  const read = (rel) => readFileSync(new URL(rel, import.meta.url), 'utf8');
  const drawer = read('../../features/journal/components/TradeDetailDrawer.jsx');
  assert.match(drawer, /<aside[^>]*role="dialog"[^>]*aria-modal="true"/);
  const review = read('../../features/watchlist/components/WeeklyReview.jsx');
  assert.match(review, /role="dialog" aria-modal="true" aria-label="Weekly review"/);
});

// ...and the page loops that act on them stand down under ANY dialog (review
// 2026-10-04): Enter on the Calibration 'Unsaved marks' confirm clicked Stay AND
// saved the draft; ↓ under the trade drawer swapped the Watchlist charts behind
// its scrim (the drawer does not take focus, so a closest() check never saw it).
test('the Calibration marking keys and the Watchlist arrows stand down under any dialog', async () => {
  const { readFileSync } = await import('node:fs');
  const read = (rel) => readFileSync(new URL(rel, import.meta.url), 'utf8');
  // The window keydown handler: from `const onKey =` to where it is installed.
  const handler = (src) => src.slice(src.indexOf('const onKey = '), src.indexOf("window.addEventListener('keydown', onKey)"));
  const guardedBefore = (src, guard, acts) => {
    const body = handler(src);
    const at = body.indexOf(guard);
    assert.ok(at > 0, `no stand-down: ${guard}`);
    for (const act of acts) assert.ok(body.indexOf(act) > at, `${act} runs before the stand-down`);
  };
  guardedBefore(read('../../features/calibration/components/CalibrationTab.jsx'),
    'if (!isMarkingKeystroke(e) || dialogOpen()) return;',
    ["dispatchMarking({ type: 'tool', tool })", 'keyDeps.current.save()']);
  guardedBefore(read('../../features/watchlist/components/WatchlistPage.jsx'),
    'if (!isPageKeystroke(event)) return;',
    ['event.preventDefault()', 'select(tickers[']);
});

// The calibration list's ↑/↓ keeps keyboard focus on the loaded row across a rail
// page turn: the old row unmounts and drops focus to <body> (review 2026-10-04).
test('the calibration rail carries a focused row across a page turn', async () => {
  const { readFileSync } = await import('node:fs');
  const rail = readFileSync(new URL('../../features/calibration/components/CalibrationRail.jsx', import.meta.url), 'utf8');
  const keydown = rail.slice(rail.indexOf('const onKey = '), rail.indexOf('pick(row.ticker, row.asOf);'));
  assert.match(keydown, /rowFocusRef\.current = focused\?\.tagName === 'TR' && Boolean\(railRef\.current\?\.contains\(focused\)\);/);
  assert.match(rail, /const rowLost = rowFocusRef\.current && focused === document\.body;/);
  assert.match(rail, /if \(activeRow && focused !== activeRow && \(rowHeld \|\| rowLost\)\) \{\s*activeRow\.focus\(/);
  assert.match(rail, /if \(activeRow\) rowFocusRef\.current = false;/);
});
