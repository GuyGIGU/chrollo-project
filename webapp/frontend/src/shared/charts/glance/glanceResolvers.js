import { API_BASE } from '../../../api/base';
import { adaptReplaySnapshot } from '../../../features/watchlist/presentation/replayAdapter';
import { createGlanceCache } from './glanceCache';
import { glanceChartKey } from './glanceMath';

// The per-surface resolver seam (plan Task 11). Each returns a glance object —
// { status, entry?, header?, note?, stamp? } — synchronously where it can, as a
// promise where it must. Resolvers never render; the shell never fetches.
//
// The ladder, cheapest first:
//   artifact  — the scan already in memory. ZERO network, synchronous.
//   snapshot  — a pinned watchlist save's stored chart, via the replay route.
//   archive   — the only path that genuinely must ask the server for candles,
//               and the only one that can reach the vendor. Bounded, cached,
//               single-flight.

const CLIENT_HEADER = { 'X-Chrollo-Client': 'chrollo-dashboard' };

// One cache per path, so a big archive envelope can never evict the snapshot a
// watchlist sweep is re-reading.
const snapshotCache = createGlanceCache();
const archiveCache = createGlanceCache();

// The header renders only fields already on the wire (EC-28).
const artifactHeader = (ticker, entry, context) => ({
  ticker,
  tier: entry?.tier ?? null,
  // The 0-100 grade - the number the tier beside it derives from. The legacy
  // raw score retired from display 2026-08-22; the scales never coalesce, so
  // an ungraded (pre-flip) entry shows nothing rather than the other scale.
  grade: entry?.ta_grade == null ? null : Math.round(Number(entry.ta_grade)),
  context: context || entry?.setup || '',
});

// --- artifact (Home watchlist, screener watchlist panel) ---
//
// `stamp` is the SCAN the payload came from, not the payload object: the
// screener store hands out a fresh chart_data object on every landed fetch, so
// an identity-keyed chart would rebuild itself mid-hover for no reason.
export function artifactGlance(chartData, ticker, scanStamp) {
  const entry = chartData?.[ticker];
  if (!entry || !entry.candles?.length) {
    return {
      status: 'empty',
      header: { ticker, tier: null, score: null, context: '' },
      note: 'not in the latest scan',
    };
  }
  return {
    status: 'ready',
    entry,
    header: artifactHeader(ticker, entry, entry.setup),
    stamp: scanStamp,
    chartKey: glanceChartKey(ticker, scanStamp),
  };
}

// --- stored snapshot (a pinned watchlist save) ---
//
// Goes through adaptReplaySnapshot, which refuses a wrong snapshot_version and
// a zero-candle payload — its null IS the empty verdict, and reading
// snapshot.entry directly would bypass that gate.
export function snapshotGlance(watchId, ticker) {
  if (watchId == null) {
    return Promise.resolve({
      status: 'empty',
      header: { ticker, tier: null, score: null, context: '' },
      note: 'saved before charts were stored',
    });
  }
  return snapshotCache.load(`watch:${watchId}`, () =>
    fetch(`${API_BASE}/watchlist/${watchId}/replay`)
      .then((response) => {
        if (!response.ok) throw new Error(`replay ${response.status}`);
        return response.json();
      })
      .then((replay) => {
        const adapted = adaptReplaySnapshot(replay?.snapshot);
        if (!adapted) {
          return {
            status: 'empty',
            header: { ticker, tier: null, score: null, context: '' },
            note: 'saved before charts were stored',
          };
        }
        const stamp = adapted.scanIdentity?.scan_date || null;
        return {
          status: 'ready',
          entry: adapted.entry,
          header: artifactHeader(ticker, adapted.entry, stamp ? `as scanned ${stamp}` : ''),
          stamp,
          chartKey: glanceChartKey(ticker, `snap:${watchId}`),
        };
      }),
  );
}

// --- archive row (the one server fetch) ---
//
// Asks the EXISTING chart route for its bounded variant: same ticker, same
// window arithmetic, just fewer bars on the wire. Cached per setup id and
// single-flight, because hovering is a sweep and this path reaches the provider
// the nightly scans depend on.
export function archiveGlance(setupId, ticker) {
  if (setupId == null) {
    return Promise.resolve({
      status: 'empty',
      header: { ticker, tier: null, score: null, context: '' },
    });
  }
  return archiveCache.load(`archive:${setupId}`, () =>
    fetch(`${API_BASE}/archive/setups/${setupId}/chart?glance=1`, { headers: CLIENT_HEADER })
      .then((response) => {
        if (!response.ok) throw new Error(`archive chart ${response.status}`);
        return response.json();
      })
      .then((entry) => {
        if (!entry?.candles?.length) {
          return {
            status: 'empty',
            header: { ticker, tier: entry?.tier ?? null, score: null, context: '' },
            note: 'no market data for this window',
          };
        }
        return {
          status: 'ready',
          entry,
          header: artifactHeader(ticker, entry, entry.setup),
          stamp: `archive:${setupId}`,
          chartKey: glanceChartKey(ticker, `archive:${setupId}`),
        };
      }),
  );
}

export const __caches = { snapshotCache, archiveCache };
