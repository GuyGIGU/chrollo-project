// THE one wire → render-ready tag resolver (TA-grade build task 11).
//
// Dual-epoch by ONE explicit switch (EC-8's rollback mechanism): a payload
// whose `fired_tags` key is PRESENT — even as [] — was resolved by the
// backend; the entries are VERDICTS and this module only projects
// presentation onto them (label/group from the frozen catalog; an unknown
// id renders VISIBLY as its raw slug — the puzzle_quality lesson, never a
// silent drop). A payload WITHOUT the key (flag-off scan, pre-v2 archive
// row) routes to the legacy derive path unchanged, so a flag rollback
// restores legacy chips with no frontend redeploy.
//
// No cap, threshold, or firing rule lives here (EC-28: the wire carries
// verdicts, never rules). [] renders as "resolved, nothing fired" — it is
// NEVER re-derived through the legacy rules. ScreenerCard's TagRow, the
// filter bar's tag map, and the lens all consume THIS function — one
// derivation, so the grid and the filters cannot disagree.
// Explicit .js extensions: this module runs under node --test as well as
// Vite (the wireVocabulary/narrativeRead node-suite convention).
import { deriveTags, TAG_CATALOG } from './setupTagsData.js';
import { tagFlagsFromWire } from './wireVocabulary.js';

const CATALOG_BY_ID = new Map(TAG_CATALOG.map(def => [def.id, def]));
const ORDER_BY_ID = new Map(TAG_CATALOG.map((def, index) => [def.id, index]));

export function hasResolvedTags(data) {
  return Array.isArray(data?.fired_tags);
}

export function resolveTags(data) {
  if (!data) return [];
  if (!hasResolvedTags(data)) {
    // Legacy epoch: the frozen derive path, verbatim (its stale caps are
    // deliberately untouched until the whole file's deletion — task 15).
    return deriveTags(data.sub_scores, tagFlagsFromWire(data));
  }
  return data.fired_tags
    .map(entry => {
      const def = CATALOG_BY_ID.get(entry.id);
      if (!def) {
        return {
          id: entry.id,
          label: entry.id,
          group: 'consolidation',
          title: 'New engine tag — signed label pending',
          detail: entry.detail || {},
        };
      }
      // Presentation only: label/group from the frozen catalog; the rich
      // explainTip copy migrates to the surviving catalog with the lens
      // rebuild (task 12). Which chips FIRE was decided engine-side.
      return {
        id: def.id,
        label: def.label,
        group: def.group,
        title: def.label,
        detail: entry.detail || {},
      };
    })
    // Presentational ordering: the catalog's group→weight order (unknown ids
    // sink to the end, still visible). The card's overflow chip bounds count.
    .sort((a, b) => (ORDER_BY_ID.get(a.id) ?? 999) - (ORDER_BY_ID.get(b.id) ?? 999));
}
