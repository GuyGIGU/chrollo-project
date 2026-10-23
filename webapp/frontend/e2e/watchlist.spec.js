import { test, expect } from './mockApi.js';

const list = (page) => page.getByRole('table', { name: 'Watchlist tickers', exact: true });
const row = (page, ticker) => list(page).locator(`tbody tr[data-ticker="${ticker}"]`);
function populate(api) {
  api.watches = [
    { id: 1, ticker: 'DEMOB', save_date: '2026-10-22', pinned: true, pin_scan_date: '2026-10-22',
      pin_universe_key: 'us_stocks', saved_setup: 'VCP', saved_price: 100,
      saved_market_cap: 2e9, saved_sector: 'Technology', saved_industry: 'Software' },
    { id: 2, ticker: 'OLD', save_date: '2026-09-20', pinned: false, saved_price: null },
  ];
  api.quotes = { DEMOB: 110, OLD: 25 };
  api.history = api.watches.map((item) => ({ ...item, active: true, has_snapshot: true,
    saved_at: `${item.save_date}T22:00:00Z`, origin: 'user', setup: item.saved_setup, price: item.saved_price }));
}

test('watchlist is a searchable, sortable ticker ledger including off-scan names', async ({ page, api }) => {
  populate(api);
  await page.goto('/watchlist');
  await expect(list(page).locator('tbody tr')).toHaveCount(2);
  await expect(row(page, 'DEMOB')).toContainText('22/10/26');
  await expect(row(page, 'DEMOB')).toContainText('VCP');
  await expect(row(page, 'DEMOB')).toContainText('+10.0%');
  await expect(row(page, 'DEMOB')).toContainText('Software');
  await expect(row(page, 'OLD')).toContainText('No');
  await expect(row(page, 'OLD').getByRole('cell').nth(6)).toHaveText('—');
  await expect(page.locator('.screener-card, .wl-daily-canvas')).toHaveCount(0);
  expect(api.candleRequests).toEqual([]);
  await list(page).getByRole('button', { name: 'Added', exact: false }).click();
  await expect(list(page).locator('tbody tr').first()).toHaveAttribute('data-ticker', 'OLD');
  await page.getByPlaceholder('Search watchlist…').fill('old');
  await expect(list(page).locator('tbody tr')).toHaveCount(1);
  await expect(list(page).locator('tbody tr')).toHaveAttribute('data-ticker', 'OLD');
  await page.getByPlaceholder('Search watchlist…').fill('missing');
  await expect(page.getByText('No saved tickers match this search.', { exact: false })).toBeVisible();
  await page.getByRole('button', { name: 'Clear search', exact: true }).click();
  await expect(list(page).locator('tbody tr')).toHaveCount(2);
  await page.setViewportSize({ width: 640, height: 900 });
  const bounds = await page.locator('.wl-ledger .instrument-well').evaluate((element) => ({
    right: element.getBoundingClientRect().right, width: element.clientWidth, contentWidth: element.scrollWidth,
  }));
  expect(bounds.right).toBeLessThanOrEqual(640);
  expect(bounds.contentWidth).toBeGreaterThan(bounds.width);
  expect(api.writes).toEqual([]);
});

test('row inspection retains multi-timeframe charts, pin routing and keyboard return focus', async ({ page, api }) => {
  populate(api);
  await page.goto('/watchlist');
  await row(page, 'DEMOB').focus();
  await page.keyboard.press('Enter');
  await expect(page.getByRole('dialog', { name: 'DEMOB watchlist charts' })).toBeVisible();
  await expect(page.locator('.wl-daily-canvas')).toHaveCount(1);
  await expect(page.locator('.wl-htf-pane')).toHaveCount(2);
  await expect.poll(() => api.candleRequests.length).toBe(1);
  expect(api.candleRequests[0]).toContain('universe=us_stocks');
  api.failCandles = true;
  await page.getByRole('button', { name: 'Next', exact: true }).click();
  await expect(page.getByRole('dialog', { name: 'OLD watchlist charts' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Retry candles', exact: true })).toBeVisible();
  api.failCandles = false;
  await page.getByRole('button', { name: 'Retry candles', exact: true }).click();
  await expect(page.locator('.wl-daily-canvas')).toHaveCount(1);
  await page.keyboard.press('Escape');
  await expect(row(page, 'OLD')).toBeFocused();
  await page.keyboard.press('ArrowUp');
  await expect(row(page, 'DEMOB')).toBeFocused();
  await expect(row(page, 'DEMOB')).toHaveAttribute('aria-current', 'true');
  expect(api.writes).toEqual([]);
});

test('the chart dialog leaves modified arrows to the browser and fits the screen at 130% UI scale', async ({ page, api }) => {
  populate(api);
  await page.goto('/watchlist');
  await page.evaluate(() => document.documentElement.style.setProperty('--ui-scale', '1.3'));
  await row(page, 'DEMOB').click();
  const dialog = page.getByRole('dialog', { name: 'DEMOB watchlist charts' });
  await expect(dialog).toBeVisible();
  const box = await dialog.evaluate((element) => {
    const rect = element.getBoundingClientRect();
    return { left: rect.left, top: rect.top, right: rect.right, bottom: rect.bottom,
      width: window.innerWidth, height: window.innerHeight };
  });
  expect(box.left).toBeGreaterThanOrEqual(0);
  expect(box.top).toBeGreaterThanOrEqual(0);
  expect(box.right).toBeLessThanOrEqual(box.width);
  expect(box.bottom).toBeLessThanOrEqual(box.height);
  await dialog.press('Alt+ArrowRight');
  await expect(dialog).toBeVisible();
  await dialog.press('ArrowRight');
  await expect(page.getByRole('dialog', { name: 'OLD watchlist charts' })).toBeVisible();
  expect(api.writes).toEqual([]);
});

test('Undo while the removal is still saving restores the ticker', async ({ page, api }) => {
  populate(api);
  let release;
  api.deleteGate = new Promise((resolve) => { release = resolve; });
  await page.goto('/watchlist');
  await row(page, 'DEMOB').getByRole('button', { name: 'Remove DEMOB from watchlist', exact: true }).click();
  await expect(row(page, 'DEMOB')).toHaveCount(0);
  await page.getByRole('button', { name: 'Undo', exact: true }).click();
  release();
  await expect(row(page, 'DEMOB')).toHaveCount(1);
  await expect.poll(() => api.writes.at(-1)).toEqual(
    { path: '/watchlist/DEMOB', body: { universe: 'us_stocks', scan_date: '2026-10-22' } });
});

test('list actions preserve likes, removal undo identity and saved replay history', async ({ page, api }) => {
  populate(api);
  await page.goto('/watchlist');
  await row(page, 'DEMOB').getByRole('button', { name: 'Like DEMOB', exact: true }).press('Enter');
  await expect.poll(() => api.likes).toEqual(['DEMOB']);
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await row(page, 'DEMOB').getByRole('button', { name: 'Remove DEMOB from watchlist', exact: true }).click();
  await expect(row(page, 'DEMOB')).toHaveCount(0);
  await page.getByRole('button', { name: 'Undo', exact: true }).click();
  await expect(row(page, 'DEMOB')).toHaveCount(1);
  expect(api.writes.at(-1)).toEqual({ path: '/watchlist/DEMOB', body: { universe: 'us_stocks', scan_date: '2026-10-22' } });
  await page.getByRole('button', { name: 'Review history', exact: true }).click();
  const review = page.getByRole('dialog', { name: 'Weekly review', exact: true });
  await expect(review).toContainText('DEMOB');
  await review.getByRole('button', { name: /^DEMOB\b/ }).click();
  await expect(page.getByRole('dialog', { name: 'DEMOB chart lens' })).toBeVisible();
});

test('list failures remain distinct from an empty list and stale quotes are labeled', async ({ page, api }) => {
  api.failWatchlistLoad = true;
  await page.goto('/watchlist');
  await expect(page.getByText('Couldn’t refresh the watchlist.', { exact: false })).toBeVisible();
  await expect(page.getByText('Star a setup on the screener', { exact: false })).toHaveCount(0);
  api.failWatchlistLoad = false;
  populate(api);
  api.failPrices = true;
  await page.getByRole('button', { name: 'Retry', exact: true }).click();
  await expect(row(page, 'DEMOB')).toBeVisible();
  await expect(page.getByText('Quotes could not refresh.', { exact: false })).toBeVisible();
  await expect(row(page, 'DEMOB').getByRole('cell').nth(5)).toHaveText('—');
});

test('the screener has no watchlist filter or manager; stars still save to the tab', async ({ page, api }) => {
  await page.goto('/screener?tier=WATCHLIST');
  await expect(page.locator('.screener-card[data-ticker]')).toHaveCount(3);
  await expect(page.getByRole('button', { name: 'All Tiers', exact: true })).toHaveAttribute('aria-pressed', 'true');
  await expect(page.getByRole('button', { name: /^Watchlist \(/ })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Review', exact: true })).toHaveCount(0);
  expect(api.writes).toEqual([]);
});
