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
  readCaveats,
} from './narrativeRead.js';
import { CHAPTER_LABELS, CHAPTER_ORDER, WARNING_LABELS } from './wireVocabulary.js';

// The chapters whose terms read the Event-Map story — their honesty subtext
// keys off the narrative family's own three-state read.
const STORY_CHAPTERS = new Set(['phase_b', 'phase_d']);

// Chapter → chart-region hover target (the lens's activeRegion channel).
// IDENTITY since the fold (2026-08-12): each chapter lights its OWN phase.
// The old routing sent phase_c to Phase D and phase_d to the LPS — defensible
// when the strip stood alone (it pointed each chapter at where its terms live,
// and nothing else claimed the LPS), but the fused panel now shows each phase's
// SPAN and its grade on one row, so a row labelled Phase C that lights Phase D
// contradicts its own words. The LPS has its own row now (see setupStoryRows).
export const CHAPTER_REGION = {
  cause: 'b',
  phase_b: 'b',
  phase_c: 'c',
  phase_d: 'd',
  trend: null,
};

export function chapterCells(data) {
  if (data?.ta_grade == null) return [];
  // The WIRE's chapters drive the cells (2026-08-08 review, finding 12):
  // the backend pins their emission order to taxonomy.CHAPTER_ORDER, the
  // local maps supply labels only (unknown wire chapters fall through
  // verbatim — visible, never dropped), and a payload WITHOUT a chapters
  // dict yields NO strip — the old CHAPTER_ORDER-mirror iteration rendered
  // a grade-carrying, chapters-less payload (SetupOut's exact shape) as
  // five confident "0.0" cells: absence dressed as measured zero.
  const points = data.ta_grade_chapters;
  if (!points || typeof points !== 'object') return [];
  const fractions = data.ta_grade_chapter_fractions || {};
  const status = narrativeStatus(data);
  // Both read-honesty caveats (unreadable bars + starved geometry), composed
  // once in narrativeRead — the story chapters' subtext says exactly what
  // the Engine's Read panel says.
  const caveat = readCaveats(data);
  return Object.keys(points).map((key) => {
    const value = Number(points[key]);
    const cell = {
      key,
      label: CHAPTER_LABELS[key]?.label ?? key,
      short: CHAPTER_LABELS[key]?.short ?? key,
      // null (rendered as a dash), never a fabricated 0.0.
      points: Number.isFinite(value) ? value : null,
      fraction: Math.max(0, Math.min(1, Number(fractions[key]) || 0)),
      subtext: null,
    };
    // NOT_CARRIED renders NO subtext — narrativeRead's own law (the
    // council-F4 ruling): a wire that doesn't carry the family cannot say
    // anything honest, and "predates the event-map read" is exactly the
    // falsifiable diagnosis that state must never wear.
    if (STORY_CHAPTERS.has(key) && status !== NARRATIVE_STATUS.NOT_CARRIED) {
      if (status === NARRATIVE_STATUS.NOT_MEASURED) {
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
