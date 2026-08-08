// Chapter-strip presentation logic (TA-grade build task 12) — pure and
// node-tested; the JSX in TaGradePanel stays a thin projection.
//
// Reads only RESOLVED wire values (EC-28): chapter points, earned fractions,
// and warning factors all arrive computed engine-side — no cap, divisor, or
// threshold is re-derived here. The three-state honesty grammar is
// narrativeRead's (not-measured / measured-zero with its readability
// caveat / graded) — the same words the Engine's Read tape uses.
import {
  ABSENCE_COPY,
  NARRATIVE_STATUS,
  narrativeStatus,
  readabilityCaveat,
} from './narrativeRead.js';
import { CHAPTER_LABELS, CHAPTER_ORDER, WARNING_LABELS } from './wireVocabulary.js';

// The chapters whose terms read the Event-Map story — their honesty subtext
// keys off the narrative family's own three-state read.
const STORY_CHAPTERS = new Set(['work', 'finish']);

// Chapter → chart-region hover target (the lens's activeRegion channel):
// cause/work light the base, turn lights Phase D, finish lights the LPS.
export const CHAPTER_REGION = {
  cause: 'b',
  work: 'b',
  turn: 'd',
  finish: 'lps',
  trend_context: null,
};

export function chapterCells(data) {
  if (data?.ta_grade == null) return [];
  const points = data.ta_grade_chapters || {};
  const fractions = data.ta_grade_chapter_fractions || {};
  const status = narrativeStatus(data);
  const caveat = readabilityCaveat(data);
  return CHAPTER_ORDER.map((key) => {
    const cell = {
      key,
      label: CHAPTER_LABELS[key]?.label ?? key,
      short: CHAPTER_LABELS[key]?.short ?? key,
      points: Number(points[key]) || 0,
      fraction: Math.max(0, Math.min(1, Number(fractions[key]) || 0)),
      subtext: null,
    };
    if (STORY_CHAPTERS.has(key)) {
      if (status === NARRATIVE_STATUS.NOT_MEASURED
          || status === NARRATIVE_STATUS.NOT_CARRIED) {
        cell.subtext = ABSENCE_COPY.not_measured;
      } else if (status === NARRATIVE_STATUS.EMPTY) {
        cell.subtext = caveat
          ? `${ABSENCE_COPY.empty} · ${caveat}` : ABSENCE_COPY.empty;
      } else if (caveat) {
        cell.subtext = caveat;
      }
    }
    return cell;
  });
}

export function warningItems(data) {
  const warnings = data?.ta_grade_warnings || {};
  return Object.entries(warnings).map(([id, factor]) => {
    const f = Number(factor);
    return {
      id,
      label: WARNING_LABELS[id] ?? id,
      // A registered-but-neutral warning (factor 1.0, pre-A/B) shows with no
      // cost yet — visible, never silently absent.
      cost: Number.isFinite(f) && f < 1
        ? `−${Math.round((1 - f) * 100)}%` : null,
    };
  });
}
