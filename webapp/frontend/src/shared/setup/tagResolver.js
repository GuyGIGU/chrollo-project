// THE one wire → render-ready tag resolver (TA-grade build task 11; legacy
// derive path retired at the 2026-08-22 consolidation).
//
// A payload's `fired_tags` entries are VERDICTS and this module only projects
// presentation onto them (label/group from the catalog; an unknown id renders
// VISIBLY as its raw slug — the setup_quality lesson, never a silent drop).
// A payload WITHOUT the key never grew chips here since the retirement: the
// legacy client-side derive path (deriveTags over sub_scores) is deleted, so
// pre-flip archive rows and stale pre-flip payloads render chipless — an
// honest absence, not a re-derived guess. (Its cap-mirror bug fired the two
// demoted trend chips on every legacy-epoch row; council 2026-08-22 P1.)
//
// No cap, threshold, or firing rule lives here (EC-28: the wire carries
// verdicts, never rules). [] renders as "resolved, nothing fired".
// ScreenerCard's TagRow, the filter bar's tag map, and the lens all consume
// THIS function — one derivation, so the grid and the filters cannot disagree.
// Explicit .js extensions: this module runs under node --test as well as
// Vite (the wireVocabulary/narrativeRead node-suite convention).
import { TAG_CATALOG } from './tagCatalog.js';
import { tooltipForTag } from './tagTooltips.js';

const CATALOG_BY_ID = new Map(TAG_CATALOG.map(def => [def.id, def]));
const ORDER_BY_ID = new Map(TAG_CATALOG.map((def, index) => [def.id, index]));

export function hasResolvedTags(data) {
  return Array.isArray(data?.fired_tags);
}

export function resolveTags(data) {
  if (!data || !hasResolvedTags(data)) return [];
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
      // Presentation only: label/group from the catalog; the rich explainTip
      // copy comes from tagTooltips, with the fired entry's detail facts
      // folded into the dynamic tags' suffixes. Which chips FIRE was decided
      // engine-side.
      return {
        id: def.id,
        label: def.label,
        group: def.group,
        title: tooltipForTag(def.id, entry.detail) ?? def.label,
        detail: entry.detail || {},
      };
    })
    // Presentational ordering: the catalog's order (unknown ids sink to the
    // end, still visible). The card's overflow chip bounds count.
    .sort((a, b) => (ORDER_BY_ID.get(a.id) ?? 999) - (ORDER_BY_ID.get(b.id) ?? 999));
}
