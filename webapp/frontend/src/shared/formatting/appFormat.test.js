import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { buildHealthPill, buildScanStatusText, failingChecks, scanStatusColor } from './appFormat.js';
import {
  RUN_STATUS_LABELS, RUN_VERDICT_LABELS, RUN_VERDICT_TONES,
} from '../presentation/wireVocabulary.js';

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
      '..', '..', 'features', 'screener', 'components', 'ScanHistoryModal.jsx'), 'utf8');
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

// ---------------------------------------------------------------- verdict --
//
// The operator's cut: the pill's headline is one of TWO states — press re-scan,
// or ping the developer. It is resolved server-side and read here.

test('the pill wears the verdict the wire sent, in the operator words', () => {
  const rerun = buildHealthPill({
    status: 'degraded',
    verdict: 'rerunnable',
    failing: [{ key: 'last_scan', label: 'Last scan', reason: 'shut down mid-run' }],
  });
  assert.equal(rerun.label, RUN_VERDICT_LABELS.rerunnable);
  assert.equal(rerun.color, RUN_VERDICT_TONES.rerunnable);
  assert.doesNotMatch(rerun.label, /rerunnable/);

  const attention = buildHealthPill({
    status: 'degraded',
    verdict: 'needs_attention',
    failing: [{ key: 'scheduler', label: 'Nightly scan timer', reason: 'off' }],
  });
  assert.equal(attention.label, RUN_VERDICT_LABELS.needs_attention);
  assert.equal(attention.color, RUN_VERDICT_TONES.needs_attention);
  assert.notEqual(attention.label, rerun.label);
});

// EC-28, and the shape the derivation would most plausibly take: "several
// things are wrong, so it must be serious". THREE failing checks and the wire
// still says re-runnable — that judgment is the backend's, not this file's.
test('the pill never works the verdict out from how much is failing', () => {
  const pill = buildHealthPill({
    status: 'degraded',
    verdict: 'rerunnable',
    failing: [
      { key: 'last_scan', label: 'Last scan', reason: 'shut down mid-run' },
      { key: 'screener_data', label: 'Screener results file', reason: 'missing' },
      { key: 'db', label: 'Database', reason: 'locked' },
    ],
  });
  assert.equal(pill.label, RUN_VERDICT_LABELS.rerunnable);
});

test('healthy stays healthy, and an old backend still reads as Degraded', () => {
  assert.equal(buildHealthPill({ status: 'ok', checks: {} }).label, 'Healthy');
  // No `verdict` on the wire = a backend that has not been restarted yet.
  const old = buildHealthPill({ status: 'degraded', failing: [{ key: 'db' }] });
  assert.equal(old.label, 'Degraded');
  assert.equal(old.color, 'var(--danger)');
});

// The drift pin the wire-carries-verdicts rule asks for: the two verdict slugs
// exist in exactly ONE frontend file — the vocabulary. The moment either name
// appears in a rendering module it is because something there is comparing
// against it, i.e. deciding the verdict in JS.
test('no frontend module outside the vocabulary names a verdict slug', () => {
  const here = path.dirname(fileURLToPath(import.meta.url));
  const files = [
    ['shared', 'formatting', 'appFormat.js'],
    ['features', 'screener', 'components', 'ScanHistoryModal.jsx'],
    ['app', 'components', 'AppTopbar.jsx'],
    ['app', 'components', 'AppShell.jsx'],
  ];
  for (const parts of files) {
    const src = fs.readFileSync(path.join(here, '..', '..', ...parts), 'utf8');
    assert.ok(!src.includes('needs_attention'), parts.join('/'));
    assert.ok(!src.includes('rerunnable'), parts.join('/'));
  }
});

// He asked for the two states UP FRONT. The registry has no render test, so pin
// that both of its surfaces actually reach for the wire's verdict — a row's own,
// and the app-level one over the failing checks.
test('the registry leads with the verdict on both of its surfaces', () => {
  const src = fs.readFileSync(
    path.join(path.dirname(fileURLToPath(import.meta.url)),
      '..', '..', 'features', 'screener', 'components', 'ScanHistoryModal.jsx'), 'utf8');
  assert.ok(src.includes('verdict={run.verdict}'));
  assert.ok(src.includes('verdict={health?.verdict}'));
  assert.ok(src.includes('RUN_VERDICT_LABELS[verdict]'));
});
