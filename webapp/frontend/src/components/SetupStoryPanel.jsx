import { ScoreBreakdownPills } from './ScoreBreakdown';
import { TagRow } from './SetupTags';
import { warningItems } from './chapterStrip.js';
import { storyRows } from './setupStoryRows.js';
import { explainTip } from './tooltipText';
import { formatScore } from '../utils/scoreFormat.js';

// "Why It Stands Out" — the lens's protagonist, and now its only structure
// panel (operator fold, 2026-08-12).
//
// It used to be two sections side by side that said the same thing twice:
// "Technical Structure Analysis" listed Phase B/C/D as spans you could hover to
// light the chart, and this one listed Phase B/C/D again as graded chapters.
// Fused, each phase is ONE row — its span, its words, its grade — read top to
// bottom the way the chart reads left to right, with the last support test
// finally carrying a grade of its own (setupStoryRows owns that arithmetic and
// the ordering; this file only lays it out).
//
// The rows speak the house control grammar their lens siblings speak
// (.phase-bin-control, .narrative-glyph, the old chapter cells): hover or focus
// lights the matching region on the chart through the ONE activeRegion channel,
// and a row with nothing to light is inert rather than a dead-looking button.

const fx1 = (value) => (value == null ? '—' : Number(value).toFixed(1));

function rowTip(row) {
  if (row.percent != null) {
    return explainTip({
      what: `The last support test grades ${row.percent}% — how tight its candles are.`,
      why: "Those points are already counted inside Phase D, so this row shows its own grade rather than points of the grade's 100.",
      use: 'Hover it to light the LPS zone on the chart, then check the shelf is as tight as the number claims.',
    });
  }
  if (row.points != null) {
    return explainTip({
      what: `${row.name} — ${row.detail}`,
      why: `It contributes ${fx1(row.points)} of the grade's 100${row.subtext ? ` · ${row.subtext}` : ''}.`,
      use: row.region
        ? 'Hover it to light that part of the base on the chart.'
        : 'It reads the chart around the base, so there is nothing to light.',
    });
  }
  return explainTip({
    what: `${row.name} — ${row.detail}`,
    why: row.key === 'a'
      ? 'Phase A is the lead-in that ends the trend before the base opens — it carries no chapter of its own, so it is a span, not a grade.'
      : 'No grade for this row came across the wire.',
    use: row.region ? 'Hover it to light that part of the chart.' : 'Nothing to light.',
  });
}

function StoryRow({ isActive, onRegionChange, row }) {
  const interactive = Boolean(row.region);
  const Element = interactive ? 'button' : 'div';
  const handlers = interactive
    ? {
      type: 'button',
      onBlur: () => onRegionChange?.(null),
      onFocus: () => onRegionChange?.(row.region),
      onMouseEnter: () => onRegionChange?.(row.region),
      onMouseLeave: () => onRegionChange?.(null),
    }
    : {};

  return (
    <Element
      {...handlers}
      className={[
        'story-row',
        `phase-bin-${row.key}`,
        interactive ? '' : 'is-static',
        row.nested ? 'is-nested' : '',
        isActive ? 'is-active' : '',
      ].filter(Boolean).join(' ')}
      title={rowTip(row)}
    >
      <span className="phase-bin-token">{row.token}</span>
      <span className="story-copy">
        {/* Cause / Trend / LPS ARE their token — the chip already says the
            word, so repeating it as the name would print "LPS  LPS". The
            phases keep both, because "B" and "Phase B" are not the same read. */}
        {row.name === row.token ? null : <span className="phase-bin-name">{row.name}</span>}
        <span className="phase-bin-detail">
          {row.subtext ? `${row.detail} · ${row.subtext}` : row.detail}
        </span>
      </span>
      {/* No track at all on an ungraded row — an empty bar would read as a
          measured zero, which is the one thing this lens never fakes. */}
      <span className="story-bar-cell">
        {row.fraction != null ? (
          <span className="story-bar">
            <span
              className="story-fill"
              style={{
                width: `${(row.fraction * 100).toFixed(1)}%`,
                ...(row.color ? { background: row.color } : null),
              }}
            />
          </span>
        ) : null}
      </span>
      <span className="story-grade">
        {row.percent != null ? `${row.percent}%` : fx1(row.points)}
      </span>
    </Element>
  );
}

export default function SetupStoryPanel({ activeRegion, data, note, onRegionChange, regions = [] }) {
  const rows = storyRows(data, regions);
  const warnings = warningItems(data);
  const graded = data?.ta_grade != null;

  return (
    <section className="stock-lens-section stock-lens-story">
      <div className="stock-lens-section-header">
        <span>Why It Stands Out</span>
        {note ? <small>{note}</small> : null}
      </div>
      <div className="story-topline">
        {graded ? (
          <span
            className="ta-grade-headline"
            title="Technical Analysis Grade — one 0-100 visual grade; the rows below read the chart's story top to bottom"
          >
            <span className="ta-grade-value">{formatScore(data.ta_grade)}</span>
            <span className="ta-grade-scale">/100</span>
          </span>
        ) : null}
        <TagRow data={data} maxTags={null} style={{ flex: 1, minWidth: 0, padding: 0 }} />
      </div>
      {rows.length > 0 && (
        <div className="story-rows">
          {rows.map((row) => (
            <StoryRow
              key={row.key}
              isActive={Boolean(row.region) && activeRegion === row.region}
              onRegionChange={onRegionChange}
              row={row}
            />
          ))}
        </div>
      )}
      {/* Dual-epoch (task 12): a graded payload reads through the rows above; a
          pre-v2 payload keeps the legacy Visual/Market pills. The pills' JSX+CSS
          delete as one unit at the flag's retirement. */}
      {!graded ? <ScoreBreakdownPills subScores={data.sub_scores} style={{ marginTop: 10 }} /> : null}
      {warnings.length > 0 && (
        <div className="ta-grade-warnings">
          {warnings.map((warning) => (
            <span key={warning.id} className="ta-grade-warning">
              ⚠ {warning.label}{warning.cost ? ` ${warning.cost}` : ' — no cost yet'}
            </span>
          ))}
        </div>
      )}
    </section>
  );
}
