import { test } from 'node:test';
import assert from 'node:assert/strict';

import { buildScanDateStamp } from './scanDateStamp.js';
import { dateTimeShort } from '../../../shared/formatting/format.js';

const iso = (...parts) => new Date(...parts).toISOString();

// The nightly scan of Friday's close. stale_after is the backend's verdict: the
// next slot (Monday 17:00 New York) plus the hang allowance.
const P = {
  scanned_at: '2026-10-02T21:19:00+00:00',
  stale_after: '2026-10-05T23:00:00+00:00',
  scan_identity: { scan_date: '2026-10-02' },
};
const SUNDAY = new Date('2026-10-04T12:00:00Z');
const TUESDAY = new Date('2026-10-06T09:00:00Z');

test('the stamp names the close the scan read, not the day it was written', () => {
  assert.equal(buildScanDateStamp(P, SUNDAY).text, 'Scan Fri 02/10/2026');
});

// Friday's scan is the latest one all weekend: not stale on Sunday.
test('a scan is fresh until a newer one was due', () => {
  assert.equal(buildScanDateStamp(P, SUNDAY).stale, false);
});

test('past its stale_after it reads stale, in Home\'s word, and the title says why', () => {
  const stamp = buildScanDateStamp(P, TUESDAY);
  assert.equal(stamp.stale, true);
  assert.equal(stamp.text, 'Scan Fri 02/10/2026 · stale');
  assert.ok(stamp.title.includes('A newer scan was due by'), stamp.title);
});

test('no payload, or one never scanned, draws no stamp', () => {
  assert.equal(buildScanDateStamp(null), null);
  assert.equal(buildScanDateStamp(undefined), null);
  assert.equal(buildScanDateStamp({ status: 'never_scanned', scanned_at: null }), null);
});

// An older payload with no scan identity falls back to the write time, and the
// tooltip carries both dates without leaking a missing value.
test('without a scan date the stamp shows the write time, and the title names both', () => {
  const Q = { scanned_at: iso(2026, 9, 3, 0, 19) };
  const text = buildScanDateStamp(Q, SUNDAY).text;
  assert.equal(text, `Scan ${dateTimeShort(Q.scanned_at)}`);
  assert.doesNotMatch(text, /undefined|null/);
  const title = buildScanDateStamp(P, SUNDAY).title;
  assert.ok(title.includes(dateTimeShort(P.scanned_at)), title);
  assert.ok(title.includes('Fri 02/10/2026'), title);
});
