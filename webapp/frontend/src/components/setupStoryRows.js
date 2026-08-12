// The fused setup story — ONE ordered list where every phase of the chart
// carries both its measured SPAN and its GRADE.
//
// Operator ruling 2026-08-12: "Why It Stands Out" and "Technical Structure
// Analysis" were the same panel written twice. Both listed Phase B/C/D — one as
// spans (hover to light the chart), the other as graded chapters — and neither
// was whole: the spans had no grades, and the grade strip had no LPS, the one
// phase read last and hardest. Fused, the list reads left→right like the chart.
//
// SECOND RULING, same day, after the fused panel shipped — two moves that this
// module is the display half of:
//   1. Cause and Phase B graded the same object from two sides and are now ONE
//      chapter, `consolidation`: "a two-sided zigzag price action can be folded
//      into one of the quality traits we look for in a consolidation as a
//      whole."
//   2. Phase C is no longer graded. "There is no telling whether a setup that
//      has one will win or not… it's more important for the engine to FIND
//      Phase C (spring) or the 'V' tip structure just to put a MARK on where the
//      right-most side of the consolidation is, to understand the order of how
//      the setup played out. Same with shakeouts."
// So the list now carries two kinds of thing, and they must not look alike:
// GRADED CHAPTERS (consolidation, Phase D, Trend — each with points) and MARKS
// (Phase A, Phase C — a found event, a place on the chart, no number). A mark
// with a number would be the ungrading undone.
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

// WHAT EACH CHAPTER GRADES, in the words taxonomy.py's own chapter block uses.
//
// These describe the QUESTION the chapter scores, never an event on the chart.
// That distinction is the whole point: the first cut used the phase SPAN's
// vocabulary here as a fallback, so a chapter whose span did not resolve printed
// the event anyway — `phase_c` read "Support shakeout or test" on 212 of 302
// live setups where the engine had detected no Phase C at all, in the same words
// the 16 real ones used (review 2026-08-12). A chapter's grade is real whether
// or not its span resolved; what must never happen is the panel asserting the
// event that produced it.
const CHAPTER_GRADES = {
  consolidation: 'The base itself — tight, mature, two-sided, contracting, on a rising floor',
  phase_d: 'The right side into the pivot — LPS, volume dry-up, the squeeze',
  trend: 'The chart around the base — trend, RS, 52-week, ADR',
};

// Said plainly when a chapter owns a phase band and that band did not resolve.
// "No X on this chart" is a measured absence and reads as one; it is NOT the
// three-state "not measured", because the chapter's own grade is right there
// beside it.
const absentSpan = (name) => `No ${name} on this chart`;

// The LPS's own grade: the engine's lps_tightness term as a fraction of its cap.
//
// It is deliberately NOT a chapter, and its row deliberately shows a PERCENTAGE
// rather than points of the grade's 100 — because those points are already
// counted inside Phase D. Printing them again in the same column would make the
// column stop summing to the grade, which is exactly the kind of quiet
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

// A row exists in one of three relationships with a band on the chart:
//   'measured' — the band resolved and this row can light it
//   'absent'   — this chapter owns a band and the engine found none here
//   'none'     — the chapter never had a band to own (Trend)
// The panel renders these differently on purpose. Collapsing 'absent' into
// 'measured' is what produced the Phase-C lie.
export const SPAN_STATES = ['measured', 'absent', 'none'];

const spanRow = (region, extra = {}) => ({
  key: region.key,
  // The PHASE this row belongs to (a|b|c|d|lps), or null for a chapter that is
  // not a phase. It is what the token chip is coloured by, so it must not be
  // the chapter key: the panel keyed the colour class off `key` and emitted
  // `phase-bin-phase_b` against a stylesheet that only defines `.phase-bin-b`,
  // so B, C and D lost the tint that ties them to their band on the chart while
  // A and LPS kept theirs (review 2026-08-12). It is also deliberately NOT the
  // resolved region: Phase C is pink whether or not a band was found.
  phase: region.key,
  token: region.label,
  name: region.name,
  detail: region.detail,
  grades: null,
  spanState: 'measured',
  region: region.key,
  color: region.color ?? null,
  points: null,
  fraction: null,
  percent: null,
  subtext: null,
  mark: false,
  nested: false,
  ...extra,
});

// A MARK: a found event with a place on the chart and no grade — Phase A (the
// lead-in that ends the trend) and Phase C (the shakeout or spring). Marks exist
// so the operator can read the ORDER the setup played out in; they are rendered
// as a narrow rail rather than a column, because a mark that took a chapter's
// width would claim a weight it does not carry. A mark appears only when its
// band resolved: absence of a mark is simply no mark, never "no Phase C" typed
// into the panel where 70% of setups would wear it.
const markRow = (region) => spanRow(region, { mark: true });

// The chapters that ARE a phase, and so speak that phase's measured words.
// `consolidation` is not among them: it lights the box (CHAPTER_REGION) but
// grades the base as a whole — tightness, age, touches, traversal, contraction,
// the rising floor and the completed story — so borrowing the B band's sentence
// ("Two-sided range work") would under-describe it by most of its own terms.
const CHAPTER_OWN_SPAN = { phase_d: 'd' };

const chapterRow = (cell, span, region, hasBands) => {
  // `hasBands` false = nobody looked (a weekly/monthly pane, where the daily
  // bands do not apply; an archive row with no candles). Absence of a band can
  // only be REPORTED where bands were read — saying "no Phase D on this chart"
  // over a weekly pane would be the same lie in the other direction.
  const ownsSpan = hasBands && CHAPTER_OWN_SPAN[cell.key] != null;
  const spanState = ownsSpan ? (span ? 'measured' : 'absent') : 'none';
  return {
    key: cell.key,
    // The chapter wears the hue of the band it LIGHTS (CHAPTER_REGION), not of
    // the band it owns: Consolidation owns none — it grades the base as a whole
    // — but it lights the box, and a purple column that lights the purple box is
    // the connection this panel exists to make. Taken from the static routing
    // map, never the resolved region, so Phase D stays blue on a chart where its
    // band did not resolve.
    phase: CHAPTER_REGION[cell.key] ?? null,
    token: cell.short,
    // A chapter that owns a phase wears the PHASE's name (the same words by
    // construction — CHAPTER_LABELS.phase_d.label === PHASE_NAMES.d); an unknown
    // wire chapter falls through with its own label, never dropped.
    name: cell.label,
    // Measured: the band's own words. Absent: said plainly. No band to own: what
    // the chapter grades. Never the event sentence on a chart without the event.
    detail: spanState === 'measured'
      ? span.detail
      : spanState === 'absent'
        ? absentSpan(cell.label)
        : (CHAPTER_GRADES[cell.key] ?? ''),
    // What this chapter grades, always available for the tooltip — so a row
    // whose band is absent can still say what earned its points.
    grades: CHAPTER_GRADES[cell.key] ?? null,
    spanState,
    region: region ? region.key : null,
    color: region?.color ?? null,
    points: cell.points,
    fraction: cell.fraction,
    percent: null,
    subtext: cell.subtext,
    mark: false,
    nested: false,
  };
};

// The rows, in chart order. `regions` is buildPhaseRegions' output (empty on a
// higher-timeframe pane, where the daily phases mean nothing) — with none, the
// chapters still grade, they simply light nothing.
export function storyRows(data, regions = []) {
  const cells = chapterCells(data);
  const find = (key) => regions.find((region) => region.key === key) || null;
  const rows = [];

  // Phase A leads: the climax→AR that ended the trend, before the box. A mark,
  // like Phase C — it is a chart-highlight target the operator reads for order,
  // and it never carried a chapter of its own.
  const phaseA = find('a');
  if (phaseA) rows.push(markRow(phaseA));

  // The WIRE's chapters drive the middle (chapterStrip's law): the backend pins
  // their order, and an unknown chapter renders verbatim instead of vanishing.
  const lps = find('lps');
  const lpsRow = lps ? spanRow(lps, { name: PHASE_NAMES.lps, nested: true }) : null;
  if (lpsRow) {
    const grade = lpsGrade(data);
    lpsRow.fraction = grade ? grade.fraction : null;
    lpsRow.percent = grade ? grade.percent : null;
  }

  const spring = find('c');
  let springPlaced = false;
  let lpsPlaced = false;
  for (const cell of cells) {
    // The Phase-C mark sits where it sits on the chart: after the range work,
    // before the right side.
    if (cell.key === 'phase_d' && spring) {
      rows.push(markRow(spring));
      springPlaced = true;
    }
    rows.push(chapterRow(
      cell,
      find(CHAPTER_OWN_SPAN[cell.key]),
      find(CHAPTER_REGION[cell.key]),
      regions.length > 0,
    ));
    // The LPS sits UNDER Phase D — it is a component of that chapter, not a
    // sibling of it.
    if (cell.key === 'phase_d' && lpsRow) {
      rows.push(lpsRow);
      lpsPlaced = true;
    }
  }
  // A payload with spans but no chapters (the archive serves the grade without
  // them) still gets its marks and its LPS, in the same chart order — they just
  // carry no grade unless the sub-scores came along.
  if (spring && !springPlaced) rows.push(markRow(spring));
  if (lpsRow && !lpsPlaced) rows.push(lpsRow);

  return rows;
}
