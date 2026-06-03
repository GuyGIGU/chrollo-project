import { memo } from 'react';
import useArchiveCardChart from '../hooks/useArchiveCardChart';
import { labelColor, pct, QUALITY_LABELS, tierColor } from '../utils/archiveTabUtils';
import { subScoresFromSetup } from '../utils/archiveCardUtils';
import { ScoreBreakdownPills } from './ScoreBreakdown';
import { TagRow } from './SetupTags';

const ArchiveCard = memo(({ chartData, onClick, onLabelChange, setup }) => {
  const { chartContainerRef, chartError } = useArchiveCardChart({ chartData, setup });
  const fwd = setup.fwd_return_20d;
  const fwdColor = fwd > 0 ? 'var(--success)' : fwd < 0 ? 'var(--danger)' : 'var(--text-muted)';
  const subScores = subScoresFromSetup(setup);

  return (
    <div
      onClick={() => onClick(setup)}
      onMouseEnter={event => { event.currentTarget.style.borderColor = 'var(--accent-blue)'; }}
      onMouseLeave={event => { event.currentTarget.style.borderColor = 'var(--border-color)'; }}
      style={{
        background: 'var(--bg-panel)',
        border: '1px solid var(--border-color)',
        borderRadius: '6px',
        cursor: 'pointer',
        display: 'flex',
        flexDirection: 'column',
        height: '282px',
        overflow: 'hidden',
        transition: 'border-color 0.16s ease, background 0.16s ease',
      }}
    >
      <CardHeader setup={setup} subScores={subScores} />
      <CardChart chartData={chartData} chartError={chartError} chartContainerRef={chartContainerRef} />
      <CardFooter fwdColor={fwdColor} onLabelChange={onLabelChange} setup={setup} />
      <TagRow
        flags={{
          phaseDInner: setup.phase_d_inner === 1,
          rTouchVolZ: setup.r_touch_vol_z,
          sTouchVolZ: setup.s_touch_vol_z,
        }}
        style={{
          background: 'var(--bg-main)',
          borderTop: '1px solid var(--border-color)',
          flexWrap: 'nowrap',
          height: '28px',
          overflow: 'hidden',
          padding: '4px 8px',
        }}
        compact
        maxTags="auto"
        subScores={subScores}
      />
    </div>
  );
});

function CardHeader({ setup, subScores }) {
  return (
    <div style={{
      alignItems: 'center',
      background: 'rgba(20, 23, 33, 0.98)',
      borderBottom: '1px solid rgba(255,255,255,0.055)',
      display: 'flex',
      gap: '8px',
      justifyContent: 'space-between',
      minHeight: '34px',
      overflow: 'hidden',
      padding: '5px 8px',
    }}>
      <div style={{ alignItems: 'baseline', display: 'flex', gap: '8px', minWidth: 0 }}>
        <span style={{ color: tierColor(setup.tier), fontSize: '17px', fontWeight: '850', lineHeight: 1 }}>{setup.ticker}</span>
        <span style={{ color: 'var(--text-muted)', fontSize: '10px' }}>{setup.scan_date}</span>
      </div>
      <div className="screener-card-score-meta">
        <div style={{ alignItems: 'center', color: 'var(--text-main)', display: 'flex', fontSize: '10px', gap: '6px', justifyContent: 'flex-end' }}>
          <span style={{ background: 'rgba(255,255,255,0.05)', borderRadius: '8px', padding: '1px 6px', whiteSpace: 'nowrap' }}>{setup.tier}</span>
          <span style={{ whiteSpace: 'nowrap' }}>{setup.score?.toFixed(1)}</span>
        </div>
        <ScoreBreakdownPills subScores={subScores} />
      </div>
    </div>
  );
}

function CardChart({ chartContainerRef, chartData, chartError }) {
  if (chartError) return <ChartPlaceholder text="Chart failed to load" />;
  if (!chartData) return <ChartPlaceholder text="Loading chart..." />;
  return <div ref={chartContainerRef} style={{ flex: 1, minHeight: '150px', pointerEvents: 'none', position: 'relative' }} />;
}

function ChartPlaceholder({ text }) {
  return (
    <div style={{
      alignItems: 'center',
      color: 'var(--text-muted)',
      display: 'flex',
      flex: 1,
      fontSize: '11px',
      justifyContent: 'center',
    }}>
      {text}
    </div>
  );
}

function CardFooter({ fwdColor, onLabelChange, setup }) {
  return (
    <div style={{
      alignItems: 'center',
      background: 'var(--bg-main)',
      borderTop: '1px solid var(--border-color)',
      color: 'var(--text-muted)',
      display: 'flex',
      fontSize: '10px',
      gap: '8px',
      justifyContent: 'space-between',
      padding: '6px 8px',
    }}>
      <span style={{ alignItems: 'center', display: 'flex', gap: '8px' }}>
        <span>{setup.setup_type}</span>
        <span>-</span>
        <span>20d: <span style={{ color: fwdColor, fontWeight: 600 }}>{pct(setup.fwd_return_20d)}</span></span>
        {setup.triggered === 1 && <span style={{ color: 'var(--success)' }}>Yes</span>}
        {setup.triggered === 0 && <span style={{ color: 'var(--text-muted)' }}>No</span>}
      </span>
      <select
        onChange={event => onLabelChange(setup.id, event.target.value || null)}
        onClick={event => event.stopPropagation()}
        style={{
          background: 'var(--bg-main)',
          border: '1px solid var(--border-color)',
          borderRadius: '4px',
          color: labelColor(setup.quality_label),
          cursor: 'pointer',
          fontFamily: 'inherit',
          fontSize: '10px',
          padding: '2px 4px',
        }}
        value={setup.quality_label || ''}
      >
        <option value="">-</option>
        {QUALITY_LABELS.map(label => <option key={label} value={label}>{label}</option>)}
      </select>
    </div>
  );
}

export default ArchiveCard;
