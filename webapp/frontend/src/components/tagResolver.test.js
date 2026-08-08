// The one-resolver contract (TA-grade build task 11): dual-epoch by ONE
// explicit switch; verdicts projected, never re-derived; unknown ids visible.
import test from 'node:test';
import assert from 'node:assert/strict';
import { hasResolvedTags, resolveTags } from './tagResolver.js';
import { TAG_CATALOG } from './setupTagsData.js';

test('absent fired_tags routes to the legacy derive path (the EC-8 rollback)', () => {
  // No fired_tags key = pre-v2 / flag-off payload: the frozen legacy rules
  // still decide (tight_lps fires at 1.00 x its JS cap of 20).
  const legacyRow = { sub_scores: { lps_tightness: 20 } };
  assert.equal(hasResolvedTags(legacyRow), false);
  const tags = resolveTags(legacyRow);
  assert.ok(tags.some(t => t.id === 'tight_lps'));
});

test('empty fired_tags is resolved-nothing-fired — never re-derived', () => {
  // The key PRESENT as [] means the backend resolved this row and nothing
  // fired. The legacy rules would fire tight_lps here — they must not run.
  const row = { fired_tags: [], sub_scores: { lps_tightness: 20 } };
  assert.equal(hasResolvedTags(row), true);
  assert.deepEqual(resolveTags(row), []);
});

test('v2 entries project label/group from the catalog, verdicts untouched', () => {
  const row = {
    fired_tags: [
      { id: 'tight_lps', detail: { foo: 1 } },
      { id: 'phase_d', detail: {} },
    ],
    // Bait: these sub_scores would fire other chips under the legacy rules —
    // the resolver must render exactly the two backend verdicts.
    sub_scores: { vol_contraction: 20, box_tightness: 22 },
  };
  const tags = resolveTags(row);
  assert.deepEqual(tags.map(t => t.id).sort(), ['phase_d', 'tight_lps']);
  // Presentational ordering: the catalog's group order (consolidation first).
  assert.equal(tags[0].id, 'phase_d');
  const def = TAG_CATALOG.find(d => d.id === 'tight_lps');
  const chip = tags.find(t => t.id === 'tight_lps');
  assert.equal(chip.label, def.label);
  assert.equal(chip.group, def.group);
  assert.deepEqual(chip.detail, { foo: 1 });
});

test('unknown registry ids render VISIBLY, never vanish', () => {
  // The puzzle_quality lesson: a backend id without a signed label renders
  // as its raw slug with a real group (so the chip tones resolve).
  const tags = resolveTags({ fired_tags: [{ id: 'brand_new_signal' }] });
  assert.equal(tags.length, 1);
  assert.equal(tags[0].label, 'brand_new_signal');
  assert.ok(tags[0].group);
});

test('missing payload resolves to the empty list', () => {
  assert.deepEqual(resolveTags(null), []);
  assert.deepEqual(resolveTags(undefined), []);
});
