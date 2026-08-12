import { useState } from 'react';
import { ScoreBreakdownPills } from './ScoreBreakdown';
import { TagRow } from './SetupTags';
import { warningItems } from './chapterStrip.js';
import { storyRows } from './setupStoryRows.js';
import { explainTip } from './tooltipText';
import { formatScore } from '../utils/scoreFormat.js';

// "Why It Stands Out" — the lens's protagonist, and its only structure panel.
//
// THE CONTINUED AXIS. The panel is the chart's time axis carried on below it:
// the phases march ACROSS the width as vertical stacks in chart order, never
// points-sorted, so position on the panel maps to position on the chart and the
// hover connection is pre-cognitive rather than learned. The first cut stacked
// them as seven 28px rows, which spent 75% of a 1476px panel on air and left the
// type at 10-11px (operator 2026-08-12: "plenty of dead space and yet everything
// is very tiny"). Read vertically, each phase gets ~220px of real column: a 20px
// figure, a named chip, and three readable lines instead of one clamped line
// beside 700px of nothing.
//
// The 6px rule capping each stack is doing three jobs at once — it is the
// separator, the earned-fraction gauge, and the chart's phase hue laid flat.
// With no column gap the segments touch, so the bank's top edge is ONE
// continuous multi-hued track and a fill is directly comparable to the fill two
// columns over. That is the whole "shape in under two seconds" read; the chrome
// IS the measurement, which is why no phase wears a card, a border or a radius.
//
// The LPS is not a seventh stack. Its points are already counted inside Phase D,
// so it is a readout recessed INTO Phase D's column: gold-railed and
// percent-suffixed where every chapter is flat and prints bare points, one line
// below the number line the chapters share.

const fx1 = (value) => (value == null ? '—' : Number(value).toFixed(1));
const lowerFirst = (text) => (text ? text.charAt(0).toLowerCase() + text.slice(1) : text);

// Why a row can or cannot be hovered onto the chart — one line per span state,
// so an absent band never borrows the Trend chapter's excuse (review 2026-08-12:
// a Phase C with no band was telling the operator it "reads the chart around the
// base", which is a different chapter's sentence and simply untrue).
const SPAN_USE = {
  measured: 'Hover it to light that part of the base on the chart.',
  absent: 'The engine found no such band on this chart, so there is nothing to light — the grade above comes from the rest of what this chapter reads.',
  none: 'It reads the chart around the base, so there is nothing to light.',
};

function rowTip(row) {
  if (row.percent != null) {
    return explainTip({
      what: `The last support test grades ${row.percent}% — how tight its candles are.`,
      why: "Those points are already counted inside Phase D, so this reads as a percentage rather than points of the grade's 100.",
      use: 'Hover it to light the LPS zone on the chart, then check the shelf is as tight as the number claims.',
    });
  }
  if (row.points != null) {
    return explainTip({
      what: row.grades && row.spanState !== 'measured'
        // The band is absent or was never read, so the row must not be
        // explained by an event. Say what the chapter GRADES instead.
        ? `${row.name} grades ${lowerFirst(row.grades)}. ${row.detail}.`
        : `${row.name} — ${row.detail}`,
      why: `It contributes ${fx1(row.points)} of the grade's 100${row.subtext ? ` · ${row.subtext}` : ''}.`,
      use: SPAN_USE[row.spanState] || SPAN_USE.none,
    });
  }
  return explainTip({
    what: `${row.name} — ${row.detail}`,
    why: row.key === 'a'
      ? 'Phase A is the lead-in that ends the trend before the base opens — it carries no chapter of its own, so it is a span, not a grade.'
      : 'No grade for this row came across the wire.',
    use: row.region ? SPAN_USE.measured : SPAN_USE.none,
  });
}

function StoryColumn({ engaged, footnote, onEngage, onRegionChange, row, sub }) {
  const interactive = Boolean(row.region);
  const Element = interactive ? 'button' : 'div';
  // NOT row.fraction: chapterCells coerces a missing fraction to 0, so a
  // fraction test would seat a full empty track under a chapter that was never
  // measured — absence dressed as a measured zero. One flag drives both the
  // gauge and the figure, so they can never disagree.
  const graded = row.points != null || row.percent != null;
  const [whole, decimal] = graded && row.points != null ? fx1(row.points).split('.') : [];
  const bind = interactive
    ? {
      type: 'button',
      onBlur: () => { onEngage(null); onRegionChange?.(null); },
      onFocus: () => { onEngage(row.key); onRegionChange?.(row.region); },
      onMouseEnter: () => { onEngage(row.key); onRegionChange?.(row.region); },
      onMouseLeave: () => { onEngage(null); onRegionChange?.(null); },
    }
    : {};
  const footnoted = Boolean(footnote) && row.subtext === footnote;
  const detail = row.subtext && !footnoted ? `${row.detail} · ${row.subtext}` : row.detail;
  const lit = engaged === row.key || (sub && engaged === sub.key);

  return (
    <div className={[
      'story-col',
      row.phase ? `phase-bin-${row.phase}` : '',
      lit ? 'is-engaged' : '',
    ].filter(Boolean).join(' ')}
    >
      <Element
        {...bind}
        className={[
          'story-face',
          interactive ? '' : 'is-static',
          engaged === row.key ? 'is-engaged' : '',
        ].filter(Boolean).join(' ')}
        title={rowTip(row)}
      >
        {/* No track at all on an ungraded row — an empty gauge would read as a
            measured zero, the one thing this lens never fakes. */}
        {graded ? (
          <span className="story-gauge">
            <span
              className="story-gauge-fill"
              style={{ width: `${((row.fraction ?? 0) * 100).toFixed(1)}%` }}
            />
          </span>
        ) : <span className="story-gauge is-ungraded" />}

        <span className={`story-value${graded ? '' : ' is-absent'}`}>
          {graded
            ? <>{whole}<span className="story-dec">.{decimal}</span></>
            : 'span only'}
        </span>

        <span className="story-name">
          <span className="phase-bin-token">{row.token}</span>
          {/* Cause / Trend / LPS ARE their token — repeating it would print
              "LPS  LPS". The phases keep both: "B" and "Phase B" differ. */}
          {row.name === row.token ? null : <span className="story-name-text">{row.name}</span>}
        </span>

        <span className="story-detail">
          {detail}{footnoted ? <sup className="story-dagger">†</sup> : null}
        </span>
      </Element>

      {sub ? (
        <button
          className={`story-sub${engaged === sub.key ? ' is-engaged' : ''}`}
          onBlur={() => { onEngage(null); onRegionChange?.(null); }}
          onFocus={() => { onEngage(sub.key); onRegionChange?.(sub.region); }}
          onMouseEnter={() => { onEngage(sub.key); onRegionChange?.(sub.region); }}
          onMouseLeave={() => { onEngage(null); onRegionChange?.(null); }}
          title={rowTip(sub)}
          type="button"
        >
          <span className="phase-bin-token">{sub.token}</span>
          <span className="story-sub-name">{sub.detail}</span>
          {sub.percent != null
            ? <span className="story-sub-value">{sub.percent}<span className="story-sub-unit">%</span></span>
            : <span className="story-sub-value is-absent">not graded</span>}
        </button>
      ) : null}
    </div>
  );
}

// `activeRegion` is deliberately NOT a prop. The panel's own lock-on is driven
// by a local key, because CHAPTER_REGION.cause and CHAPTER_REGION.phase_b are
// both 'b' — an activeRegion-driven state lights TWO columns on one hover. The
// outbound onRegionChange channel is unchanged, so the chart still lights band
// 'b' for either of them, which is correct.
export default function SetupStoryPanel({ data, note, onRegionChange, regions = [] }) {
  const rows = storyRows(data, regions);
  const warnings = warningItems(data);
  const graded = data?.ta_grade != null;
  const [engaged, setEngaged] = useState(null);

  // Columns, with the LPS attached to its parent. Guarded on phase_d: an
  // archive payload can serve an orphan LPS with no Phase D to sit in, and it
  // must not silently become a component of Phase A.
  const cols = [];
  for (const row of rows) {
    const prev = cols[cols.length - 1];
    if (row.nested && prev && prev.row.key === 'phase_d') prev.sub = row;
    else cols.push({ row, sub: null });
  }

  // The caveat said once: readCaveats hands ONE string to both phase_b and
  // phase_d, so the panel printed the same sentence twice. Any subtext carried
  // by two or more columns hoists to a footnote and its owners get a dagger.
  // Behaviour, not contract — if the engine ever emits per-chapter caveats the
  // hoist simply stops firing and each renders inline again.
  const shared = new Map();
  for (const row of rows) if (row.subtext) shared.set(row.subtext, (shared.get(row.subtext) || 0) + 1);
  const footnote = [...shared].find(([, count]) => count >= 2)?.[0] ?? null;

  return (
    <section className="stock-lens-section stock-lens-story">
      <div className="stock-lens-section-header">
        <span>Why It Stands Out</span>
        {/* maxTags="auto" measures its own container, so flex:1 + minWidth:0 are
            mandatory here or its ResizeObserver reads a collapsed width and
            shows a single chip. */}
        <TagRow compact data={data} maxTags="auto" style={{ flex: 1, minWidth: 0, padding: 0 }} />
        {note ? <small>{note}</small> : null}
      </div>

      <div
        className={`story-bank${cols.length <= 3 ? ' is-sparse' : ''}`}
        style={{ '--story-cols': cols.length }}
      >
        <div className="story-total">
          <span className="story-total-label">TA grade</span>
          {graded ? (
            <>
              <span
                className="story-total-fig"
                title="Technical Analysis Grade — one 0-100 visual grade; the columns beside it read the chart's story left to right"
              >
                <span className="story-total-value">{formatScore(data.ta_grade)}</span>
                <span className="story-total-scale">/100</span>
              </span>
              <small className="story-total-note">chapters sum to this</small>
            </>
          ) : (
            /* Dual-epoch: a pre-v2 payload keeps the legacy pills, in this same
               cell, so the grid never gets a hole. Deletes as one unit at the
               flag's retirement. */
            <ScoreBreakdownPills subScores={data.sub_scores} />
          )}
          {warnings.length > 0 && (
            <div className="ta-grade-warnings">
              {warnings.map((warning) => (
                <span className="ta-grade-warning" key={warning.id}>
                  ⚠ {warning.label}{warning.cost ? ` ${warning.cost}` : ' — no cost yet'}
                </span>
              ))}
            </div>
          )}
        </div>

        {cols.map(({ row, sub }) => (
          <StoryColumn
            engaged={engaged}
            footnote={footnote}
            key={row.key}
            onEngage={setEngaged}
            onRegionChange={onRegionChange}
            row={row}
            sub={sub}
          />
        ))}
      </div>

      {footnote ? <p className="story-footnote">† {footnote}</p> : null}
    </section>
  );
}
