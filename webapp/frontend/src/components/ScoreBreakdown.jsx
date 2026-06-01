import { deriveScoreBreakdown } from './setupScoreMath';

const formatScore = (value) => value == null ? '--' : `${value}`;

export function ScoreBreakdownPills({ subScores, includeFusion = false, className = '', style }) {
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
      {includeFusion && (
        <span
          className="score-pill score-pill-fusion"
          title="Fusion score: rewards setups where both Visual and Market scores are strong."
        >
          <span>Both</span>
          <strong>{formatScore(breakdown.fusion)}</strong>
        </span>
      )}
    </div>
  );
}
