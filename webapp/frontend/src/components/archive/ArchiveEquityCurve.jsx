import { fixed } from '../../utils/archiveTabUtils';
import { CHART_COLORS } from '../chartTheme';

export default function ArchiveEquityCurve({ data }) {
  if (!data?.points?.length) {
    return (
      <div className="glass-panel">
        <div style={{ fontSize: '13px', fontWeight: 600, marginBottom: '4px' }}>Equity Curve (R)</div>
        <div style={{ color: 'var(--text-muted)', fontSize: '11px' }}>
          No triggered setups with R-multiples yet. Run forward-return updater.
        </div>
      </div>
    );
  }

  const chart = buildCurve(data.points);
  const summary = data.summary || {};
  // Literal (not var()) — this colors an SVG stroke attribute, where CSS
  // variables don't resolve.
  const lineColor = chart.finalCum >= 0 ? CHART_COLORS.success : '#c76b73';
  return (
    <div className="glass-panel instrument-well">
      <div style={{ alignItems: 'baseline', display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
        <div style={{ fontSize: '13px', fontWeight: 600 }}>Equity Curve (R)</div>
        <div style={{ color: lineColor, fontFamily: "'JetBrains Mono', monospace", fontSize: '12px', fontWeight: 700 }}>
          {chart.finalCum >= 0 ? '+' : ''}{fixed(chart.finalCum, 2)}R
        </div>
      </div>
      <div style={{ color: 'var(--text-muted)', fontSize: '10px', marginBottom: '8px' }}>
        Cumulative R from {summary.total_setups ?? '-'} triggered setups - WR {fixed(summary.win_rate != null ? summary.win_rate * 100 : null, 0)}% - Max DD {fixed(summary.max_drawdown_r, 2)}R
      </div>
      <svg viewBox={`0 0 ${chart.width} ${chart.height}`} preserveAspectRatio="none" style={{ height: '140px', width: '100%' }}>
        <line x1="0" y1={chart.zeroY} x2={chart.width} y2={chart.zeroY} stroke="rgba(255,255,255,0.15)" strokeDasharray="3,3" />
        <path d={chart.path} fill="none" stroke={lineColor} strokeWidth="2" />
      </svg>
      <div style={{ color: 'var(--text-muted)', display: 'flex', fontSize: '10px', justifyContent: 'space-between', marginTop: '6px' }}>
        <span>Best: <span style={{ color: 'var(--success)' }}>{summary.best_r != null ? '+' : ''}{fixed(summary.best_r, 2)}R</span></span>
        <span>Worst: <span style={{ color: 'var(--danger)' }}>{fixed(summary.worst_r, 2)}R</span></span>
        <span>Avg: <span style={{ color: 'var(--text-main)' }}>{fixed(summary.avg_r, 2)}R</span></span>
      </div>
    </div>
  );
}

const buildCurve = (points) => {
  const width = 600;
  const height = 140;
  const cums = points
    .map(point => Number(point.cum_r))
    .filter(Number.isFinite);
  if (!cums.length) {
    return {
      finalCum: 0,
      height,
      path: '',
      width,
      zeroY: height / 2,
    };
  }
  const minR = Math.min(0, ...cums);
  const maxR = Math.max(0, ...cums);
  const span = maxR - minR || 1;
  const xStep = cums.length > 1 ? width / (cums.length - 1) : width / 2;
  const yFor = (value) => height - ((value - minR) / span) * (height - 4) - 2;
  const path = cums.map((cumR, index) => {
    const x = index * xStep;
    return `${index === 0 ? 'M' : 'L'} ${x.toFixed(1)} ${yFor(cumR).toFixed(1)}`;
  }).join(' ');
  const finalValue = cums[cums.length - 1];

  return {
    finalCum: Number.isFinite(Number(finalValue)) ? Number(finalValue) : 0,
    height,
    path,
    width,
    zeroY: yFor(0),
  };
};
