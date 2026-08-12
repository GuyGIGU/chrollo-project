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
// hover connection is pre-cognitive rather than learned.
//
// GRADES AND MARKS ARE DIFFERENT OBJECTS (operator ruling 2026-08-12, second
// sitting). Three chapters carry points — Consolidation, Phase D, Trend — and
// they get the width. Phase A and Phase C carry no points at all: they are
// MARKS, "just to put a mark on where the right-most side of the consolidation
// is, to understand the order of how the setup played out". A mark is a narrow
// rail with the phase chip standing where its neighbours print a number, so
// scanning the number line reads 73 | ▪A | 42.2 | ▪C | 23.4 | 6.4 — the ungraded
// events are visibly not part of the addition. Giving a mark a full column (as
// the first cut gave Phase A and Phase C) spends a third of the panel on things
// that were deliberately taken out of the grade.
//
// The 6px rule capping each graded stack is doing three jobs at once — it is the
// separator, the earned-fraction gauge, and the chart's phase hue laid flat.
// With no column gap the segments touch, so the bank's top edge is ONE
// continuous multi-hued track and a fill is directly comparable to the fill two
// columns over. That is the whole "shape in under two seconds" read; the chrome
// IS the measurement, which is why no phase wears a card, a border or a radius.
//
// The LPS is not a fourth chapter. Its points are already counted inside Phase
// D, so it is a readout recessed INTO Phase D's column: gold-railed and
// percent-suffixed where every chapter is flat and prints bare points.

const fx1 = (value) => (value == null ? '—' : Number(value).toFixed(1));
const lowerFirst = (text) => (text ? text.charAt(0).toLowerCase() + text.slice(1) : text);

// Why a row can or cannot be hovered onto the chart. Keyed off the REGION
// first, because owning a band and lighting one are different questions:
// Consolidation lights the box while owning no band of its own, and reading
// that off spanState alone printed "there is nothing to light" over a row that
// lights the whole base.
function spanUse(row) {
  if (row.region) return 'Hover it to light that part of the chart.';
  if (row.spanState === 'absent') {
    return 'The engine found no such band on this chart, so there is nothing to light — the grade beside it comes from the rest of what this chapter reads.';
  }
  return 'Nothing on this chart to point at.';
}

function rowTip(row) {
  if (row.mark) {
    return explainTip({
      what: `${row.name} — ${row.detail}`,
      why: row.key === 'a'
        ? 'The lead-in that ended the trend, before the base opened. A mark, not a grade.'
        : 'A mark, not a grade: the engine finds the shakeout to fix where the right side of the base begins, and the order the setup played out in. Whether a chart has one says nothing about whether it wins.',
      use: spanUse(row),
    });
  }
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
      use: spanUse(row),
    });
  }
  return explainTip({
    what: `${row.name} — ${row.detail}`,
    why: 'No grade for this row came across the wire.',
    use: spanUse(row),
  });
}

// Hover/focus wiring shared by every clickable face in the bank — three
// near-identical copies drifted apart once already.
const engageBind = (row, onEngage, onRegionChange) => ({
  onBlur: () => { onEngage(null); onRegionChange?.(null); },
  onFocus: () => { onEngage(row.key); onRegionChange?.(row.region); },
  onMouseEnter: () => { onEngage(row.key); onRegionChange?.(row.region); },
  onMouseLeave: () => { onEngage(null); onRegionChange?.(null); },
  type: 'button',
});

// A MARK — an event the engine found and never graded. Narrow by design, and
// carrying no number anywhere: the chip stands on the number line instead.
function StoryMark({ engaged, onEngage, onRegionChange, row }) {
  return (
    <div className={[
      'story-col', 'story-col-mark',
      row.phase ? `phase-bin-${row.phase}` : '',
      engaged === row.key ? 'is-engaged' : '',
    ].filter(Boolean).join(' ')}
    >
      <button
        {...engageBind(row, onEngage, onRegionChange)}
        className={`story-face story-face-mark${engaged === row.key ? ' is-engaged' : ''}`}
        title={rowTip(row)}
      >
        <span className="story-gauge is-mark" />
        <span className="story-value is-mark">
          <span className="phase-bin-token">{row.token}</span>
        </span>
        <span className="story-name">
          <span className="story-name-text">{row.name}</span>
        </span>
        <span className="story-detail is-mark">{row.detail}</span>
      </button>
    </div>
  );
}

function StoryColumn({ engaged, footnote, onEngage, onRegionChange, row, sub }) {
  const interactive = Boolean(row.region);
  const Element = interactive ? 'button' : 'div';
  // NOT row.fraction: chapterCells coerces a missing fraction to 0, so a
  // fraction test would seat a full empty track under a chapter that was never
  // measured — absence dressed as a measured zero. One flag drives both the
  // gauge and the figure, so they can never disagree.
  const graded = row.points != null || row.percent != null;
  const [whole, decimal] = row.points != null ? fx1(row.points).split('.') : [];
  const bind = interactive ? engageBind(row, onEngage, onRegionChange) : {};
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

        {/* An orphan LPS (an archive payload with no Phase D to nest under)
            lands here as a column of its own and carries a PERCENT, not points
            — printing `whole.decimal` for it rendered "undefined.undefined". */}
        <span className={`story-value${graded ? '' : ' is-absent'}`}>
          {row.points != null && <>{whole}<span className="story-dec">.{decimal}</span></>}
          {row.points == null && row.percent != null
            && <>{row.percent}<span className="story-dec">%</span></>}
          {!graded && 'not graded'}
        </span>

        <span className="story-name">
          <span className="phase-bin-token">{row.token}</span>
          {/* Trend and the LPS ARE their token — repeating it would print
              "LPS  LPS". The phases keep both: "D" and "Phase D" differ. */}
          {row.name === row.token ? null : <span className="story-name-text">{row.name}</span>}
        </span>

        <span className="story-detail">
          {detail}{footnoted ? <sup className="story-dagger">†</sup> : null}
        </span>
      </Element>

      {sub ? (
        <button
          {...engageBind(sub, onEngage, onRegionChange)}
          className={`story-sub${engaged === sub.key ? ' is-engaged' : ''}`}
          title={rowTip(sub)}
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
// by a local key: several rows can point at the same band (Consolidation lights
// 'b', and a chapter that owns its band lights the same one), so an
// activeRegion-driven state would light two columns on one hover. The outbound
// onRegionChange channel is unchanged, so the chart still lights the band.
export default function SetupStoryPanel({ data, note, onRegionChange, regions = [] }) {
  const rows = storyRows(data, regions);
  const warnings = warningItems(data);
  const graded = data?.ta_grade != null;
  const [engaged, setEngaged] = useState(null);

  // Columns, with the LPS attached to its parent. Guarded on phase_d: an
  // archive payload can serve an orphan LPS with no Phase D to sit in, and it
  // must not silently become a component of a mark.
  const cols = [];
  for (const row of rows) {
    const prev = cols[cols.length - 1];
    if (row.nested && prev && prev.row.key === 'phase_d') prev.sub = row;
    else cols.push({ row, sub: null });
  }

  // Marks take a fixed rail; the graded chapters share what is left, capped so
  // three of them never stretch to 500px each on a wide modal.
  const track = cols
    .map(({ row }) => (row.mark ? 'var(--story-mark-w)' : 'minmax(0, var(--story-col-max))'))
    .join(' ');

  // The caveat said once: readCaveats hands ONE string to both story chapters,
  // so the panel printed the same sentence twice. Any subtext carried by two or
  // more columns hoists to a footnote and its owners get a dagger. Behaviour,
  // not contract — if the engine ever emits per-chapter caveats the hoist simply
  // stops firing and each renders inline again.
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

      <div className="story-bank" style={{ '--story-track': track }}>
        <div className="story-total">
          {graded ? (
            <>
              <span
                className="story-total-fig"
                title="Technical Analysis Grade — one 0-100 visual grade; the columns beside it read the chart's story left to right"
              >
                <span className="story-total-value">{formatScore(data.ta_grade)}</span>
                <span className="story-total-scale">/100</span>
              </span>
              <span className="story-total-label">Grade</span>
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

        {cols.map(({ row, sub }) => (row.mark ? (
          <StoryMark
            engaged={engaged}
            key={row.key}
            onEngage={setEngaged}
            onRegionChange={onRegionChange}
            row={row}
          />
        ) : (
          <StoryColumn
            engaged={engaged}
            footnote={footnote}
            key={row.key}
            onEngage={setEngaged}
            onRegionChange={onRegionChange}
            row={row}
            sub={sub}
          />
        )))}
      </div>

      {footnote ? <p className="story-footnote">† {footnote}</p> : null}
    </section>
  );
}
