// Ink-on-fill contrast is a correctness property on an instrument, not a taste
// call: the operator must be able to READ "BUY"/"SELL" on the control that
// records his own fills, not infer it from the background hue.
//
// Council review 2026-09-07 finding 13 measured white ink at 1.94:1 on --success
// and 3.18:1 on --danger, with a code comment asserting the pink/red fills "read
// correctly". This pins the real numbers so a revert to `#fff` fails loudly.
//
// The floor is WCAG AA for normal text (4.5:1). Both surfaces set these labels
// at 10-12px, so the 3:1 large-text allowance does not apply.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const srcDir = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const CSS = fs.readFileSync(path.join(srcDir, 'index.css'), 'utf8');
const TOOLBAR = fs.readFileSync(path.join(srcDir, 'components', 'ScreenerToolbar.jsx'), 'utf8');

const AA_NORMAL = 4.5;

// --- WCAG 2.x relative luminance / contrast, on #rgb / #rrggbb ---------------
function channels(hex) {
  const raw = hex.trim().replace('#', '');
  const full = raw.length === 3 ? raw.split('').map((c) => c + c).join('') : raw;
  assert.equal(full.length, 6, `not a hex color: ${hex}`);
  return [0, 2, 4].map((i) => parseInt(full.slice(i, i + 2), 16) / 255);
}

function relativeLuminance(hex) {
  const [r, g, b] = channels(hex).map((c) => (c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function contrastRatio(a, b) {
  const la = relativeLuminance(a);
  const lb = relativeLuminance(b);
  const [hi, lo] = la >= lb ? [la, lb] : [lb, la];
  return (hi + 0.05) / (lo + 0.05);
}

// --- token + declaration resolution against the REAL files ------------------
// Reading the shipped CSS (rather than hard-coding the hexes) is what makes this
// a guard: retune a token or put white ink back and the assertion moves.
function token(name) {
  const match = CSS.match(new RegExp(`^\\s*--${name}:\\s*([^;]+);`, 'm'));
  assert.ok(match, `token --${name} not found in index.css`);
  return match[1].trim();
}

// Resolve a CSS color expression to a hex, following one level of var() alias.
function resolveColor(value) {
  const v = value.trim();
  if (v.startsWith('#')) return v;
  const alias = v.match(/^var\(\s*--([\w-]+)/);
  assert.ok(alias, `unresolvable color: ${value}`);
  return resolveColor(token(alias[1]));
}

// The `color:` declaration of a CSS rule, by selector.
function ruleInk(selector) {
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const block = CSS.match(new RegExp(`${escaped}\\s*\\{([^}]*)\\}`));
  assert.ok(block, `rule not found: ${selector}`);
  const color = block[1].match(/(?:^|[;{\s])color:\s*([^;]+);/);
  assert.ok(color, `no color declaration in ${selector}`);
  return resolveColor(color[1]);
}

test('the fill-entry BUY/SELL chips clear AA against their semantic fills', () => {
  const ink = ruleInk('.fills-panel .fill-side-btn');
  for (const fill of ['success', 'danger']) {
    const ratio = contrastRatio(ink, resolveColor(token(fill)));
    assert.ok(
      ratio >= AA_NORMAL,
      `fill-side-btn ink ${ink} on --${fill} is ${ratio.toFixed(2)}:1, under ${AA_NORMAL}:1`,
    );
  }
});

test('the data-refresh button takes dark ink on every fill it can wear', () => {
  // downloadColor() returns exactly these four; the ink must clear AA on all of
  // them, and no `#fff` literal may survive in the style that consumes them.
  assert.ok(
    !/color:\s*disabled[^,]*'#fff'/.test(TOOLBAR),
    'ScreenerToolbar still falls back to white ink on a semantic fill',
  );
  const ink = resolveColor(token('myth-ink'));
  for (const fill of ['accent-active', 'warning', 'danger', 'accent-pink']) {
    const ratio = contrastRatio(ink, resolveColor(token(fill)));
    assert.ok(
      ratio >= AA_NORMAL,
      `--myth-ink on --${fill} is ${ratio.toFixed(2)}:1, under ${AA_NORMAL}:1`,
    );
  }
});

test('the contrast math itself is right', () => {
  assert.equal(contrastRatio('#fff', '#000').toFixed(2), '21.00');
  assert.equal(contrastRatio('#fff', '#fff').toFixed(2), '1.00');
  // The measurement the finding was opened on, pinned so the number stays honest.
  assert.equal(contrastRatio('#fff', '#3DD37A').toFixed(2), '1.94');
  assert.equal(contrastRatio('#fff', '#DE6E78').toFixed(2), '3.18');
});
