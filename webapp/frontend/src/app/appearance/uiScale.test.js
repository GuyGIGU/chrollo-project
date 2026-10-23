import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import {
  SCALE_STEPS,
  GRID_CHROME_PX,
  CARD_MIN_PX,
  CARD_GAP_PX,
  clampScale,
  screenerColumnsAt,
  computeAutoFitScale,
  monitorId,
  storageKeyFor,
} from './uiScale.js';

// The width of one card when `cols` cards share a grid `gridWidth` px wide.
const cardWidth = (gridWidth, cols) => (gridWidth - (cols - 1) * CARD_GAP_PX) / cols;
// How many cards a grid `gridWidth` px wide holds (the CSS auto-fill rule).
const colsIn = (gridWidth) => Math.floor((gridWidth + CARD_GAP_PX) / (CARD_MIN_PX + CARD_GAP_PX));

test('one card size on both of his screens: three at 1920, four at 2560', () => {
  // Operator 2026-10-03, after a day of three 831px cards on the 2560 screen:
  // "I want them to retain the original size so the scaling looks the same, with
  // the extra monitor space I could just ... see more of the website".
  const at1920 = screenerColumnsAt(1, 1920);
  const at2560 = screenerColumnsAt(1, 2560);
  assert.equal(at1920, 3);
  assert.equal(at2560, 4);
  const w1920 = cardWidth(1920 - GRID_CHROME_PX, at1920);
  const w2560 = cardWidth(2560 - GRID_CHROME_PX, at2560);
  assert.ok(Math.abs(w1920 - w2560) < 5, `the card is ${w1920.toFixed(0)}px at 1920 but ${w2560.toFixed(0)}px at 2560`);
  // The Watchlist grid is 32px narrower (no full-bleed wrapper), measured live
  // 2026-10-03: 1850px at 1920 and 2490px at 2560. It must keep three and four.
  assert.equal(colsIn(1850), 3);
  assert.equal(colsIn(2490), 4);
  assert.ok(Math.abs(cardWidth(1850, 3) - cardWidth(2490, 4)) < 10);
});

test('screenerColumnsAt: never returns fewer than one column', () => {
  assert.equal(screenerColumnsAt(1.3, 700), 1);
});

test('screenerColumnsAt: more columns as the scale shrinks (monotonic)', () => {
  const cols = SCALE_STEPS.map((s) => screenerColumnsAt(s, 1536));
  for (let i = 1; i < cols.length; i += 1) {
    assert.ok(cols[i] <= cols[i - 1], `cols should not grow as scale grows at index ${i}`);
  }
});

test('computeAutoFitScale: stays at 100% in a 1536px window — no step reaches a third card', () => {
  // Two 590px cards at 100%, and still two at 85% (2.95 cards' room), so
  // auto-fit must not shrink his text for nothing.
  assert.equal(screenerColumnsAt(1, 1536), 2);
  assert.equal(screenerColumnsAt(0.85, 1536), 2);
  assert.equal(computeAutoFitScale(1536), 1);
});

test('computeAutoFitScale: stays at 100% when shrinking would not add a column', () => {
  // A 1280px viewport already shows 2 cards and cannot reach a 3rd without
  // dropping below the 85% floor, so auto-fit should not shrink at all.
  assert.equal(screenerColumnsAt(1, 1280), 2);
  assert.equal(screenerColumnsAt(0.85, 1280), 2);
  assert.equal(computeAutoFitScale(1280), 1);
});

test('a wider screen gets more cards, never bigger ones', () => {
  // The 2026-10-02 three-card ceiling drew three 831px cards at 2560; with it
  // gone the card stays within the 590px minimum and the stretch to fill a row.
  for (const width of [1920, 2560, 3440, 3840]) {
    const cols = screenerColumnsAt(1, width);
    const card = cardWidth(width - GRID_CHROME_PX, cols);
    assert.ok(card >= CARD_MIN_PX && card < 700, `${width}px drew ${cols} cards of ${card.toFixed(0)}px`);
  }
});

test('computeAutoFitScale: both of his screens stay at 100%', () => {
  // No step down to 85% buys another 590px card at 1920 (3.7 cards' room) or at
  // 2560 (4.95), so auto-fit has nothing to chase.
  assert.equal(computeAutoFitScale(1920), 1);
  assert.equal(computeAutoFitScale(2560), 1);
});

test('monitorId names the screen by its CSS size, and degrades to one shared id', () => {
  assert.equal(monitorId({ width: 2560, height: 1440 }), '2560x1440');
  assert.equal(monitorId({ width: 1536.0, height: 864 }), '1536x864');
  assert.equal(monitorId(undefined), 'default');
  assert.equal(monitorId({ width: 0, height: 900 }), 'default');
  assert.equal(storageKeyFor('2560x1440'), 'chrollo:ui-scale@2560x1440');
});

test('computeAutoFitScale: never enlarges past 1', () => {
  assert.ok(computeAutoFitScale(900) <= 1);
});

test('computeAutoFitScale: always returns an allowed step', () => {
  for (const w of [900, 1280, 1536, 1707, 1920, 2560]) {
    assert.ok(SCALE_STEPS.includes(computeAutoFitScale(w)), `width ${w} produced a non-step scale`);
  }
});

test('clampScale: snaps arbitrary/garbage values to the nearest step', () => {
  assert.equal(clampScale(0.87), 0.85);
  assert.equal(clampScale(1.02), 1);
  assert.equal(clampScale(5), 1.3);
  assert.equal(clampScale('nonsense'), 1);
});

// --- Parity guard for the forced twin -------------------------------------------------------
// index.html's pre-paint <head> script duplicates this auto-fit math so the saved/first-run scale
// applies before React mounts (no flash). It cannot import this ES module, so it is a forced twin
// (like the AP-5 JS/Python ledger). These tests are its parity guard: if the pre-paint constants or
// the resulting scale drift from uiScale.js, the flash-prevention silently breaks and every other
// unit test still passes. Keep the two in sync or this goes red.
const preScript = (() => {
  const html = readFileSync(join(dirname(fileURLToPath(import.meta.url)), '../../../index.html'), 'utf8');
  const start = html.indexOf('chrollo:ui-scale');
  assert.ok(start !== -1, 'index.html: pre-paint UI-scale script not found');
  return html.slice(start);
})();

const preNum = (re) => {
  const m = preScript.match(re);
  assert.ok(m, `index.html pre-paint script: constant ${re} not found`);
  return Number(m[1]);
};

const preSteps = () => JSON.parse(preScript.match(/STEPS\s*=\s*(\[[^\]]*\])/)[1]);

test('index.html pre-paint constants match uiScale.js', () => {
  assert.equal(preNum(/CHROME\s*=\s*(\d+)/), GRID_CHROME_PX);
  assert.equal(preNum(/CARD\s*=\s*(\d+)/), CARD_MIN_PX);
  assert.equal(preNum(/GAP\s*=\s*(\d+)/), CARD_GAP_PX);
  assert.deepEqual(preSteps(), SCALE_STEPS);
});

test('index.html pre-paint auto-fit reproduces computeAutoFitScale across widths', () => {
  const CHROME = preNum(/CHROME\s*=\s*(\d+)/);
  const CARD = preNum(/CARD\s*=\s*(\d+)/);
  const GAP = preNum(/GAP\s*=\s*(\d+)/);
  const STEPS = preSteps();
  const prePaintAutoFit = (V) => {
    let best = 1;
    let bestCols = 0;
    for (const s of STEPS) {
      if (s > 1) continue;
      const cols = Math.max(1, Math.floor((V / s - CHROME + GAP) / (CARD + GAP)));
      if (cols > bestCols || (cols === bestCols && s > best)) {
        bestCols = cols;
        best = s;
      }
    }
    return best;
  };
  for (const w of [900, 1150, 1280, 1536, 1707, 1920, 2560, 3840]) {
    assert.equal(prePaintAutoFit(w), computeAutoFitScale(w), `auto-fit disagrees at ${w}px`);
  }
});


// --- the forced twins -------------------------------------------------------
//
// The card minimum lives at FIVE sites and the pre-paint auto-fit is a hand copy
// of computeAutoFitScale. Both were guarded by prose until the 2026-09-02
// review, which mutation-proved the gaps: three grid declarations could drift to
// a different minimum with the whole suite green, and the pre-paint script's
// LOGIC could drift (or be deleted outright) while a re-typed copy of it was
// tested instead of the real thing.

const frontendDir = join(dirname(fileURLToPath(import.meta.url)), '..', '..', '..');
const readRepo = (rel) => readFileSync(join(frontendDir, rel), 'utf8');

test('the card minimum is identical across the card-rendering sites', () => {
  // Each regex is anchored to its OWN rule: a bare minmax() match on index.css
  // finds an unrelated 150px grid first and the test would be red on arrival.
  const sites = [
    ['index.html pre-paint', readRepo('index.html'), /var CHROME = \d+, CARD = (\d+)/],
    // A plain minmax(<card>px, 1fr): a ceiling expression in the track (the
    // 2026-10-02 `max(480px, calc(.../ 3 ...))`) no longer matches, and fails here.
    ['ScreenerGrid gridStyle', readRepo('src/features/screener/components/ScreenerGrid.jsx'), /gridStyle\s*=\s*\{[^}]*?gridTemplateColumns: 'repeat\(auto-fill, minmax\((\d+)px, 1fr\)\)'/],
    ['HealthBoard gridStyle', readRepo('src/features/screener/components/HealthBoard.jsx'), /gridStyle\s*=\s*\{[^}]*?gridTemplateColumns: 'repeat\(auto-fill, minmax\((\d+)px, 1fr\)\)'/],
  ];
  for (const [label, text, pattern] of sites) {
    const match = text.match(pattern);
    assert.ok(match, `${label}: card-grid minimum not found — did the declaration move or get renamed?`);
    assert.equal(
      Number(match[1]),
      CARD_MIN_PX,
      `${label} says ${match[1]}px but uiScale.CARD_MIN_PX is ${CARD_MIN_PX}. All card sites must move together: uiScale.js, index.html, ScreenerGrid, HealthBoard — HealthBoard renders inside ScreenerGrid's own wrapper, so a split makes one ScreenerMiniChart frame the same window at two densities in one pane.`,
    );
  }
});

test('the lens is two blocks on a page that scrolls, and the big charts hold one size on every screen', () => {
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
  assert.match(modal[1], /maxWidth: 1760,/, 'the lens is no longer held at its 1920 width');
  assert.doesNotMatch(modal[1], /maxHeight/, 'the lens shell is height-capped again — the stats block loses the room below the chart');
  assert.match(css, /--lens-chart-band: 600px;/, 'the chart grid lost its one height (600px on every monitor: the grade board must fit under it at 1080)');
  const lensBand = css.match(/\n\.lens-chart-grid\s*\{([^}]*)\}/);
  assert.ok(lensBand, 'index.css: the desktop .lens-chart-grid rule not found');
  assert.match(lensBand[1], /height: var\(--lens-chart-band\);/, 'the chart grid no longer takes its own height');
  assert.doesNotMatch(lensBand[1], /max-height|vh/, 'the chart grid is sized by the screen again');
  const narrowBand = css.match(/@media \(max-width: 760px\)[\s\S]*?\n {2}\.lens-chart-grid\s*\{([^}]*)\}/);
  assert.ok(narrowBand, 'index.css: the 760px .lens-chart-grid override not found');
  assert.match(narrowBand[1], /height: auto;/, 'the stacked lens grid keeps the desktop block height again');
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

test('the index.html pre-paint script RUNS and agrees with computeAutoFitScale', () => {
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

  for (const width of [900, 1150, 1280, 1440, 1536, 1707, 1920, 2560, 3840]) {
    const { applied, calls, saved } = runPrePaint(width);
    assert.equal(calls >= 1, true, `pre-paint never applied a scale at ${width}px`);
    assert.equal(applied, computeAutoFitScale(width), `pre-paint scale disagrees with computeAutoFitScale at ${width}px`);
    assert.equal(saved, undefined, `auto-fit at ${width}px was saved - auto must stay live, never stored`);
  }

  // THIS screen's stored choice is honoured verbatim and NOT re-saved...
  const stored = runPrePaint(2560, '1.15', { width: 2560, height: 1440 });
  assert.equal(stored.applied, 1.15);
  assert.equal(stored.saved, undefined);
  // ...the OTHER screen's choice does not leak onto this one...
  const other = runPrePaint(2560, '0.85', { width: 2560, height: 1440 }, 'chrollo:ui-scale@1920x1080');
  assert.equal(other.applied, computeAutoFitScale(2560));
  // ...nor does the retired single key...
  const legacy = runPrePaint(2560, '0.85', { width: 2560, height: 1440 }, 'chrollo:ui-scale');
  assert.equal(legacy.applied, computeAutoFitScale(2560));
  // ...but a garbage one falls through to auto-fit.
  const garbage = runPrePaint(1536, '9');
  assert.equal(garbage.applied, computeAutoFitScale(1536));
});
