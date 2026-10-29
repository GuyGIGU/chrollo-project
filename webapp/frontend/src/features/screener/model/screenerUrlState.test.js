// Operator 2026-10-03, "never lose your place": the screener's filters and page
// round-trip through the address bar.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { TIER_LETTERS } from '../../../shared/presentation/wireVocabulary.js';
import {
  PUSHED_BY_DRILLDOWN,
  PUSHED_BY_LENS,
  SORT_KEYS,
  TIER_FILTERS,
  applyParamPatch,
  closesByPop,
  dropUnshownFilters,
  filterChange,
  filterParamPatch,
  pageForIndex,
  pushedEntry,
  readFilterParams,
} from './screenerUrlState.js';

test('an empty address is the default view', () => {
  assert.deepEqual(readFilterParams(new URLSearchParams('')), {
    tierFilter: 'ALL', setupFilter: 'ALL', tagIds: [], sortBy: 'score', searchTerm: '', page: 1,
  });
});

test('every filter reads back from the address', () => {
  const params = new URLSearchParams('tier=A&setup=VCP&tag=tight_box&tag=vcp_coil&sort=rs&q=nv&p=3');
  assert.deepEqual(readFilterParams(params), {
    tierFilter: 'A', setupFilter: 'VCP', tagIds: ['tight_box', 'vcp_coil'], sortBy: 'rs', searchTerm: 'nv', page: 3,
  });
  for (const search of ['p=0', 'p=-2', 'p=abc', 'p=']) {
    assert.equal(readFilterParams(new URLSearchParams(search)).page, 1, search);
  }
});

// A hand-typed ?tier=a matched nothing and faked 'No setups match' with no pill pressed;
// ?sort=valueOf (or __proto__, hasOwnProperty) handed Array.sort an Object.prototype member.
test('a tier or sort the command band does not offer reads as the default', () => {
  for (const search of ['tier=WATCHLIST', 'tier=a', 'tier=Z', 'tier=valueOf', 'tier=__proto__']) {
    assert.equal(readFilterParams(new URLSearchParams(search)).tierFilter, 'ALL', search);
  }
  for (const search of ['sort=valueOf', 'sort=__proto__', 'sort=hasOwnProperty', 'sort=RS']) {
    assert.equal(readFilterParams(new URLSearchParams(search)).sortBy, 'score', search);
  }
  for (const tier of TIER_FILTERS) assert.equal(readFilterParams(new URLSearchParams({ tier })).tierFilter, tier);
  for (const sort of SORT_KEYS) assert.equal(readFilterParams(new URLSearchParams({ sort })).sortBy, sort);
});

// The band shares the URL's choices; a new view cannot vanish on reload.
test("the reader's tiers and sorts are the command band's", () => {
  const srcDir = join(dirname(fileURLToPath(import.meta.url)), '..', '..', '..');
  const band = readFileSync(join(srcDir, 'features/screener/components/ScreenerToolbar.jsx'), 'utf8');
  assert.match(band, /TIER_FILTERS\.map\(/);
  assert.deepEqual(TIER_FILTERS, ['ALL', ...TIER_LETTERS, 'LIKED']);
  const sortRow = band.slice(band.indexOf('label="Sort by:"'));
  const options = sortRow.slice(0, sortRow.indexOf(']}'));
  assert.deepEqual([...options.matchAll(/^\s*\['(\w+)', '/gm)].map((m) => m[1]), SORT_KEYS);
});

test('patches keep unrelated params and delete defaults', () => {
  assert.equal(applyParamPatch('?u=etf&t=NVDA', { tier: 'A' }).toString(), 'u=etf&t=NVDA&tier=A');
  assert.equal(applyParamPatch('?tier=A&q=nv', { tier: null, q: '' }).toString(), '');
  assert.equal(applyParamPatch('?tag=a&tag=b&u=x', { tag: ['c'] }).toString(), 'u=x&tag=c');
  assert.equal(applyParamPatch('?tag=a&tag=b', { tag: [] }).toString(), '');
  assert.deepEqual(filterChange({ tierFilter: 'A' }), { tier: 'A', p: null });
  assert.deepEqual(
    filterParamPatch({ tierFilter: 'ALL', sortBy: 'score', searchTerm: '', page: 1, setupFilter: 'ALL' }),
    { tier: null, sort: null, q: null, p: null, setup: null },
  );
  assert.deepEqual(filterParamPatch({ tagIds: new Set(['vcp_coil', 'tight_box']) }), { tag: ['tight_box', 'vcp_coil'] });
});

test('what is written reads back identically', () => {
  const view = {
    tierFilter: 'LIKED', setupFilter: 'VCP', tagIds: ['a_tag', 'b_tag'], sortBy: 'trigger', searchTerm: 'brk.b', page: 4,
  };
  assert.deepEqual(readFilterParams(applyParamPatch('?u=etf', filterParamPatch(view))), view);
});

test("a ticker's page", () => {
  assert.equal(pageForIndex(0, 24), 1);
  assert.equal(pageForIndex(23, 24), 1);
  assert.equal(pageForIndex(24, 24), 2);
  assert.equal(pageForIndex(-1, 24), null);
});

test('a filter the controls cannot show is ignored', () => {
  const gone = dropUnshownFilters({ setupFilter: 'GONE', tagIds: ['tight_box', 'gone_tag'] }, ['VCP'], new Set(['tight_box']));
  assert.equal(gone.setupFilter, 'ALL');
  assert.deepEqual([...gone.tagFilter], ['tight_box']);
  const kept = dropUnshownFilters({ setupFilter: 'VCP', tagIds: [] }, ['VCP'], new Set(['tight_box']));
  assert.equal(kept.setupFilter, 'VCP');
});

test('closing pops only the entry its own open pushed', () => {
  assert.equal(closesByPop(pushedEntry(PUSHED_BY_LENS), PUSHED_BY_LENS), true);
  assert.equal(closesByPop(pushedEntry(PUSHED_BY_DRILLDOWN), PUSHED_BY_DRILLDOWN), true);
  // The drill-down's Back must not pop the lens entry above it, nor the lens the drill-down's.
  assert.equal(closesByPop(pushedEntry(PUSHED_BY_LENS), PUSHED_BY_DRILLDOWN), false);
  assert.equal(closesByPop(pushedEntry(PUSHED_BY_DRILLDOWN), PUSHED_BY_LENS), false);
  // A deep link, a reload of a copied URL or another page's link carries no tag.
  assert.equal(closesByPop(null, PUSHED_BY_LENS), false);
  assert.equal(closesByPop(undefined, PUSHED_BY_LENS), false);
  assert.equal(closesByPop({}, PUSHED_BY_LENS), false);
});
