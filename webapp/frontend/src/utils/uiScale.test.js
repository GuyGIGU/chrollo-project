import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
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

test('screenerColumnsAt: the operator 1536px viewport now shows 3 cards at 100% (rail removed)', () => {
  assert.equal(screenerColumnsAt(1, 1536), 3); // full width reclaimed from the old 86px rail
  assert.equal(screenerColumnsAt(0.9, 1536), 3);
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

test('computeAutoFitScale: stays at 100% for the 1536px monitor — 3 cards already fit', () => {
  assert.equal(computeAutoFitScale(1536), 1);
});

test('computeAutoFitScale: stays at 100% when shrinking would not add a column', () => {
  // A ~1150px viewport already shows 2 cards and cannot reach a 3rd without
  // dropping below the 85% floor, so auto-fit should not shrink at all.
  assert.equal(screenerColumnsAt(1, 1150), 2);
  assert.equal(screenerColumnsAt(0.85, 1150), 2);
  assert.equal(computeAutoFitScale(1150), 1);
});

test('computeAutoFitScale: on a wide monitor shrinks only as far as the next column needs', () => {
  // 2560px reaches a 6th card at 85% shrink — take it, but no further.
  assert.equal(computeAutoFitScale(2560), 0.85);
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
