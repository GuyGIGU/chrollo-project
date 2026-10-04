// Operator 2026-10-03, "no dead Prev/Next": the lens draws Prev and Next only
// where its host can step, so no mount shows two buttons that do nothing. A
// source contract, like app/appearance/uiScale.test.js: there is no DOM harness.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const srcDir = join(dirname(fileURLToPath(import.meta.url)), '..', '..');
const read = (rel) => readFileSync(join(srcDir, rel), 'utf8');

test('the lens draws Prev and Next only when it is handed a stepper', () => {
  const src = read('shared/setup/ScreenerModalToolbar.jsx');   // the lens's top bar
  assert.match(src, /\{onPrev && \(?\s*<button\b[^>]*\bonClick=\{onPrev\}[^>]*>\s*Prev\s*<\/button>\s*\)?\}/);
  assert.match(src, /\{onNext && \(?\s*<button\b[^>]*\bonClick=\{onNext\}[^>]*>\s*Next\s*<\/button>\s*\)?\}/);
});

test('no host hands the lens a do-nothing Prev/Next', () => {
  const hosts = readdirSync(srcDir, { recursive: true })
    .map((f) => f.split('\\').join('/'))
    .filter((f) => f.endsWith('.jsx') && read(f).includes('<ScreenerModal'));
  // Vacuity: the walk must reach the mounts this rule is about.
  assert.ok(hosts.includes('features/archive/components/ArchiveTab.jsx'), hosts.join(', '));
  assert.ok(hosts.includes('features/screener/components/ScreenerGrid.jsx'), hosts.join(', '));
  for (const f of hosts) {
    assert.doesNotMatch(read(f), /\bon(?:Prev|Next)=\{\(\)\s*=>\s*\{\s*\}\}/, f);
  }
});

test('the hosts that can step still hand the lens their steppers', () => {
  const grid = read('features/screener/components/ScreenerGrid.jsx');
  assert.match(grid, /const canStep = canStepLens\(modalTickers, activeModalTicker\);/);
  assert.match(grid, /if \(!activeModalTicker \|\| !canStep\) return;/, 'the arrows step only where the buttons are drawn');
  assert.match(grid, /onNext=\{canStep \? handleNextModal : undefined\}\s*onPrev=\{canStep \? handlePrevModal : undefined\}/);
  const review = read('features/watchlist/components/WeeklyReview.jsx');
  const mount = review.slice(review.indexOf('<ScreenerModal'));
  assert.match(mount, /\bonPrev=\{onPrev\}/);
  assert.match(mount, /\bonNext=\{onNext\}/);
});

// Escape closes the lens through ONE listener, the lens's own. The grid's close POPS the
// history entry its open pushed; a second Escape closer on the same keystroke popped
// twice, and Escape on the Screener's big chart landed on Home (live check 2026-10-04).
// The WHOLE grid is scanned: a second keydown effect is a second closer just as much as a
// line in the arrow handler is.
test('one Escape closer per lens: the grid leaves Escape to the lens', () => {
  const lens = read('shared/setup/ScreenerModal.jsx');
  assert.match(lens, /if \(event\.key === 'Escape'\) onClose\?\.\(\);/, "the lens's own Escape listener");
  const grid = read('features/screener/components/ScreenerGrid.jsx');
  assert.match(grid, /\bonClose=\{closeModal\}/, 'the grid hands the lens its close by reference');
  assert.doesNotMatch(grid, /['"`]Esc(?:ape)?['"`]/, 'an Escape key check in the grid');
  assert.doesNotMatch(grid, /\bcloseModal\s*\(/, 'the grid calling its close itself');
});

// Closing lands on the card the lens last DREW. Keyed on ?t=, a close that popped back to an
// address naming a chart the lens cannot draw (F5 once it left the scan) never landed.
test('the close lands from the lens on screen, not from the address', () => {
  const grid = read('features/screener/components/ScreenerGrid.jsx');
  assert.match(grid, /const lensTicker = activeModalTicker && modalChart\[activeModalTicker\] \? activeModalTicker : null;/);
  const from = grid.slice(grid.indexOf('const lensTickerRef = useRef(null);'));
  const landing = from.slice(0, from.indexOf('return ('));
  assert.ok(landing.includes('card.focus('), 'vacuity: this is the landing effect');
  assert.match(landing, /if \(lensTicker\) \{\s*lensTickerRef\.current = lensTicker;/);
  assert.match(landing, /\}, \[lensTicker, drilldown, currentPage, pageOf, setCurrentPage\]\);/);
  assert.doesNotMatch(landing, /activeModalTicker/, 'the landing reads the lens drawn, never ?t=');
});
