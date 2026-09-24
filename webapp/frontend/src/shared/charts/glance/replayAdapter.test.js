import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import {
  ARCHIVE_STATUS_COPY,
  SNAPSHOT_VERSION,
  adaptReplaySnapshot,
  replayProvenance,
} from './replayAdapter.js';

// THE immutable v1 fixture — the same file the backend round-trip test reads
// (tests/fixtures/watchlist_snapshot_v1.json). If a shape change breaks this
// adapter on v1 bytes, old saves stop rendering: that is the defect this
// file exists to catch, not a fixture to "update".
const FIXTURE = JSON.parse(readFileSync(
  new URL('../../../../../../tests/fixtures/watchlist_snapshot_v1.json', import.meta.url),
  'utf-8',
));

test('the v1 fixture adapts to a renderable modal payload', () => {
  const adapted = adaptReplaySnapshot(FIXTURE);
  assert.ok(adapted, 'v1 snapshot must stay renderable');
  // Byte-faithful passthrough: the stored entry IS the render source (EC-28) —
  // the adapter may never normalize, fill, or strip it.
  assert.deepEqual(adapted.entry, FIXTURE.entry);
  assert.deepEqual(adapted.scanIdentity, FIXTURE.scan_identity);
});

test('the fixture entry carries every key the chart surfaces render from', () => {
  // The modal/mini chart contract (useDailyStructureChart + chartGeometry):
  // absence of one of these in a v1 save means the replay draws wrong or not
  // at all — keep the fixture honest to the minimum render set.
  for (const key of ['candles', 'volumes', 'base_len', 'R', 'S',
    'tier', 'score', 'setup', 'price', 'trigger']) {
    assert.ok(key in FIXTURE.entry, `fixture entry missing ${key}`);
  }
  assert.equal(FIXTURE.snapshot_version, SNAPSHOT_VERSION);
});

test('unknown versions and empty snapshots are refused, not mis-drawn', () => {
  assert.equal(adaptReplaySnapshot(null), null);
  assert.equal(adaptReplaySnapshot({}), null);
  assert.equal(
    adaptReplaySnapshot({ ...FIXTURE, snapshot_version: 2 }), null,
    'a future version must be refused rather than rendered as v1');
  assert.equal(
    adaptReplaySnapshot({ snapshot_version: 1, entry: { candles: [] } }), null,
    'no candles -> nothing to draw');
});

test('every archive verdict in the closed registry has copy', () => {
  // Frontend twin of services/watchlist_ledger.ARCHIVE_STATUSES (EC-33): a
  // verdict the server can emit without copy here would render as raw enum.
  const registry = ['matched', 'rewritten', 'purged', 'never_archived', 'no_pin'];
  for (const status of registry) {
    assert.equal(typeof ARCHIVE_STATUS_COPY[status], 'string', status);
    assert.ok(ARCHIVE_STATUS_COPY[status].length > 0, status);
  }
  assert.deepEqual(Object.keys(ARCHIVE_STATUS_COPY).sort(), registry.sort());
});

test('replayProvenance resolves the frame strings from the envelope alone', () => {
  const provenance = replayProvenance({
    watch: {
      pin_scan_date: '2026-08-11',
      save_date: '2026-08-12',
      unstarred_at: null,
    },
    archive_status: 'matched',
    snapshot: FIXTURE,
  });
  assert.equal(provenance.asScanned, '2026-08-11');
  assert.equal(provenance.savedOn, '2026-08-12');
  assert.equal(provenance.unstarred, false);
  assert.equal(provenance.archiveNote, ARCHIVE_STATUS_COPY.matched);
  assert.equal(provenance.renderable, true);
});

test('an unpinned save without a snapshot degrades honestly', () => {
  const provenance = replayProvenance({
    watch: { pin_scan_date: null, save_date: '2026-08-12', unstarred_at: '2026-08-12T09:00:00' },
    archive_status: 'no_pin',
    snapshot: null,
  });
  assert.equal(provenance.asScanned, null);
  assert.equal(provenance.unstarred, true);
  assert.equal(provenance.archiveNote, ARCHIVE_STATUS_COPY.no_pin);
  assert.equal(provenance.renderable, false);
});
