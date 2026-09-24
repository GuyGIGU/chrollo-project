// Features depend on each other one way only (docs/architecture.md section 7):
// when features/<a> imports features/<b> and <b> imports <a>, one of them owns
// a piece that belongs to the other or in shared/. This scans every relative
// import specifier under src/features and fails on any such pair.
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

test('no two features import each other', () => {
  const edges = crossFeatureImports();
  assert.ok(edges.size > 0, 'the scan found no cross-feature import: the specifier pattern went vacuous');
  const cycles = [];
  for (const [key, file] of edges) {
    const [from, to] = key.split('->');
    const back = edges.get(`${to}->${from}`);
    if (back && from < to) cycles.push(`${from} <-> ${to}: features/${file} and features/${back}`);
  }
  assert.deepEqual(cycles, []);
});
