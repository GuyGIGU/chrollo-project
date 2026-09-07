// Council review 2026-09-07, finding 4 — the client half. The server keeps the
// job running past a disconnect; this is the decision to pick it back up.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  activeStreamUrl,
  attachStreamUrl,
  cancelStreamUrl,
  reattachTarget,
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
