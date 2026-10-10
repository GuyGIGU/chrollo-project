// Council review 2026-09-07, finding 4 — the client half. The server keeps the
// job running past a disconnect; this is the decision to pick it back up.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import {
  activeStreamUrl,
  attachStreamUrl,
  cancelStreamUrl,
  endJob,
  reattachTarget,
  resultsStale,
  startStreamUrl,
} from './scanStream.js';

test('a mount re-attaches to the job the server says is running', () => {
  assert.equal(reattachTarget({ active: true, job: 'evaluation', run_id: 42 }), 'evaluation');
  assert.equal(reattachTarget({ active: true, job: 'download', run_id: 43 }), 'download');
});

test('a mount with nothing running attaches to nothing', () => {
  for (const state of [
    null, undefined, {}, { active: false, job: null },
    { active: false, job: 'evaluation' },   // a finished job is not re-attachable
    { active: true, job: null },
  ]) {
    assert.equal(reattachTarget(state), null, JSON.stringify(state));
  }
});

test('a job name the client cannot map is refused, never turned into a URL', () => {
  assert.equal(reattachTarget({ active: true, job: 'maturation' }), null);
  assert.equal(reattachTarget({ active: true, job: '../../etc' }), null);
  // The full-scan route is labelled 'scan' at the source (review A6). No surface
  // starts it, so the client has no readout for it and refuses it rather than
  // re-attaching as a cached evaluation — the wrong job under the Retry button.
  assert.equal(reattachTarget({ active: true, job: 'scan' }), null);
});

test('a stream the operator just started is not stomped by a late answer', () => {
  assert.equal(reattachTarget({ active: true, job: 'evaluation' }, true), null);
});

test('the stream URLs', () => {
  assert.equal(startStreamUrl('', 'evaluation'), '/run-evaluation-stream/');
  assert.equal(startStreamUrl('', 'download'), '/download-data-stream/');
  assert.equal(attachStreamUrl(''), '/scan-stream/attach/');
  assert.equal(activeStreamUrl('http://x'), 'http://x/scan-stream/active');
  assert.equal(cancelStreamUrl('http://x'), 'http://x/scan-stream/cancel');
});

// Operator 2026-10-03: Evaluate keeps the last scan on screen, dimmed, instead of
// blanking the grid for the whole run.
test('a running evaluation dims the results it is about to replace', () => {
  assert.equal(resultsStale('evaluation', false), true);
});

test('a data download never dims the scan, which it does not rewrite', () => {
  assert.equal(resultsStale('download', false), false);
});

test('the dim holds through the re-fetch after the job ends', () => {
  assert.equal(resultsStale(null, true), true);
});

test('with no job and nothing awaited, the results are current', () => {
  assert.equal(resultsStale(null, false), false);
});

// endJob is the ORDER behind that dim; the hook that calls it has no test of its own.
// The re-fetch is held open so the test can look while it is in flight.
const recordEnd = (refetch, { fail = false } = {}) => {
  const calls = [];
  let release;
  const landed = new Promise((resolve) => { release = resolve; });
  const done = endJob(refetch, {
    holdDim: (on) => calls.push(`dim ${on}`),
    clearJob: () => calls.push('clear'),
    reloadStatus: async () => { calls.push('status'); },
    reloadResults: async () => {
      calls.push('fetch');
      await landed;
      if (fail) throw new Error('re-fetch failed');
      calls.push('fetched');
    },
  });
  return { calls, release, done };
};
const settle = () => new Promise((resolve) => setTimeout(resolve, 0));

test('an evaluation ends with the dim up before the job clears, and down only after the re-fetch', async () => {
  const { calls, release, done } = recordEnd(true);
  assert.deepEqual(calls.slice(0, 2), ['dim true', 'clear'], 'the old cards light up for a tick');
  await settle();
  assert.deepEqual(calls, ['dim true', 'clear', 'status', 'fetch'], 'the dim dropped while the re-fetch was in flight');
  release();
  await done;
  assert.deepEqual(calls, ['dim true', 'clear', 'status', 'fetch', 'fetched', 'dim false']);
});

test('a re-fetch that fails still lifts the dim', async () => {
  const { calls, release, done } = recordEnd(true, { fail: true });
  release();
  await assert.rejects(done);
  assert.equal(calls.at(-1), 'dim false');
});

test('a job that did not rewrite the scan clears without dimming or re-fetching', async () => {
  const { calls, release, done } = recordEnd(false);
  release();   // so a stray re-fetch fails here instead of hanging the run
  await done;
  assert.deepEqual(calls, ['clear', 'status']);
});

// Both ends of a run reach endJob with the real dim setter: the export line always
// re-fetches, [DONE] only for an evaluation that has not already.
test('useScanRunner ends a run through endJob at both ends', () => {
  const src = readFileSync(new URL('../hooks/useScanRunner.js', import.meta.url), 'utf8');
  assert.match(src, /endJob\(refetch, \{\s*holdDim: setAwaitingResults,/);
  assert.match(src, /resultsRevealed = true;\s*await endThisJob\(true\);/);
  assert.match(src, /const refetch = job === 'evaluation' && !resultsRevealed && !jobHadError;\s*await endThisJob\(refetch\);/);
  assert.doesNotMatch(src, /setAwaitingResults\(/, 'a direct dim write outside endJob');
});
