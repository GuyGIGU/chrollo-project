// Tab titles (operator suggestion 6, 2026-10-03): every tab names its page, and
// what it is looking at, so two screens of Chrollo tabs can be told apart. One
// owner per route writes it; the owner list is pinned against the top nav so a
// new page cannot ship untitled and a second writer cannot fight the first.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { APP_TITLE, documentTitle } from './documentTitle.js';

const srcDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
const read = (rel) => fs.readFileSync(path.join(srcDir, rel), 'utf8');

// The one component per page that calls useDocumentTitle, keyed by its nav label.
const OWNERS = {
  Home: 'features/home/HomeRoute.jsx',
  Portfolio: 'features/portfolio/PortfolioRoute.jsx',
  Journal: 'features/journal/DashboardRoute.jsx',
  Options: 'features/options/OptionsRoute.jsx',
  Screener: 'features/screener/components/ScreenerGrid.jsx',
  Watchlist: 'features/watchlist/components/WatchlistPage.jsx',
  Archive: 'features/archive/ArchiveRoute.jsx',
  Calibration: 'features/calibration/components/CalibrationTab.jsx',
};

test('a page with no detail is titled by its name alone', () => {
  assert.equal(documentTitle('Home'), 'Home');
  assert.equal(documentTitle('Watchlist', null), 'Watchlist');
  assert.equal(documentTitle('Watchlist', ''), 'Watchlist');
});

test('a detail follows the page name after a middle dot', () => {
  assert.equal(documentTitle('Calibration', 'SKYT 2026-04-13'), 'Calibration · SKYT 2026-04-13');
  assert.equal(documentTitle('Screener', 'NVDA'), 'Screener · NVDA');
});

test('unsaved work puts the dot FIRST, so a truncated tab still shows it', () => {
  assert.equal(
    documentTitle('Calibration', 'SKYT 2026-04-13', { unsaved: true }),
    '● Calibration · SKYT 2026-04-13',
  );
  assert.equal(
    documentTitle('Calibration', 'SKYT 2026-04-13', { unsaved: false }),
    'Calibration · SKYT 2026-04-13',
  );
});

test('the title restored on unmount is the one index.html loads with', () => {
  const html = fs.readFileSync(path.join(srcDir, '..', 'index.html'), 'utf8');
  assert.ok(html.includes(`<title>${APP_TITLE}</title>`), `index.html <title> is not ${APP_TITLE}`);
});

test('every top-nav page has exactly one title owner', () => {
  const labels = [...read(path.join('app', 'components', 'AppTopbar.jsx')).matchAll(/label: '([^']+)'/g)]
    .map((m) => m[1])
    .sort();
  assert.deepEqual(labels, Object.keys(OWNERS).sort());
});

test('each owner titles its page with its nav label', () => {
  for (const [label, file] of Object.entries(OWNERS)) {
    assert.ok(read(file).includes(`useDocumentTitle('${label}'`), `${file} does not call useDocumentTitle('${label}'`);
  }
});

test('no file other than the owners writes a page title', () => {
  const writers = fs
    .readdirSync(srcDir, { recursive: true })
    .map((f) => f.split(path.sep).join('/'))
    .filter((f) => /\.jsx?$/.test(f) && !f.endsWith('.test.js'))
    .filter((f) => /useDocumentTitle\(\s*'/.test(read(f)))
    .sort();
  assert.deepEqual(writers, Object.values(OWNERS).sort());
});
