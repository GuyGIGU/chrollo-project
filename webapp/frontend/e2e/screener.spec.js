import { test, expect } from './mockApi.js';

const cards = (page) => page.locator('.screener-card[data-ticker]');

test('a card is one size on every window, the Finviz way, and the wall offers no table', async ({ page }) => {
  // Operator Thu 29/10/2026: one chart size whatever the monitor, more of them on a
  // wider one; and "only charts".
  for (const [width, perRow] of [[2560, 5], [1920, 4], [1024, 2]]) {
    await page.setViewportSize({ width, height: 1000 });
    await page.goto('/screener');
    await expect(cards(page)).toHaveCount(3);
    const box = await cards(page).first().boundingBox();
    expect(Math.round(box.width)).toBe(460);
    const tracks = await page.locator('.screener-grid').evaluate((el) => getComputedStyle(el).gridTemplateColumns.split(' ').length);
    expect(tracks).toBe(perRow);
    expect(await page.evaluate(() => getComputedStyle(document.documentElement).getPropertyValue('--ui-scale').trim())).toBe('1');
  }
  await expect(page.getByRole('button', { name: 'Table', exact: true })).toHaveCount(0);
});

test('filters, sorting, chart keyboard navigation and URL reload retain the operator place', async ({ page, api }) => {
  await page.goto('/screener');
  await expect(cards(page)).toHaveCount(3);
  await page.getByPlaceholder('Search ticker...').fill('demob');
  await expect(cards(page)).toHaveCount(1);
  await expect(cards(page)).toHaveAttribute('data-ticker', 'DEMOB');
  await page.reload();
  await expect(page.getByPlaceholder('Search ticker...')).toHaveValue('demob');
  await expect(cards(page)).toHaveCount(1);
  await page.getByPlaceholder('Search ticker...').clear();
  await page.getByRole('button', { name: 'S Tier', exact: true }).click();
  await expect(cards(page)).toHaveCount(1);
  await expect(cards(page)).toHaveAttribute('data-ticker', 'DEMOA');
  await page.getByRole('button', { name: 'All Tiers', exact: true }).click();
  await page.getByRole('button', { name: /▸ Filters/ }).click();
  await page.getByLabel('Sort by:').selectOption('base');
  await expect(cards(page).first()).toHaveAttribute('data-ticker', 'DEMOB');
  await page.getByRole('button', { name: /▸ Filters/ }).click();
  await cards(page).first().press('Enter');
  await expect(page.getByRole('dialog', { name: 'DEMOB chart lens' })).toBeVisible();
  await page.getByRole('button', { name: 'Next', exact: true }).click();
  await expect(page.getByRole('dialog', { name: 'DEMOA chart lens' })).toBeVisible();
  await page.reload();
  await expect(page.getByRole('dialog', { name: 'DEMOA chart lens' })).toBeVisible();
  await page.keyboard.press('Alt+ArrowRight');   // the browser's Forward, never the lens's Next
  await expect(page.getByRole('dialog', { name: 'DEMOA chart lens' })).toBeVisible();
  await page.keyboard.press('ArrowLeft');
  await expect(page.getByRole('dialog', { name: 'DEMOB chart lens' })).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.getByRole('dialog', { name: /chart lens/ })).toHaveCount(0);
  await expect(cards(page).first()).toBeFocused();
  expect(api.writes).toEqual([]);
});

test('feedback persists, rolls back failed saves, and refuses an old engine judgment', async ({ page, api }) => {
  await page.goto('/screener?t=DEMOA');
  const read = page.getByRole('button', { name: 'Tells it right', exact: true });
  const grade = page.getByRole('button', { name: 'About right', exact: true });
  await expect(grade).toBeDisabled();
  await read.click();
  await expect(read).toBeEnabled();
  await grade.click();
  await expect(grade).toBeEnabled();
  expect(api.writes.at(-1).body).toMatchObject({
    ticker: 'DEMOA', scan_date: '2026-10-22', universe_type: 'us_equities',
    engine_config_version: 'synthetic-browser-fixture-v1', verdict: 'agree', grade_verdict: 'agree',
  });
  await page.reload();
  await expect(read).toHaveAttribute('aria-pressed', 'true');
  await expect(grade).toHaveAttribute('aria-pressed', 'true');
  api.failFeedback = true;
  await page.getByRole('button', { name: 'Too high', exact: true }).click();
  await expect(page.getByText('Feedback did not save.', { exact: false })).toBeVisible();
  await expect(grade).toHaveAttribute('aria-pressed', 'true');
  api.feedback.DEMOA.engine_config_version = 'older-engine';
  await page.reload();
  await expect(page.getByText('Previous feedback belongs to another engine version.', { exact: false })).toBeVisible();
  await expect(read).toHaveAttribute('aria-pressed', 'false');
  await expect(grade).toBeDisabled();
});

test('watchlist saves carry the displayed scan identity and survive a reload', async ({ page, api }) => {
  await page.goto('/screener?t=DEMOA');
  const star = page.getByRole('dialog').getByRole('button', { name: 'Watchlist', exact: true });
  await star.click();
  await expect(star).toHaveAttribute('aria-pressed', 'true');
  await expect.poll(() => api.watches.length).toBe(1);
  expect(api.writes.at(-1)).toEqual({ path: '/watchlist/DEMOA', body: { universe: 'us_stocks', scan_date: '2026-10-22' } });
  await page.reload();
  await expect(star).toHaveAttribute('aria-pressed', 'true');
});

test('a failed initial scan request shows a clear error', async ({ page, api }) => {
  api.failScreener = true;
  await page.goto('/screener');
  await expect(page.getByText("Couldn't load this screener.", { exact: false })).toBeVisible();
  await expect(cards(page)).toHaveCount(0);
  api.failScreener = false;
  await page.getByRole('button', { name: 'Retry', exact: true }).click();
  await expect(cards(page)).toHaveCount(3);
});

test('liked setups are a reloadable shortlist with visible sorting and removable filters', async ({ page, api }) => {
  api.likes = ['DEMOB'];
  await page.goto('/screener');
  await page.getByRole('button', { name: 'Liked (1)', exact: true }).click();
  await expect(cards(page)).toHaveCount(1);
  await expect(cards(page)).toHaveAttribute('data-ticker', 'DEMOB');
  await page.getByLabel('Sort by:').selectOption('base');
  await page.reload();
  await expect(cards(page)).toHaveAttribute('data-ticker', 'DEMOB');
  await expect(page.getByLabel('Sort by:')).toHaveValue('base');
  await page.getByLabel('Search tickers').fill('NO_MATCH');
  await expect(page.getByText('No setups match the current filters.', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Remove Search: NO_MATCH filter', exact: true }).click();
  await expect(cards(page)).toHaveCount(1);
  await page.getByRole('button', { name: 'Clear filters', exact: true }).click();
  await expect(cards(page)).toHaveCount(3);
  await expect(page.getByLabel('Sort by:')).toHaveValue('score');
  await expect(page).toHaveURL(/\/screener$/);
  await cards(page).filter({ hasText: 'DEMOA' }).press('Enter');
  const heart = page.getByRole('dialog', { name: 'DEMOA chart lens' }).getByRole('button', { name: 'Like', exact: true });
  await heart.click();
  await expect(heart).toHaveAttribute('aria-pressed', 'true');
  await expect.poll(() => api.likes.includes('DEMOA')).toBe(true);
  await page.keyboard.press('Escape');
  await page.getByRole('button', { name: 'Liked (2)', exact: true }).click();
  await page.reload();
  await expect(cards(page)).toHaveCount(2);
});

test('a failed likes load offers retry instead of claiming that hearts are empty', async ({ page, api }) => {
  api.likes = ['DEMOB'];
  api.failLikesLoad = true;
  await page.goto('/screener?tier=LIKED');
  await expect(page.getByText("Couldn't load your liked setups.", { exact: false })).toBeVisible();
  await expect(page.getByText('No liked setups yet.', { exact: false })).toHaveCount(0);
  api.failLikesLoad = false;
  await page.getByRole('button', { name: 'Retry', exact: true }).click();
  await expect(cards(page)).toHaveAttribute('data-ticker', 'DEMOB');
});

test('cached charts remain visible under a failed refresh and the retry clears the warning', async ({ page, api }) => {
  await page.goto('/screener');
  await expect(cards(page)).toHaveCount(3);
  await page.getByRole('button', { name: 'Sectors + Market', exact: true }).click();
  await expect(page.getByText('This scan matched no setups.', { exact: true })).toBeVisible();
  api.failSummary = true;
  await page.getByRole('button', { name: 'US Stocks', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('Refresh failed. Showing the last loaded scan');
  await expect(cards(page)).toHaveCount(3);
  api.failSummary = false;
  await page.getByRole('button', { name: 'Retry refresh', exact: true }).click();
  await expect(page.getByRole('alert')).toHaveCount(0);
  await expect(cards(page)).toHaveCount(3);
});

test('failed saves restore the star and heart visibly, and rapid clicks issue one write', async ({ page, api }) => {
  api.failLikeSave = true;
  api.failWatchlist = true;
  let releaseLike, releaseWatch;
  api.likeGate = new Promise((resolve) => { releaseLike = resolve; });
  api.watchGate = new Promise((resolve) => { releaseWatch = resolve; });
  await page.goto('/screener?t=DEMOA');
  await expect(page.getByRole('button', { name: 'Liked (0)', exact: true })).toBeVisible();
  const lens = page.getByRole('dialog', { name: 'DEMOA chart lens' });
  const heart = lens.getByRole('button', { name: 'Like', exact: true });
  await heart.click();
  await heart.click();
  await expect.poll(() => api.writes.filter((write) => write.path.endsWith('/like')).length).toBe(1);
  releaseLike();
  await expect(heart).toHaveAttribute('aria-pressed', 'false');
  await expect(page.getByText('DEMOA: your like change did not save.', { exact: false })).toBeVisible();
  const star = lens.getByRole('button', { name: 'Watchlist', exact: true });
  await star.click();
  await star.click();
  await expect.poll(() => api.writes.filter((write) => write.path.endsWith('/DEMOA')).length).toBe(1);
  releaseWatch();
  await expect(star).toHaveAttribute('aria-pressed', 'false');
  await expect(page.getByText('DEMOA was not saved to the watchlist.', { exact: false })).toBeVisible();
});

test('top paging can reach the next scan results without scrolling through the chart wall', async ({ page, api }) => {
  const original = api.payload.chart_data.DEMOA;
  api.payload.ordered_tickers = Array.from({ length: 25 }, (_, index) => `DEMO${index}`);
  api.payload.chart_data = Object.fromEntries(api.payload.ordered_tickers.map((ticker) => [ticker, structuredClone(original)]));
  await page.goto('/screener');
  await expect(cards(page)).toHaveCount(24);
  await page.getByRole('group', { name: 'Setup pages (top)', exact: true })
    .getByRole('button', { name: 'Next page', exact: true }).click();
  await expect(cards(page)).toHaveCount(1);
  await expect(cards(page)).toHaveAttribute('data-ticker', 'DEMO24');
  await page.reload();
  await expect(cards(page)).toHaveAttribute('data-ticker', 'DEMO24');
});

test('narrow layouts keep navigation, actions and filter panels apart and within the viewport', async ({ page, api }) => {
  await page.setViewportSize({ width: 640, height: 900 });
  await page.goto('/screener');
  await expect(cards(page)).toHaveCount(3);
  const nav = await page.getByRole('navigation', { name: 'Primary', exact: true }).boundingBox();
  const actions = await page.locator('.topnav-right').boundingBox();
  expect(nav.y + nav.height).toBeLessThanOrEqual(actions.y);
  const connect = await page.getByRole('button', { name: /CONNECT IBKR/i }).boundingBox();
  expect(connect.x).toBeGreaterThanOrEqual(0);
  expect(connect.x + connect.width).toBeLessThanOrEqual(640);
  await page.getByRole('button', { name: /▸ Filters/ }).click();
  const filters = page.getByRole('dialog', { name: 'Setup, sort and tag filters' });
  await expect(filters).toBeVisible();
  const panel = await filters.boundingBox();
  expect(panel.x).toBeGreaterThanOrEqual(0);
  expect(panel.x + panel.width).toBeLessThanOrEqual(640);
  expect(api.writes).toEqual([]);
});
