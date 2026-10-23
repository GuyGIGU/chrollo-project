import { readFileSync } from 'node:fs';
import { test as base, expect } from '@playwright/test';

// Synthetic UI data, never a market or scoring acceptance fixture. Python's
// contract tests validate these same bytes against the backend response model.
const fixture = JSON.parse(readFileSync(new URL('./fixtures/screener.json', import.meta.url), 'utf8'));

export const test = base.extend({
  api: async ({ page }, provideApi) => {
    const api = {
      payload: structuredClone(fixture),
      feedback: {}, watches: [], writes: [], unexpected: [], errors: [],
      failFeedback: false, failScreener: false,
      likes: [], failLikesLoad: false, failLikeSave: false, failWatchlist: false, failSummary: false,
      likeGate: null, watchGate: null, deleteGate: null,
      quotes: {}, failPrices: false, failWatchlistLoad: false, history: [], gains: {},
      candleRequests: [], failCandles: false,
    };
    page.on('pageerror', (error) => api.errors.push(error.message));
    await page.route('**/*', async (route) => {
      const request = route.request();
      const url = new URL(request.url());
      // Only built frontend documents/assets may reach the preview server.
      if (url.origin === 'http://127.0.0.1:4173'
        && ((request.isNavigationRequest() && ['/screener', '/watchlist'].includes(url.pathname))
          || url.pathname.startsWith('/assets/')
          || url.pathname === '/favicon.svg')) return route.continue();
      // Keep browser checks independent of the public font CDN.
      if (url.origin === 'https://fonts.googleapis.com' && request.resourceType() === 'stylesheet') {
        return route.fulfill({ contentType: 'text/css', body: '' });
      }
      const method = request.method();
      const path = url.pathname;
      const reply = (json, status = 200) => route.fulfill({ status, json });
      const unexpected = () => {
        api.unexpected.push(`${method} ${request.url()}`);
        return reply({ detail: 'Unexpected browser-test request' }, 501);
      };
      if (url.origin !== 'http://127.0.0.1:4173') return unexpected();
      if (method === 'GET') {
        if (path === '/screener-data/') {
          if (api.failScreener) return reply({ detail: 'Synthetic outage' }, 503);
          const universe = url.searchParams.get('universe') || 'us_stocks';
          return reply(universe === 'us_stocks' ? api.payload : {
            ...api.payload, universe, ordered_tickers: [], chart_data: {},
          });
        }
        if (path === '/screener-summary/') return api.failSummary
          ? reply({ detail: 'Synthetic refresh failure' }, 503) : reply({ scanned_at: api.payload.scanned_at });
        if (path === '/archive/reviews/read-verdict') return reply(api.feedback[url.searchParams.get('ticker')] || {
          verdict: null, grade_verdict: null, note: null, engine_config_version: null,
        });
        if (path === '/watchlist/') return api.failWatchlistLoad ? reply({ detail: 'Synthetic list failure' }, 503) : reply(api.watches);
        if (path === '/live-prices/') return api.failPrices ? reply({ detail: 'Synthetic quote failure' }, 503) : reply(api.quotes);
        if (path === '/watchlist/best-gains') return reply(api.gains);
        if (path === '/watchlist/review') return reply({ weeks: api.history.length ? [{ week_start: '2026-10-19', saves: api.history }] : [] });
        if (/^\/watchlist\/\d+\/replay$/.test(path)) {
          const watch = api.watches.find((item) => item.id === Number(path.split('/')[2])) || api.history[0];
          return reply({ watch, snapshot_status: 'ok', archive_status: 'never_archived', archive: null,
            snapshot: { snapshot_version: 1, scan_identity: api.payload.scan_identity,
              entry: api.payload.chart_data[watch?.ticker] || api.payload.chart_data.DEMOA } });
        }
        if (path.startsWith('/candles/')) {
          api.candleRequests.push(request.url());
          if (api.failCandles) return reply({ detail: 'Synthetic candle failure' }, 503);
          const entry = api.payload.chart_data[decodeURIComponent(path.split('/')[2])] || api.payload.chart_data.DEMOA;
          return reply({ status: 'ok', last_bar_date: '2026-10-22', price_series: 'as_traded', frames: {
            daily: { candles: entry.candles, volumes: [], status: 'ok' },
            weekly: { candles: [], volumes: [], status: 'empty' }, monthly: { candles: [], volumes: [], status: 'empty' },
          } });
        }
        if (path === '/archive/reviews/liked') return api.failLikesLoad
          ? reply({ detail: 'Synthetic likes load failure' }, 503) : reply({ tickers: api.likes });
        if (path === '/archive/reviews/passed') return reply({ tickers: [] });
        if (path === '/calibration/box-fixes' || path === '/archive/setups' || path === '/trades/') return reply([]);
        if (path === '/ibkr/status') return reply({ connected: false, available: false, mode: 'live' });
        if (path === '/journal-stats/') return reply({ total_trades: 0, total_pnl: 0 });
        if (path === '/scan-status/latest') return reply({ status: 'success' });
        if (path === '/health') return reply({ status: 'ok' });
        if (path === '/scan-stream/active') return reply({ active: false });
        if (path === '/market-data/status') return reply({ health_state: 'healthy', can_evaluate: true });
      }
      if (method === 'POST' && path === '/screener-data/earnings') return reply({});
      if (method === 'POST' && path === '/archive/reviews/read-verdict') {
        const body = request.postDataJSON();
        api.writes.push({ path, body });
        if (api.failFeedback) return reply({ detail: 'Synthetic save failure' }, 503);
        api.feedback[body.ticker] = body;
        return reply(body);
      }
      if (method === 'POST' && path === '/archive/reviews/like') {
        const body = request.postDataJSON();
        api.writes.push({ path, body });
        if (api.likeGate) await api.likeGate;
        if (api.failLikeSave) return reply({ detail: 'Synthetic like save failure' }, 503);
        const liked = !api.likes.includes(body.ticker);
        api.likes = liked ? [...api.likes, body.ticker] : api.likes.filter((ticker) => ticker !== body.ticker);
        return reply({ liked });
      }
      if (method === 'POST' && path.startsWith('/watchlist/')) {
        const body = request.postDataJSON();
        api.writes.push({ path, body });
        if (api.watchGate) await api.watchGate;
        if (api.failWatchlist) return reply({ detail: 'Synthetic watchlist save failure' }, 503);
        const item = { id: Math.max(0, ...api.watches.map((watch) => watch.id)) + 1, ticker: path.split('/').at(-1), pinned: true,
          created_at: '2026-10-22T22:01:00Z', save_date: '2026-10-22',
          pin_scan_date: body.scan_date, pin_universe_key: body.universe };
        api.watches.push(item);
        return reply(item);
      }
      if (method === 'DELETE' && path.startsWith('/watchlist/')) {
        api.writes.push({ path, method });
        if (api.deleteGate) await api.deleteGate;
        api.watches = api.watches.filter((item) => item.ticker !== decodeURIComponent(path.split('/').at(-1)));
        return reply({ ok: true });
      }
      // Fail closed: no unknown API, external origin, broker or scan request
      // can fall through to a backend or be hidden behind an empty mock object.
      return unexpected();
    });
    await provideApi(api);
    expect(api.unexpected, 'all network requests must be explicitly mocked').toEqual([]);
    expect(api.errors, 'the UI must not crash').toEqual([]);
  },
});
export { expect };
