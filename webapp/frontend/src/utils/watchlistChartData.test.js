import assert from 'node:assert/strict';
import test from 'node:test';
import {
  CANDLE_REASON_COPY, cardPlan, resolvePaneData, resolveRenderedSelection,
} from './watchlistChartData.js';

const scanEntry = {
  candles: [{ time: '2026-08-13' }, { time: '2026-08-14' }],
  volumes: [{ time: '2026-08-13' }, { time: '2026-08-14' }],
  weekly_candles: [{ time: '2026-08-14' }],
  weekly_volumes: [{ time: '2026-08-14' }],
  weekly_box: { r: 12, s: 10 },
  monthly_candles: [{ time: '2026-08-31' }],
  monthly_volumes: [{ time: '2026-08-31' }],
  monthly_box: null,
  R: 12, S: 10, base_len: 30,
};

const envelope = {
  status: 'ok',
  last_bar_date: '2026-08-14',
  price_series: 'as_traded',
  frames: {
    daily: { status: 'ok', forming_last_bar: false, candles: [{ time: '2026-08-14' }], volumes: [{ time: '2026-08-14' }] },
    weekly: { status: 'ok', forming_last_bar: false, candles: [{ time: '2026-08-14' }], volumes: [{ time: '2026-08-14' }] },
    monthly: { status: 'ok', forming_last_bar: true, candles: [{ time: '2026-08-31' }], volumes: [{ time: '2026-08-31' }] },
  },
};

// ── rendered selection is derived, never synced ────────────────────────────

test('selection: chosen ticker wins while it is on the list', () => {
  const records = [{ ticker: 'AAA' }, { ticker: 'BBB' }];
  assert.equal(resolveRenderedSelection('BBB', records), 'BBB');
});

test('selection: a removed chosen ticker falls to the first record', () => {
  const records = [{ ticker: 'AAA' }, { ticker: 'BBB' }];
  assert.equal(resolveRenderedSelection('GONE', records), 'AAA');
  assert.equal(resolveRenderedSelection(null, records), 'AAA');
});

test('selection: an empty watchlist renders nothing', () => {
  assert.equal(resolveRenderedSelection('AAA', []), null);
  assert.equal(resolveRenderedSelection(null, null), null);
});

// ── the atomic pane contract ───────────────────────────────────────────────

test('overlay on + artifact: the scan row rides WHOLESALE', () => {
  const pane = resolvePaneData({
    scanEntry, scanDate: '2026-08-14',
    endpointEntry: { status: 'ready', envelope }, overlayOn: true,
  });
  assert.equal(pane.source, 'scan');
  assert.equal(pane.overlayDrawn, true);
  // The daily pane's object IS the scan entry — same reference, no copy, no
  // field-level merge path.
  assert.equal(pane.daily, scanEntry);
  assert.equal(pane.weekly.box, scanEntry.weekly_box);
  assert.equal(pane.provenance.scanDate, '2026-08-14');
});

test('overlay off with an artifact present: fresh endpoint candles, clean', () => {
  const pane = resolvePaneData({
    scanEntry, scanDate: '2026-08-14',
    endpointEntry: { status: 'ready', envelope }, overlayOn: false,
  });
  assert.equal(pane.source, 'endpoint');
  assert.equal(pane.overlayAvailable, true);
  assert.equal(pane.overlayDrawn, false);
  // Clean chart = bare candles + volumes. No overlay fields, no boxes.
  assert.deepEqual(Object.keys(pane.daily).sort(), ['candles', 'volumes']);
  assert.equal(pane.weekly.box, null);
  assert.equal(pane.provenance.lastBarDate, '2026-08-14');
  assert.equal(pane.provenance.forming.monthly, true);
});

test('overlay on but NO artifact: clean endpoint chart, overlay not drawn', () => {
  const pane = resolvePaneData({
    scanEntry: null, scanDate: null,
    endpointEntry: { status: 'ready', envelope }, overlayOn: true,
  });
  assert.equal(pane.source, 'endpoint');
  assert.equal(pane.overlayAvailable, false);
  assert.equal(pane.overlayDrawn, false);
});

test('ticker in neither source: the endpoint verdict is the named reason', () => {
  const missing = {
    ...envelope,
    status: 'unknown_ticker',
    frames: {
      daily: { status: 'empty', forming_last_bar: null, candles: [], volumes: [] },
      weekly: { status: 'empty', forming_last_bar: null, candles: [], volumes: [] },
      monthly: { status: 'empty', forming_last_bar: null, candles: [], volumes: [] },
    },
  };
  const pane = resolvePaneData({
    scanEntry: null, scanDate: null,
    endpointEntry: { status: 'ready', envelope: missing }, overlayOn: true,
  });
  assert.equal(pane.source, null);
  assert.equal(pane.reason, 'unknown_ticker');
  assert.equal(pane.daily, null);
});

test('no answer yet / failed fetch: loading and error reasons', () => {
  assert.equal(resolvePaneData({
    scanEntry: null, scanDate: null, endpointEntry: undefined, overlayOn: true,
  }).reason, 'loading');
  assert.equal(resolvePaneData({
    scanEntry: null, scanDate: null,
    endpointEntry: { status: 'error' }, overlayOn: true,
  }).reason, 'error');
});

test('overlay off while the endpoint is still pending: the reason shows — never bare scan candles', () => {
  // The atomic pane contract has NO third state: with the overlay off, the
  // pane is endpoint-sourced or it is a named reason — a "helpful" railless
  // render of the scan row would be a cross-source mix.
  const pane = resolvePaneData({
    scanEntry, scanDate: '2026-08-14', endpointEntry: undefined, overlayOn: false,
  });
  assert.equal(pane.source, null);
  assert.equal(pane.reason, 'loading');
  assert.equal(pane.overlayAvailable, true);
  assert.equal(pane.daily, null);
});

test('null scan fields never crash the resolver', () => {
  const bare = { candles: [{ time: '2026-08-14' }], volumes: [] };
  const pane = resolvePaneData({
    scanEntry: bare, scanDate: null, endpointEntry: undefined, overlayOn: true,
  });
  assert.equal(pane.source, 'scan');
  assert.deepEqual(pane.weekly.candles, []);
  assert.equal(pane.weekly.box, null);
});

// ── the card plan ──────────────────────────────────────────────────────────

test('cards: a scanned ticker carries the scan row WHOLESALE', () => {
  const { cards, toFetch } = cardPlan(['AAA'], { AAA: scanEntry }, {});
  assert.equal(cards.AAA.kind, 'scan');
  // Same reference — the card renders the full screener card from the exact
  // artifact row, no slicing, no field-level copy.
  assert.equal(cards.AAA.data, scanEntry);
  assert.deepEqual(toFetch, []);
});

test('cards: an off-scan ticker becomes a clean card wearing the CELL itself', () => {
  const cell = { status: 'ok', candles: [{ time: 'x' }], volumes: [{ time: 'x' }] };
  const { cards } = cardPlan(['CACHED'], {}, { CACHED: cell });
  assert.equal(cards.CACHED.kind, 'clean');
  // Same reference — the store cell's identity IS the chart's rebuild key;
  // a fresh wrapper per plan run would tear the chart down on every pass.
  assert.equal(cards.CACHED.data, cell);
});

test('cards: batch verdicts and unfetched names are voids with named reasons', () => {
  const { cards, toFetch } = cardPlan(
    ['DEAD', 'MISSING'], {}, { DEAD: { status: 'no_cache', candles: [], volumes: [] } });
  assert.deepEqual(cards.DEAD, { kind: 'void', reason: 'no_cache' });
  assert.deepEqual(cards.MISSING, { kind: 'void', reason: 'loading' });
  assert.deepEqual(toFetch, ['MISSING']);
});

test('cards: an empty-candles scan entry falls through to the endpoint', () => {
  const { toFetch } = cardPlan(['AAA'], { AAA: { candles: [] } }, {});
  assert.deepEqual(toFetch, ['AAA']);
});

test('every no-candles reason has plain words', () => {
  // The endpoint's closed verdicts + the store's transport states — a verdict
  // without copy would surface as undefined text in the pane.
  const reasons = ['loading', 'error', 'unknown_ticker', 'no_cache', 'no_drawable_bars'];
  for (const reason of reasons) {
    assert.equal(typeof CANDLE_REASON_COPY[reason], 'string');
    assert.ok(CANDLE_REASON_COPY[reason].length > 0);
  }
});
