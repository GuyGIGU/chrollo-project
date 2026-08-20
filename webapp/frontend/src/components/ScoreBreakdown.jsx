import { deriveScoreBreakdown } from './setupScoreMath';
import { explainTip } from './tooltipText';
import { fmtRound } from '../utils/format';

const formatScore = (value) => fmtRound(value, '--');

export function ScoreBreakdownPills({ subScores, className = '', style }) {
  const breakdown = deriveScoreBreakdown(subScores);

  return (
    <div className={`score-breakdown ${className}`.trim()} style={style}>
      <span
        className="score-pill score-pill-visual"
        title={explainTip({
          what: 'The structure side of the setup score: base shape, tightness, touches, LPS quality, contraction, and ascending support.',
          why: 'It tells us whether the chart has a clean, workable base before we care about confirmation.',
          use: 'Favor higher visual scores when planning risk around the box; a weak visual score means the setup needs more manual scrutiny.',
        })}
      >
        <span>Visual</span>
        <strong>{formatScore(breakdown.visual.score)}</strong>
      </span>
      <span
        className="score-pill score-pill-market"
        title={explainTip({
          what: 'The confirmation side of the setup score: volume dry-up, trend, relative strength, 52-week proximity, market breadth, and ADR.',
          why: 'It tells us whether the setup has supportive context beyond the box itself.',
          use: 'Use it as a quality filter after the chart structure passes; it should not replace the trigger and risk plan.',
        })}
      >
        <span>Market</span>
        <strong>{formatScore(breakdown.market.score)}</strong>
      </span>
    </div>
  );
}
