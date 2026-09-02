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
} from './uiScale.js';

test('screenerColumnsAt: the operator 1536px viewport shows 2 cards at 100%', () => {
  // Two-up by design since CARD_MIN_PX went 480 -> 620 (operator 2026-09-02,
  // "make the mini chart graph bigger"): a 742px card gives the ~687px plot the
  // 140-trading-day reference window needs to render at ~4.9px per trading day.
  assert.equal(screenerColumnsAt(1, 1536), 2);
  assert.equal(screenerColumnsAt(0.9, 1536), 2);
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

test('computeAutoFitScale: stays at 100% for the 1536px monitor — 2 cards already fit', () => {
  // No step down to 85% reaches a 3rd 620px card at this width, so auto-fit must
  // not shrink his text to chase one.
  assert.equal(computeAutoFitScale(1536), 1);
});

test('computeAutoFitScale: stays at 100% when shrinking would not add a column', () => {
  // A 1440px viewport already shows 2 cards and cannot reach a 3rd without
  // dropping below the 85% floor, so auto-fit should not shrink at all.
  assert.equal(screenerColumnsAt(1, 1440), 2);
  assert.equal(screenerColumnsAt(0.85, 1440), 2);
  assert.equal(computeAutoFitScale(1440), 1);
});

test('computeAutoFitScale: on a wide monitor shrinks only as far as the next column needs', () => {
  // 1920px reaches a 3rd card at 95% — take that step, but no further down.
  assert.equal(screenerColumnsAt(1, 1920), 2);
  assert.equal(screenerColumnsAt(0.95, 1920), 3);
  assert.equal(computeAutoFitScale(1920), 0.95);
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
  const html = readFileSync(join(dirname(fileURLToPath(import.meta.url)), '../../index.html'), 'utf8');
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

const frontendDir = join(dirname(fileURLToPath(import.meta.url)), '..', '..');
const readRepo = (rel) => readFileSync(join(frontendDir, rel), 'utf8');

test('the card minimum is identical at all five sites', () => {
  // Each regex is anchored to its OWN rule: a bare minmax() match on index.css
  // finds an unrelated 150px grid first and the test would be red on arrival.
  const sites = [
    ['index.html pre-paint', readRepo('index.html'), /var CHROME = \d+, CARD = (\d+)/],
    ['ScreenerGrid gridStyle', readRepo('src/components/ScreenerGrid.jsx'), /gridStyle\s*=\s*\{[\s\S]*?minmax\((\d+)px, 1fr\)/],
    ['HealthBoard gridStyle', readRepo('src/components/HealthBoard.jsx'), /gridStyle\s*=\s*\{[\s\S]*?minmax\((\d+)px, 1fr\)/],
    ['index.css .wl-card-grid', readRepo('src/index.css'), /\.wl-card-grid\s*\{[^}]*minmax\((\d+)px, 1fr\)/],
  ];
  for (const [label, text, pattern] of sites) {
    const match = text.match(pattern);
    assert.ok(match, `${label}: card-grid minimum not found — did the declaration move or get renamed?`);
    assert.equal(
      Number(match[1]),
      CARD_MIN_PX,
      `${label} says ${match[1]}px but uiScale.CARD_MIN_PX is ${CARD_MIN_PX}. All five must move together: uiScale.js, index.html, ScreenerGrid, HealthBoard, .wl-card-grid — HealthBoard renders inside ScreenerGrid's own wrapper, so a split makes one ScreenerMiniChart frame the same window at two densities in one pane.`,
    );
  }
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

  const runPrePaint = (clientWidth, stored = null) => {
    let applied = null;
    let calls = 0;
    let saved;
    const context = {
      localStorage: { getItem: () => stored, setItem: (_k, v) => { saved = v; } },
      window: { innerWidth: clientWidth },
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
    const { applied, calls } = runPrePaint(width);
    assert.equal(calls >= 1, true, `pre-paint never applied a scale at ${width}px`);
    assert.equal(applied, computeAutoFitScale(width), `pre-paint scale disagrees with computeAutoFitScale at ${width}px`);
  }

  // A stored value is honoured verbatim and NOT re-saved...
  const stored = runPrePaint(1536, '1.15');
  assert.equal(stored.applied, 1.15);
  assert.equal(stored.saved, undefined);
  // ...but a garbage one falls through to auto-fit.
  const garbage = runPrePaint(1536, '9');
  assert.equal(garbage.applied, computeAutoFitScale(1536));
});
