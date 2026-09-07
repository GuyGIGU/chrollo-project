import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { buildHealthPill, buildScanStatusText, failingChecks, scanStatusColor } from './appFormat.js';
import { RUN_STATUS_LABELS } from '../components/wireVocabulary.js';

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

// Same drift pin, one file over: the registry renders a possibly-null count and
// must reach for the house guard rather than mint an inline one.
test('the scan registry renders its count through the house guard', () => {
  const src = fs.readFileSync(
    path.join(path.dirname(fileURLToPath(import.meta.url)),
      '..', 'components', 'ScanHistoryModal.jsx'), 'utf8');
  assert.ok(src.includes('fmtInt(run.n_setups'));
  assert.ok(!src.includes('n_setups ??'));
});

// An aborted run is not-ok on the backend's own health check and has always
// rendered danger in the scan-history table. Folding that table's private color
// map into this one must not quietly turn it grey.
test('an aborted run is not painted like a healthy one', () => {
  assert.notEqual(scanStatusColor('aborted'), scanStatusColor('ok'));
  assert.equal(scanStatusColor('aborted'), scanStatusColor('failed'));
});

// EC-28: WHICH checks count as a failure is a judgment, and it crosses the wire
// already made. This must stay a pass-through — the moment it filters
// `health.checks` itself, exempting a check server-side still leaves it listed
// here, with whatever fallback prose the JS invents.
test('failingChecks passes the wire verdict through and derives nothing', () => {
  const wire = [
    { key: 'last_scan', label: 'Last scan', reason: 'boom', solution: 'do this' },
    { key: 'scheduler', label: 'Nightly scan timer', reason: 'off', solution: 'restart' },
  ];
  assert.deepEqual(failingChecks({ failing: wire, checks: { db: { ok: false } } }), wire);
});

test('failingChecks is empty when the wire says nothing is failing', () => {
  assert.deepEqual(failingChecks({ checks: { last_scan: { ok: false } } }), []);
  assert.deepEqual(failingChecks(null), []);
});

// The pill tooltip is operator-facing copy: it must not leak the internal check
// key, and it must not render "undefined" for a check the wire described.
test('the health pill tooltip uses the wire words, not the raw check key', () => {
  const pill = buildHealthPill({
    status: 'degraded',
    failing: [{
      key: 'last_scan',
      label: 'Last scan',
      reason: 'The computer was shut down while the scan was still running.',
    }],
  });
  assert.match(pill.title, /Last scan/);
  assert.doesNotMatch(pill.title, /last_scan/);
  assert.doesNotMatch(pill.title, /undefined/);
});

test('a check with no wire words still renders something readable', () => {
  const pill = buildHealthPill({
    status: 'degraded',
    failing: [{ key: 'db' }],
  });
  assert.doesNotMatch(pill.title, /undefined/);
});

// The topbar and the registry name one run with one word: the pill used to
// translate stale_data to "stale" while the registry printed the wire enum.
test('the scan status line speaks the shared status vocabulary', () => {
  const stale = buildScanStatusText({
    status: 'stale_data', n_setups: 12, finished_at: '2026-09-04T22:00:30Z',
  });
  assert.match(stale, new RegExp(`${RUN_STATUS_LABELS.stale_data}$`));
  assert.doesNotMatch(stale, /stale_data/);
  // The inline ternary this replaces translated stale_data ONLY, so every other
  // status reached the operator as its wire enum.
  const aborted = buildScanStatusText({
    status: 'aborted', n_setups: null, finished_at: '2026-09-04T22:00:30Z',
  });
  assert.match(aborted, new RegExp(`${RUN_STATUS_LABELS.aborted}$`));
});
