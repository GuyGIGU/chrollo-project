// Features depend on each other one way only (docs/architecture.md section 7):
// Cycles of any length reveal ownership that needs fixing. Shared code must
// also stay independent of features; otherwise a move can hide the same cycle.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const featuresDir = path.join(path.dirname(fileURLToPath(import.meta.url)), 'features');

// `import x from`, `export { x } from`, `import '...'` and `import('...')`.
const SPECIFIER = /\b(?:from|import)\s*\(?\s*['"](\.{1,2}\/[^'"\n]+)['"]/g;

const featureOf = (file) => {
  const rel = path.relative(featuresDir, file);
  return rel.startsWith('..') || path.isAbsolute(rel) ? null : rel.split(path.sep)[0];
};

// "a->b" -> the first file in feature a that imports feature b.
const crossFeatureImports = () => {
  const edges = new Map();
  const files = fs.readdirSync(featuresDir, { recursive: true }).filter((f) => /\.jsx?$/.test(f));
  for (const rel of files) {
    const file = path.join(featuresDir, rel);
    const from = featureOf(file);
    for (const [, spec] of fs.readFileSync(file, 'utf8').matchAll(SPECIFIER)) {
      const to = featureOf(path.resolve(path.dirname(file), spec));
      const key = `${from}->${to}`;
      if (to && to !== from && !edges.has(key)) edges.set(key, rel.split(path.sep).join('/'));
    }
  }
  return edges;
};

function findCycle(keys) {
  const graph = new Map();
  for (const key of keys) {
    const [from, to] = key.split('->');
    if (!graph.has(from)) graph.set(from, []);
    graph.get(from).push(to);
  }
  const done = new Set();
  const active = [];
  const visit = (node) => {
    const index = active.indexOf(node);
    if (index >= 0) return [...active.slice(index), node];
    if (done.has(node)) return null;
    active.push(node);
    for (const next of graph.get(node) || []) {
      const cycle = visit(next);
      if (cycle) return cycle;
    }
    active.pop();
    done.add(node);
    return null;
  };
  for (const node of graph.keys()) {
    const cycle = visit(node);
    if (cycle) return cycle;
  }
  return null;
}

test('the ownership guard detects indirect cycles and permits a dependency diamond', () => {
  assert.deepEqual(findCycle(['home->screener', 'screener->watchlist', 'watchlist->home']), ['home', 'screener', 'watchlist', 'home']);
  assert.equal(findCycle(['home->screener', 'home->watchlist', 'screener->watchlist']), null);
});

test('features have no direct or indirect import cycle', () => {
  const edges = crossFeatureImports();
  assert.ok(edges.size > 0, 'the scan found no cross-feature import: the specifier pattern went vacuous');
  const cycle = findCycle(edges.keys());
  assert.equal(cycle, null, cycle?.map((from, i) => i ? edges.get(`${cycle[i - 1]}->${from}`) : from).join(' -> '));
});

test('shared production code never reaches back into a feature', () => {
  const sharedDir = path.join(featuresDir, '..', 'shared');
  const violations = [];
  for (const rel of fs.readdirSync(sharedDir, { recursive: true }).filter((f) => /\.jsx?$/.test(f) && !f.includes('.test.'))) {
    const file = path.join(sharedDir, rel);
    for (const [, spec] of fs.readFileSync(file, 'utf8').matchAll(SPECIFIER)) {
      if (featureOf(path.resolve(path.dirname(file), spec))) violations.push(`${rel}: ${spec}`);
    }
  }
  assert.deepEqual(violations, []);
});
