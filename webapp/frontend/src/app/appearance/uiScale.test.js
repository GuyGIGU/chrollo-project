import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import {
  SCALE_STEPS,
  GRID_CHROME_PX,
  CARD_PX,
  CARD_GAP_PX,
  clampScale,
  screenerColumnsAt,
  monitorId,
  storageKeyFor,
} from './uiScale.js';

// The width of the row `cols` fixed cards take.
const rowWidth = (cols) => cols * CARD_PX + (cols - 1) * CARD_GAP_PX;

test('one card size, the Finviz way: four at 1920, five at 2560, two in a 1024px window', () => {
  // Operator Thu 29/10/2026, his Finviz chart view: one chart size on every screen,
  // a wider window shows more of them.
  assert.equal(screenerColumnsAt(1, 1920), 4);
  assert.equal(screenerColumnsAt(1, 2560), 5);
  assert.equal(screenerColumnsAt(1, 1280), 2);
  assert.equal(screenerColumnsAt(1, 1024), 2);
  // Four cards fill the 1920 grid to the pixel: the card he had there on 28/10.
  assert.equal(rowWidth(4), 1920 - GRID_CHROME_PX);
  assert.ok(rowWidth(5) <= 2560 - GRID_CHROME_PX);
});

test('screenerColumnsAt: never returns fewer than one column', () => {
  assert.equal(screenerColumnsAt(1.3, 400), 1);
});

test('screenerColumnsAt: more columns as the scale shrinks (monotonic)', () => {
  const cols = SCALE_STEPS.map((s) => screenerColumnsAt(s, 1536));
  for (let i = 1; i < cols.length; i += 1) {
    assert.ok(cols[i] <= cols[i - 1], `cols should not grow as scale grows at index ${i}`);
  }
});

test('monitorId names the screen by its CSS size, and degrades to one shared id', () => {
  assert.equal(monitorId({ width: 2560, height: 1440 }), '2560x1440');
  assert.equal(monitorId({ width: 1536.0, height: 864 }), '1536x864');
  assert.equal(monitorId(undefined), 'default');
  assert.equal(monitorId({ width: 0, height: 900 }), 'default');
  assert.equal(storageKeyFor('2560x1440'), 'chrollo:ui-scale@2560x1440');
});

test('clampScale: snaps arbitrary/garbage values to the nearest step', () => {
  assert.equal(clampScale(0.87), 0.85);
  assert.equal(clampScale(1.02), 1);
  assert.equal(clampScale(5), 1.3);
  assert.equal(clampScale('nonsense'), 1);
});

// --- Parity guard for the forced twin -------------------------------------------------------
// index.html's pre-paint <head> script applies the stored scale before React mounts (no flash).
// It cannot import this ES module, so it is a forced twin (like the AP-5 JS/Python ledger). These
// tests are its parity guard: if its steps or the scale it applies drift from uiScale.js, the
// flash-prevention silently breaks and every other unit test still passes.
const preScript = (() => {
  const html = readFileSync(join(dirname(fileURLToPath(import.meta.url)), '../../../index.html'), 'utf8');
  const start = html.indexOf('chrollo:ui-scale');
  assert.ok(start !== -1, 'index.html: pre-paint UI-scale script not found');
  return html.slice(start);
})();

const preSteps = () => JSON.parse(preScript.match(/STEPS\s*=\s*(\[[^\]]*\])/)[1]);

test('index.html pre-paint steps match uiScale.js', () => {
  assert.deepEqual(preSteps(), SCALE_STEPS);
});

// --- the forced twins -------------------------------------------------------
//
// The card grid is declared at two sites and the pre-paint script is a hand copy.
// Both were guarded by prose until the 2026-09-02 review, which mutation-proved the
// gaps: grid declarations could drift apart with the whole suite green, and the
// pre-paint script's LOGIC could drift (or be deleted outright) while a re-typed
// copy of it was tested instead of the real thing.

const frontendDir = join(dirname(fileURLToPath(import.meta.url)), '..', '..', '..');
const readRepo = (rel) => readFileSync(join(frontendDir, rel), 'utf8');

test('both card grids are the one-size grid, built from uiScale', () => {
  // HealthBoard renders inside ScreenerGrid's own wrapper: a split makes one
  // ScreenerMiniChart frame the same window at two densities in one pane. A
  // stretched track (1fr) or a fixed column count is the 28/10 grid again, which
  // drew a 620px card at 2560 and a 236px one in a 1024px window.
  for (const rel of ['src/features/screener/components/ScreenerGrid.jsx', 'src/features/screener/components/HealthBoard.jsx']) {
    const style = readRepo(rel).match(/const gridStyle\s*=\s*\{([\s\S]*?)\r?\n\};/);
    assert.ok(style, `${rel}: gridStyle not found — did the declaration move or get renamed?`);
    assert.match(style[1], /gridTemplateColumns: `repeat\(auto-fill, \$\{CARD_PX\}px\)`/, `${rel}: the card is no longer one fixed size`);
    assert.match(style[1], /justifyContent: 'center'/, `${rel}: the rows are no longer centred`);
    assert.match(style[1], /gap: `\$\{CARD_GAP_PX\}px`/, `${rel}: the gap is no longer uiScale's`);
  }
});

test('the lens fills the 1920 screen and scrolls, and the big charts hold one size on every screen', () => {
  // Operator 2026-10-03, "same goes for the big charts": the lens's chart band and
  // the Watchlist D/W/M band are one size on every monitor. Operator Thu
  // 16/10/2026: the lens is TWO BLOCKS — the chart block at its own height and
  // the stats block under it at its natural height, the body scrolling to it:
  // "give much more room for both blocks but without the need to squeeze them
  // together". Fri 17/10/2026: the chart block is the THREE-PANE GRID (monthly
  // over weekly beside the big daily, his TradingView layout) at
  // --lens-chart-band, sized so the grade board under it fits the 1080 screen
  // with it ("I need to see both the chart and the highlights it provides in
  // the same screen").
  const css = readRepo('src/index.css');
  const modal = readRepo('src/shared/setup/ScreenerModal.jsx').match(/className="screener-modal-shell"[\s\S]*?style=\{\{([\s\S]*?)\}\}/);
  assert.ok(modal, 'ScreenerModal: the lens shell style not found');
  // Thu 29/10/2026: the whole 1920 screen inside the scrim ("make the entire pop up bigger"), and that size,
  // not a bigger one, on the 2560 screen (2026-10-03 "same goes for the big charts").
  assert.match(modal[1], /maxWidth: 1896,/, 'the lens no longer fills the 1920 screen, or grows past it on a bigger one');
  assert.doesNotMatch(modal[1], /maxHeight/, 'the lens shell is height-capped again — the stats block loses the room below the chart');
  assert.match(css, /--lens-chart-band: 400px;/, 'the chart lost its one height (Finviz’s 400px on every monitor, so the grade board fits under it at 1080)');
  const lensBand = css.match(/\n\.lens-chart-grid\s*\{([^}]*)\}/);
  assert.ok(lensBand, 'index.css: the desktop .lens-chart-grid rule not found');
  assert.match(lensBand[1], /height: var\(--lens-chart-band\);/, 'the chart grid no longer takes its own height');
  assert.doesNotMatch(lensBand[1], /max-height|vh/, 'the chart grid is sized by the screen again');
  const narrowBand = css.match(/@media \(max-width: 760px\)[\s\S]*?\n {2}\.lens-chart-grid\s*\{([^}]*)\}/);
  assert.ok(narrowBand, 'index.css: the 760px .lens-chart-grid override not found');
  assert.match(narrowBand[1], /height: auto;/, 'the stacked lens grid keeps the desktop block height again');
  // Thu 29/10/2026: the wheel over a pane zooms, so the page's sides are the lanes he scrolls in.
  const lanes = css.match(/\n\.lens-page\s*\{([^}]*)\}/);
  assert.ok(lanes, 'index.css: the desktop .lens-page rule not found');
  assert.match(lanes[1], /padding: 8px 72px 32px;/, 'the scroll lanes beside the chart and the stats are thin again');
  const body = readRepo('src/shared/setup/ScreenerModal.jsx').match(/className="screener-modal-body lens-page" style=\{\{([^}]*)\}\}/);
  assert.ok(body, 'ScreenerModal: the lens body style not found');
  assert.match(body[1], /overflowY: 'auto'/, 'the lens body no longer scrolls — the two blocks are squeezed into the screen again');
  const row = readRepo('src/shared/setup/ScreenerModal.jsx').match(/className="lens-chart-grid" style=\{\{([^}]*)\}\}/);
  assert.ok(row, 'ScreenerModal: the chart grid style not found');
  assert.match(row[1], /flex: '0 0 auto'/, 'the chart grid flexes again — it would shrink to what the screen leaves');
  const panel = css.match(/\n\.stock-lens\s*\{([^}]*)\}/);
  assert.ok(panel, 'index.css: .stock-lens not found');
  assert.match(panel[1], /flex: 0 0 auto;/, 'the stats block is squeezed into what the chart block leaves again');
  assert.doesNotMatch(panel[1], /max-height|overflow-y/, 'the stats block scrolls inside itself again instead of the page');
  const band = css.match(/\.wl-chart-dialog\s*\{([^}]*)\}/);
  assert.ok(band, 'index.css: .wl-chart-dialog not found');
  assert.match(band[1], /max-height: 805px;/, 'the Watchlist chart band is no longer held at its 1920 height');
  assert.match(band[1], /height: calc\(82dvh \/ var\(--ui-scale\)\);/, 'the Watchlist chart band lost its height, or its viewport height is no longer divided by the UI scale (it clips at 130%)');
  assert.match(band[1], /width: calc\(96vw \/ var\(--ui-scale\)\);/, 'the Watchlist chart band\'s viewport width is no longer divided by the UI scale (it clips at 130%)');
  assert.match(band[1], /max-width: 1850px;/, 'the Watchlist chart band is no longer held at its 1920 width');
});

test('the index.html pre-paint script RUNS: a stored choice, else 100%', () => {
  // Executes the real script, not a re-typed copy of it. The script wraps
  // everything in try/catch, so a gap in the stub is swallowed silently — hence
  // the `calls` assertion, which is the load-bearing half: it is the only thing
  // that fails if the script stops applying a scale at all.
  const html = readRepo('index.html');
  const body = html.match(/<script>([\s\S]*?)<\/script>/);
  assert.ok(body, 'index.html: the pre-paint <script> block is gone');
  assert.match(body[1], /chrollo:ui-scale/, 'the pre-paint script no longer touches the scale key');

  const runPrePaint = (clientWidth, stored = null, screen = { width: clientWidth, height: 1080 }, storedFor = null) => {
    let applied = null;
    let calls = 0;
    let saved;
    const key = storedFor ?? storageKeyFor(monitorId(screen));
    const context = {
      localStorage: { getItem: (k) => (k === key ? stored : null), setItem: (_k, v) => { saved = v; } },
      window: { innerWidth: clientWidth, screen },
      document: {
        documentElement: {
          clientWidth,
          style: { setProperty: (_name, value) => { calls += 1; applied = Number(value); } },
        },
      },
    };
    vm.runInNewContext(body[1], context);
    return { applied, calls, saved };
  };

  // A screen with no choice is at 100% whatever its width: nothing is zoomed to fit.
  for (const width of [900, 1150, 1280, 1440, 1536, 1707, 1920, 2560, 3840]) {
    const { applied, calls, saved } = runPrePaint(width);
    assert.equal(calls >= 1, true, `pre-paint never applied a scale at ${width}px`);
    assert.equal(applied, 1, `pre-paint zoomed a ${width}px window to ${applied}`);
    assert.equal(saved, undefined, `the scale at ${width}px was saved - only a manual choice is stored`);
  }

  // THIS screen's stored choice is honoured verbatim and NOT re-saved...
  const stored = runPrePaint(2560, '1.15', { width: 2560, height: 1440 });
  assert.equal(stored.applied, 1.15);
  assert.equal(stored.saved, undefined);
  // ...the OTHER screen's choice does not leak onto this one...
  const other = runPrePaint(2560, '0.85', { width: 2560, height: 1440 }, 'chrollo:ui-scale@1920x1080');
  assert.equal(other.applied, 1);
  // ...nor does the retired single key...
  const legacy = runPrePaint(2560, '0.85', { width: 2560, height: 1440 }, 'chrollo:ui-scale');
  assert.equal(legacy.applied, 1);
  // ...and a garbage one falls through to 100%.
  const garbage = runPrePaint(1536, '9');
  assert.equal(garbage.applied, 1);
});
