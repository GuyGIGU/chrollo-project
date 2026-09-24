// The one-resolver contract (TA-grade build task 11; legacy derive path
// retired at the 2026-08-22 consolidation): verdicts projected, never
// derived client-side; unresolved payloads render chipless; unknown ids
// stay visible.
import test from 'node:test';
import assert from 'node:assert/strict';
import { hasResolvedTags, resolveTags } from './tagResolver.js';
import { TAG_CATALOG } from './tagCatalog.js';

test('absent fired_tags renders NO chips — the legacy derive path is retired', () => {
  // A pre-flip payload (no fired_tags key) must not grow client-derived
  // chips: the retired derive path's cap-mirror bug fired the two demoted
  // trend chips on every such row (council 2026-08-22 P1). Chipless is the
  // honest read of an unresolved payload.
  const legacyRow = { sub_scores: { lps_tightness: 20, rs_bonus: 0, uptrend_bonus: 0 } };
  assert.equal(hasResolvedTags(legacyRow), false);
  assert.deepEqual(resolveTags(legacyRow), []);
});

test('empty fired_tags is resolved-nothing-fired', () => {
  const row = { fired_tags: [], sub_scores: { lps_tightness: 20 } };
  assert.equal(hasResolvedTags(row), true);
  assert.deepEqual(resolveTags(row), []);
});

test('the demoted trend chips are out of the catalog — they can never fire', () => {
  // rs/uptrend are weight-0 (decisions.md 2026-07-25) and the engine's cap>0
  // rule keeps them dead; the catalog lists no dead filter entries. If the
  // engine ever re-emits them, the raw-slug fallback keeps them VISIBLE.
  assert.equal(TAG_CATALOG.some(d => d.id === 'strong_rs'), false);
  assert.equal(TAG_CATALOG.some(d => d.id === 'uptrend'), false);
  const tags = resolveTags({ fired_tags: [{ id: 'strong_rs' }] });
  assert.equal(tags.length, 1);
  assert.equal(tags[0].label, 'strong_rs');
});

test('v2 entries project label/group from the catalog, verdicts untouched', () => {
  const row = {
    fired_tags: [
      { id: 'tight_lps', detail: { foo: 1 } },
      { id: 'phase_d', detail: {} },
    ],
    // Bait: sub_scores must be inert — which chips fired was decided
    // engine-side and only the two verdicts may render.
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
  // The setup_quality lesson: a backend id without a signed label renders
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
