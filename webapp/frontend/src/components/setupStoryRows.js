// The fused setup story — ONE ordered list where every phase of the chart
// carries both its measured SPAN and its GRADE.
//
// Operator ruling 2026-08-12: "Why It Stands Out" and "Technical Structure
// Analysis" were the same panel written twice. Both listed Phase B/C/D — one as
// spans (hover to light the chart), the other as graded chapters — and neither
// was whole: the spans had no grades, and the grade strip had no LPS, the one
// phase read last and hardest. Fused, the list reads left→right like the chart:
// the lead-in, the cause, what happened inside, the shakeout, the right side,
// the last support test, and the trend around it all.
//
// Pure and node-tested; the JSX stays a thin projection (chapterStrip's
// precedent). Reads only RESOLVED wire values (EC-28) — chapter points and
// earned fractions arrive computed engine-side, spans arrive from the same
// buildPhaseRegions the chart overlay draws. The ONE arithmetic here is the LPS
// grade (see lpsGrade), which divides by the cap mirror setupScoreMath.js has
// always owned.
import { CHAPTER_REGION, chapterCells } from './chapterStrip.js';
import { SUB_SCORE_CAPS } from './setupScoreMath.js';
import { PHASE_NAMES } from './wireVocabulary.js';

// What each chapter grades, in the words taxonomy.py's chapter block uses. A
// chapter with a phase span of its own prefers the SPAN's detail (it is the
// measured one — "Undercut and recovery" for a real spring, the resolved
// Phase-D evidence source); these are the fallback, and the only text the two
// span-less chapters ever show.
const CHAPTER_DETAIL = {
  cause: 'The base itself — proper, tight, mature',
  phase_b: 'Two-sided range work',
  phase_c: 'Support shakeout or test',
  phase_d: 'Right-side tightening range',
  trend: 'The chart around the base — trend, RS, 52-week, ADR',
};

// The LPS's own grade: the engine's lps_tightness term as a fraction of its cap.
//
// It is deliberately NOT a sixth chapter, and its row deliberately shows a
// PERCENTAGE rather than points of the grade's 100 — because those points are
// already counted inside Phase D. Printing them again in the same column would
// make the column stop summing to the grade, which is exactly the kind of quiet
// double-count this panel exists to prevent.
//
// Three-state: null when the term was never measured (an archive row without
// sub-scores), a real 0 when the last support test was measured and graded
// loose. Number(null) === 0 is finite, so absence is rejected BEFORE the finite
// check — the same guard setupScoreMath's isMeasured has always used.
export function lpsGrade(data) {
  const earned = data?.sub_scores?.lps_tightness;
  if (earned == null) return null;
  const value = Number(earned);
  const cap = Number(SUB_SCORE_CAPS.lps_tightness);
  if (!Number.isFinite(value) || !(cap > 0)) return null;
  const fraction = Math.max(0, Math.min(1, value / cap));
  return { fraction, percent: Math.round(fraction * 100) };
}

const spanRow = (region, extra = {}) => ({
  key: region.key,
  token: region.label,
  name: region.name,
  detail: region.detail,
  region: region.key,
  color: region.color ?? null,
  points: null,
  fraction: null,
  percent: null,
  subtext: null,
  nested: false,
  ...extra,
});

// The three chapters that ARE a phase, and so speak that phase's measured
// words. `cause` is not among them: it lights the base (CHAPTER_REGION) but
// grades a different question than Phase B does, so borrowing Phase B's detail
// would print the same sentence twice under two different names.
const CHAPTER_OWN_SPAN = { phase_b: 'b', phase_c: 'c', phase_d: 'd' };

const chapterRow = (cell, span, region) => ({
  key: cell.key,
  token: cell.short,
  // A chapter that owns a phase wears the PHASE's name (the same words by
  // construction — CHAPTER_LABELS.phase_b.label === PHASE_NAMES.b); an unknown
  // wire chapter falls through with its own label, never dropped.
  name: cell.label,
  detail: span?.detail ?? CHAPTER_DETAIL[cell.key] ?? '',
  region: region ? region.key : null,
  color: region?.color ?? null,
  points: cell.points,
  fraction: cell.fraction,
  percent: null,
  subtext: cell.subtext,
  nested: false,
});

// The rows, in chart order. `regions` is buildPhaseRegions' output (empty on a
// higher-timeframe pane, where the daily phases mean nothing) — with none, the
// chapters still grade, they simply light nothing.
export function storyRows(data, regions = []) {
  const cells = chapterCells(data);
  const find = (key) => regions.find((region) => region.key === key) || null;
  const rows = [];

  // Phase A leads: the climax→AR that ended the trend, before the box. It is a
  // span with no chapter of its own — shown ungraded rather than hidden, because
  // it is a chart-highlight target the operator reads.
  const phaseA = find('a');
  if (phaseA) rows.push(spanRow(phaseA));

  // The WIRE's chapters drive the middle (chapterStrip's law): the backend pins
  // their order, and an unknown chapter renders verbatim instead of vanishing.
  const lps = find('lps');
  const lpsRow = lps ? spanRow(lps, { name: PHASE_NAMES.lps, nested: true }) : null;
  if (lpsRow) {
    const grade = lpsGrade(data);
    lpsRow.fraction = grade ? grade.fraction : null;
    lpsRow.percent = grade ? grade.percent : null;
  }

  let lpsPlaced = false;
  for (const cell of cells) {
    rows.push(chapterRow(
      cell,
      find(CHAPTER_OWN_SPAN[cell.key]),
      find(CHAPTER_REGION[cell.key]),
    ));
    // The LPS sits UNDER Phase D — it is a component of that chapter, not a
    // sibling of it.
    if (cell.key === 'phase_d' && lpsRow) {
      rows.push(lpsRow);
      lpsPlaced = true;
    }
  }
  // A payload with spans but no chapters (the archive serves the grade without
  // them) still gets its LPS row — it just carries no grade unless the
  // sub-scores came along.
  if (lpsRow && !lpsPlaced) rows.push(lpsRow);

  return rows;
}
