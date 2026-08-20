// The npm test script hand-enumerates every test file (node --test with an
// explicit list); this pin fails the suite loudly when a new src/**/*.test.js
// lands without being appended to that list.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const srcDir = path.dirname(fileURLToPath(import.meta.url));

test('package.json test script names exactly the src/**/*.test.js files on disk', () => {
  const pkg = JSON.parse(fs.readFileSync(path.join(srcDir, '..', 'package.json'), 'utf8'));
  const listed = pkg.scripts.test
    .split(/\s+/)
    .filter((tok) => tok.endsWith('.test.js'))
    .sort();
  const onDisk = fs
    .readdirSync(srcDir, { recursive: true })
    .filter((f) => f.endsWith('.test.js'))
    .map((f) => 'src/' + f.split(path.sep).join('/'))
    .sort();
  assert.deepEqual(listed, onDisk);
});
