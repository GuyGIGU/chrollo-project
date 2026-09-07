import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { buildHealthPill, buildScanStatusText, failingChecks, scanStatusColor } from './appFormat.js';

// The live defect: scan_runs row 277 was killed 24 seconds in and carries a NULL
// setup count. Number(null) is 0 and Number.isFinite(0) is true, so the topbar
// read "0 setups" and the operator took it to mean the scan ran and found
// nothing.
test('a null setup count says unknown, not zero', () => {
  const text = buildScanStatusText({
    status: 'failed', n_setups: null, finished_at: '2026-09-04T22:00:30Z',
  });
  assert.match(text, /setup count unknown/);
  assert.doesNotMatch(text, /\b0 setups\b/);
});

// The pair that stops the fix over-correcting: a genuinely empty scan is real
// information, and stale_data rows legitimately carry a count.
test('a real zero still reads as zero', () => {
  const text = buildScanStatusText({
    status: 'ok', n_setups: 0, finished_at: '2026-09-04T22:00:30Z',
  });
  assert.match(text, /\b0 setups\b/);
});

test('a real count still reads as the count', () => {
  const text = buildScanStatusText({
    status: 'stale_data', n_setups: 12, finished_at: '2026-09-04T22:00:30Z',
  });
  assert.match(text, /12 setups/);
});

// The drift pin the null-safety rule asks for: this module must import the
// house guard, never mint its own.
test('appFormat declares no null guard of its own', () => {
  const src = fs.readFileSync(
    path.join(path.dirname(fileURLToPath(import.meta.url)), 'appFormat.js'), 'utf8');
  assert.ok(!src.includes('Number.isFinite('));
});

// An aborted run is not-ok on the backend's own health check and has always
// rendered danger in the scan-history table. Folding that table's private color
// map into this one must not quietly turn it grey.
test('an aborted run is not painted like a healthy one', () => {
  assert.notEqual(scanStatusColor('aborted'), scanStatusColor('ok'));
  assert.equal(scanStatusColor('aborted'), scanStatusColor('failed'));
});

test('failingChecks returns only the failing, non-ibkr checks', () => {
  const checks = failingChecks({
    checks: {
      db: { ok: true },
      last_scan: { ok: false, label: 'Last scan', reason: 'boom' },
      ibkr: { ok: false },
      scheduler: { ok: false },
    },
  });
  assert.deepEqual(checks.map(c => c.key).sort(), ['last_scan', 'scheduler']);
});

// The pill tooltip is operator-facing copy: it must not leak the internal check
// key, and it must not render "undefined" for a check the wire described.
test('the health pill tooltip uses the wire words, not the raw check key', () => {
  const pill = buildHealthPill({
    status: 'degraded',
    checks: {
      last_scan: {
        ok: false,
        label: 'Last scan',
        reason: 'The computer was shut down while the scan was still running.',
      },
    },
  });
  assert.match(pill.title, /Last scan/);
  assert.doesNotMatch(pill.title, /last_scan/);
  assert.doesNotMatch(pill.title, /undefined/);
});

test('a check with no wire words still renders something readable', () => {
  const pill = buildHealthPill({
    status: 'degraded',
    checks: { db: { ok: false } },
  });
  assert.doesNotMatch(pill.title, /undefined/);
});
