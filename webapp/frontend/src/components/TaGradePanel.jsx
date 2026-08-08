// The Technical Analysis Grade panel (build task 12): the 0-100 as the
// lens's single dominant datum — mono/tabular with a permanent /100 scale
// marker so it can never be misread as the legacy raw score — and the
// chapter strip beneath it in FIXED story order (never points-sorted),
// equal-width segments whose FILL is the engine-resolved earned fraction
// (an A/B reweight moves the fill, never the panel's shape). Chromatically
// neutral: no chapter element wears a tier hue; warnings keep the only hot
// treatment, as visible labeled line items with their cost.
import { CHAPTER_REGION, chapterCells, warningItems } from './chapterStrip.js';
import { formatScore } from '../utils/scoreFormat.js';

export function TaGradePanel({ data, onRegionChange }) {
  const cells = chapterCells(data);
  if (cells.length === 0) return null;
  const warnings = warningItems(data);
  return (
    <div className="ta-grade-panel">
      <div
        className="ta-grade-headline"
        title="Technical Analysis Grade — one 0-100 visual grade; the chapters read the chart's story left to right"
      >
        <span className="ta-grade-value">{formatScore(data.ta_grade)}</span>
        <span className="ta-grade-scale">/100</span>
      </div>
      <div className="ta-grade-strip">
        {cells.map((cell) => (
          <div
            key={cell.key}
            className="ta-grade-chapter"
            title={cell.subtext
              ? `${cell.label}: ${cell.subtext}`
              : `${cell.label}: ${cell.points.toFixed(1)} of the grade's 100`}
            onMouseEnter={() => onRegionChange?.(CHAPTER_REGION[cell.key] ?? null)}
            onMouseLeave={() => onRegionChange?.(null)}
          >
            <span className="ta-grade-chapter-label">{cell.short}</span>
            <span className="ta-grade-chapter-bar">
              <span
                className="ta-grade-chapter-fill"
                style={{ width: `${(cell.fraction * 100).toFixed(1)}%` }}
              />
            </span>
            <span className="ta-grade-chapter-points">{cell.points.toFixed(1)}</span>
            {cell.subtext ? (
              <span className="ta-grade-chapter-caveat">{cell.subtext}</span>
            ) : null}
          </div>
        ))}
      </div>
      {warnings.length > 0 && (
        <div className="ta-grade-warnings">
          {warnings.map((warning) => (
            <span key={warning.id} className="ta-grade-warning">
              ⚠ {warning.label}{warning.cost ? ` ${warning.cost}` : ' — no cost yet'}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
