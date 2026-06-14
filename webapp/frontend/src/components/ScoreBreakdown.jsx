import { deriveScoreBreakdown } from './setupScoreMath';

const formatScore = (value) => (
  value == null || !Number.isFinite(Number(value)) ? '--' : `${Math.round(Number(value))}`
);

export function ScoreBreakdownPills({ subScores, className = '', style }) {
  const breakdown = deriveScoreBreakdown(subScores);

  return (
    <div className={`score-breakdown ${className}`.trim()} style={style}>
      <span
        className="score-pill score-pill-visual"
        title="Visual / structural score: base shape, tightness, touches, LPS, contraction, and ascending support."
      >
        <span>Visual</span>
        <strong>{formatScore(breakdown.visual.score)}</strong>
      </span>
      <span
        className="score-pill score-pill-market"
        title="Market / confirmation score: volume dry-up, uptrend, relative strength, 52-week proximity, breadth, and ADR."
      >
        <span>Market</span>
        <strong>{formatScore(breakdown.market.score)}</strong>
      </span>
    </div>
  );
}
