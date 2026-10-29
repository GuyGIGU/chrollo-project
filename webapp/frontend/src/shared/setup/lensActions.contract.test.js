// Operator 2026-10-03, suggestion #1, "act from the big chart": the lens's top
// bar carries the card's star and heart, ↗ TV and a "12 / 37" counter. A source
// contract, like screenerModalPager.test.js: there is no DOM harness.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const srcDir = join(dirname(fileURLToPath(import.meta.url)), '..', '..');
const read = (rel) => readFileSync(join(srcDir, rel), 'utf8');
const TOOLBAR = 'shared/setup/ScreenerModalToolbar.jsx';
const GRID = 'features/screener/components/ScreenerGrid.jsx';

// The `{guard && ( ... )}` block holding `marker`, or null when it is not so guarded.
const guardedBlock = (src, guard, marker) => {
  const re = new RegExp(`\\{${guard} && \\(\\s*<(button|span)\\b[\\s\\S]*?<\\/\\1>\\s*\\)\\}`, 'g');
  return [...src.matchAll(re)].map((m) => m[0]).find((block) => block.includes(marker)) ?? null;
};

test('the star is drawn only when the host hands in a watchlist handler', () => {
  const src = read(TOOLBAR);
  const block = guardedBlock(src, 'onToggleWatchlist', '★');
  assert.ok(block, 'no {onToggleWatchlist && (<button>)} block holds the star');
  assert.match(block, /onClick=\{\(\) => onToggleWatchlist\(ticker\)\}/);
  assert.match(block, /aria-pressed=\{Boolean\(watchlisted\)\}/);
  assert.match(block, /'☆'/);
  const rest = src.replace(block, '');
  assert.doesNotMatch(rest, /[☆★]/, 'a star drawn outside its guard');
});

test('the heart is drawn only when the host hands in a like handler', () => {
  const src = read(TOOLBAR);
  const block = guardedBlock(src, 'onToggleLike', '♥');
  assert.ok(block, 'no {onToggleLike && (<button>)} block holds the heart');
  assert.match(block, /onClick=\{\(\) => onToggleLike\(ticker\)\}/);
  assert.match(block, /aria-pressed=\{Boolean\(liked\)\}/);
  assert.match(block, /'♡'/);
  const rest = src.replace(block, '');
  assert.doesNotMatch(rest, /[♡♥]/, 'a heart drawn outside its guard');
});

test('the counter is drawn only with a position; ↗ TV in every lens; the order is his', () => {
  const src = read(TOOLBAR);
  const counter = guardedBlock(src, 'position', 'lens-position');
  assert.ok(counter, 'no {position && (<span>)} block holds the counter');
  assert.match(counter, /\{position\.n \?\? '–'\} \/ \{position\.total\}/, 'a dropped-out chart keeps the slot as "– / 36"');
  assert.doesNotMatch(src.replace(counter, ''), /lens-position|position\.n/, 'a counter drawn outside its guard');
  // ↗ TV straight after the heart's block: no guard of its own.
  const heart = guardedBlock(src, 'onToggleLike', '♥');
  assert.match(src, new RegExp(`${heart.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\s*<a\\b[^>]*href=\\{tradingViewUrl\\(ticker\\)\\}`));
  // Finviz's quote page (Thu 29/10/2026): the pager in the slim bar over the page, the card's acts at the
  // end of the quote's tab row.
  const inOrder = (part, markers, label) => {
    const order = markers.map((m) => part.indexOf(m));
    assert.ok(order.every((at) => at >= 0), `${label}: ${order.join(',')}`);
    assert.deepEqual([...order].sort((a, b) => a - b), order, label);
  };
  const bar = src.slice(src.indexOf('export function LensNavBar'), src.indexOf('export function LensQuote'));
  const quote = src.slice(src.indexOf('export function LensQuote'), src.indexOf('export function LensChartToolbar'));
  inOrder(bar, ['lens-position', '>Prev<', '>Next<', 'aria-label="Close"'], 'the bar: counter, Prev, Next, close');
  inOrder(quote, ["'★'", "'♥'", '↗ TV'], 'the quote: star, heart, TV');
});

test('W and L act only where their button is drawn; T opens TradingView in a new tab', () => {
  const src = read(TOOLBAR);
  assert.match(src, /useLensActionKeys\(ticker, onToggleWatchlist, onToggleLike, onToggleFix\);/);
  assert.match(src, /action === 'fixbox' && onToggleFix\) onToggleFix\(\);/, 'B arms "fix the box" only where the host hands in the toggle');
  assert.match(src, /action === 'watch' && onToggleWatchlist\) onToggleWatchlist\(ticker\);/);
  assert.match(src, /action === 'like' && onToggleLike\) onToggleLike\(ticker\);/);
  assert.match(src, /action === 'tradingview'\) window\.open\(tradingViewUrl\(ticker\), '_blank', 'noopener,noreferrer'\);/);
  assert.match(src, /else return;\s*event\.preventDefault\(\);/);
  // The listener is installed, and re-bound to the chart on screen: with stale
  // deps, W and L after Next would act on the FIRST chart opened.
  const start = src.indexOf('function useLensActionKeys');
  const end = src.indexOf('export function LensNavBar', start);
  assert.ok(start >= 0 && end > start, 'the useLensActionKeys hook is gone');
  const hook = src.slice(start, end);
  assert.match(hook, /window\.addEventListener\('keydown', onKey\);/);
  assert.match(hook, /\}, \[ticker, onToggleWatchlist, onToggleLike, onToggleFix\]\);/);
});

test('the screener grid hands the lens the star (drill-down aware), the heart and the counter', () => {
  const grid = read(GRID);
  const mount = grid.slice(grid.indexOf('<ScreenerModal'), grid.indexOf('/>', grid.indexOf('<ScreenerModal')));
  assert.match(mount, /\bwatchlisted=\{watchlist\.has\(activeModalTicker\)\}/);
  assert.match(mount, /\bonToggleWatchlist=\{drilldown \? handleToggleWatchlistDrilldown : handleToggleWatchlist\}/);
  assert.match(mount, /\bliked=\{liked\.has\(activeModalTicker\)\}/);
  assert.match(mount, /\bonToggleLike=\{toggleLiked\}/);
  assert.match(mount, /\bposition=\{lensPosition\(modalTickers, activeModalTicker\)\}/);
  // Prev/Next step through the model from the last place the chart HAD in the
  // list (kept only while it is in it), so a chart that dropped out still lands.
  assert.match(grid, /const index = modalTickers\.indexOf\(activeModalTicker\);\s*if \(index >= 0\) lensIndexRef\.current = index;/);
  assert.match(grid, /stepTicker\(modalTickers, activeModalTicker, lensIndexRef\.current, delta\)/);
});

test('the lens hands all five through: the acts to the quote, the counter and the keys to the bar', () => {
  const lens = read('shared/setup/ScreenerModal.jsx');
  const mountOf = (tag) => {
    const at = lens.indexOf(`<${tag}`);
    assert.ok(at >= 0, `${tag} is not mounted`);
    return lens.slice(at, lens.indexOf('/>', at));
  };
  const quote = mountOf('LensQuote');
  for (const prop of ['watchlisted', 'onToggleWatchlist', 'liked', 'onToggleLike']) {
    assert.match(quote, new RegExp(`\\b${prop}=\\{${prop}\\}`), `the quote's ${prop}`);
  }
  const bar = mountOf('LensNavBar');
  for (const prop of ['position', 'onToggleWatchlist', 'onToggleLike', 'onToggleFix']) {
    assert.match(bar, new RegExp(`\\b${prop}=\\{${prop}\\}`), `the bar's ${prop} (its keys act only where the button is drawn)`);
  }
});

test('every other lens host gets ↗ TV alone, and no lens carries a second TradingView link', () => {
  const hosts = readdirSync(srcDir, { recursive: true })
    .map((f) => f.split('\\').join('/'))
    .filter((f) => f.endsWith('.jsx') && /<ScreenerModal\s/.test(read(f)));   // not the lens's own <ScreenerModalToolbar
  // Vacuity: the walk must reach the mounts this rule is about.
  for (const f of [GRID, 'features/home/components/ActionCenter.jsx', 'features/home/components/WatchlistZone.jsx']) {
    assert.ok(hosts.includes(f), hosts.join(', '));
  }
  for (const f of hosts) {
    const src = read(f);
    assert.doesNotMatch(src, /footer=\{<BridgeOut\b/, f);
    if (f === GRID) continue;
    assert.doesNotMatch(src, /\b(?:onToggleWatchlist|onToggleLike|position)=\{/, `${f} hands the lens a Screener-only control`);
  }
  const zone = read('features/home/components/WatchlistZone.jsx');
  assert.doesNotMatch(zone.slice(zone.indexOf('function ReplayFooter')), /<BridgeOut\b/, "the replay lens's footer");
});

test("a card stands down under the big chart, for a command modifier and for a held key before it acts", () => {
  const card = read('shared/setup/ScreenerCard.jsx');
  const handler = card.slice(card.indexOf('onKeyDown={(event) => {'), card.indexOf('style={{', card.indexOf('onKeyDown={(event) => {')));
  const guard = handler.indexOf('if (hasCommandModifier(event) || dialogOpenOutside(event.currentTarget)) return;');
  assert.ok(guard > 0, 'the stand-down guard is missing');
  // A held W/L must not flicker the star or heart, one write per repeat (the lens's lensKeyAction rule).
  const repeat = handler.indexOf('if (event.repeat) return;');
  assert.ok(repeat > 0, 'the held-key guard is missing');
  for (const act of ['onClick(ticker)', 'onToggleWatchlist(ticker)', 'onToggleLike(ticker)']) {
    const at = handler.indexOf(act);
    assert.ok(at > guard, `${act} runs before the stand-down`);
    assert.ok(at > repeat, `${act} runs before the held-key guard`);
  }
});
