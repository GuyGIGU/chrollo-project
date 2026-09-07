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
  const matches = [...CSS.matchAll(new RegExp(`^\\s*--${name}:\\s*([^;]+);`, 'gm'))];
  assert.ok(matches.length > 0, `token --${name} not found in index.css`);
  // Measuring the FIRST definition is only honest while there is one. The day a
  // theme block redefines a fill, the second value is what the operator sees on
  // that theme and this file has to be taught to measure both — so fail here
  // rather than keep reporting the light-theme number (review A8).
  assert.equal(matches.length, 1,
    `--${name} is defined ${matches.length}x — this guard measures one value per token`);
  return matches[0][1].trim();
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

// The body of a top-level `const NAME = ... };` in the toolbar source, comments
// stripped — so a colour named inside a comment can never be measured.
function toolbarBlock(name) {
  const block = TOOLBAR.match(new RegExp(`const ${name} = [\\s\\S]*?\\n};`));
  assert.ok(block, `${name} not found in ScreenerToolbar.jsx`);
  return block[0].replace(/\/\/[^\n]*/g, '');
}

// The ink the data-refresh button actually wears when it is ENABLED — i.e. when
// it is sitting on one of downloadColor()'s semantic fills.
function toolbarEnabledInk() {
  const decl = toolbarBlock('downloadButtonStyle').match(/\n\s*color:\s*(.+?),\s*\n/);
  assert.ok(decl, 'no color declaration in downloadButtonStyle');
  // `disabled ? <disabled ink> : <enabled ink>` — the enabled arm is the one on
  // a fill. A plain expression is taken as-is.
  const expr = decl[1].includes('?') ? decl[1].split(':').slice(1).join(':') : decl[1];
  return resolveColor(expr.replace(/['"]/g, '').trim());
}

// Every fill downloadColor() can return, derived rather than re-typed: a fifth
// state added there must be measured too, without anyone remembering to.
function toolbarFills() {
  const fills = [...toolbarBlock('downloadColor').matchAll(/return\s+'([^']+)'/g)].map((m) => m[1]);
  assert.ok(fills.length >= 4, `downloadColor returned ${fills.length} fills, expected its four+`);
  return fills;
}

test('the data-refresh button takes dark ink on every fill it can wear', () => {
  // This RESOLVES what the file says, rather than sniffing for one banned
  // literal: the old assertion only refused `'#fff'`, so swapping in
  // `var(--text-muted)` — about 2:1 on --accent-active — would have passed it
  // (council review 2026-09-07, A8).
  const ink = toolbarEnabledInk();
  for (const fill of toolbarFills()) {
    const ratio = contrastRatio(ink, resolveColor(fill));
    assert.ok(
      ratio >= AA_NORMAL,
      `toolbar ink ${ink} on ${fill} is ${ratio.toFixed(2)}:1, under ${AA_NORMAL}:1`,
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
