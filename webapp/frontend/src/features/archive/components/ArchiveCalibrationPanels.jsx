import { pct } from '../presentation/archiveTabUtils';

// The setup-type and market-regime breakdown of the archive's outcomes. The
// sub-score correlation panel that stood beside it left with the old engine
// (retire-old-engine, decision C): the reader scores no sub-scores.
export default function ArchiveCalibrationPanels({ calibration }) {
  if (!calibration) return null;
  return <BreakdownPanel calibration={calibration} />;
}

function BreakdownPanel({ calibration }) {
  return (
    <div className="glass-panel instrument-tile">
      <div style={{ ...panelTitleStyle, marginBottom: '12px' }}>Setup Type Performance</div>
      {calibration.setup_type_breakdown && Object.entries(calibration.setup_type_breakdown).map(([type, data]) => (
        <BreakdownRow
          key={type}
          title={type}
          left={`${data.count} trades`}
          middle={pct(data.avg_fwd_20d)}
          right={`WR: ${pct(data.win_rate)}`}
          value={data.avg_fwd_20d}
        />
      ))}
      <div style={{ ...panelTitleStyle, margin: '16px 0 12px' }}>Market Regime Impact</div>
      {calibration.market_context && Object.entries(calibration.market_context).map(([regime, data]) => (
        <BreakdownRow
          key={regime}
          title={`SPY ${regime}`}
          titleColor={regime === 'BULLISH' ? 'var(--success)' : regime === 'BEARISH' ? 'var(--danger)' : 'var(--text-muted)'}
          left={`${data.count} setups`}
          middle={pct(data.avg_fwd_20d)}
          value={data.avg_fwd_20d}
        />
      ))}
    </div>
  );
}

function BreakdownRow({ left, middle, right, title, titleColor, value }) {
  return (
    <div style={{
      alignItems: 'center',
      background: 'var(--bg-main)',
      border: '1px solid var(--border-color)',
      borderRadius: '6px',
      display: 'flex',
      justifyContent: 'space-between',
      marginBottom: '8px',
      padding: '10px 12px',
    }}>
      <span style={{ color: titleColor || 'var(--text-main)', fontSize: '13px', fontWeight: '600' }}>{title}</span>
      <div style={{ display: 'flex', fontSize: '12px', gap: '16px' }}>
        <span style={{ color: 'var(--text-muted)' }}>{left}</span>
        <span style={{ color: value > 0 ? 'var(--success)' : 'var(--danger)', fontWeight: '600' }}>{middle}</span>
        {right && <span style={{ color: 'var(--text-muted)' }}>{right}</span>}
      </div>
    </div>
  );
}

const panelTitleStyle = {
  color: 'var(--text-main)',
  fontSize: '13px',
  fontWeight: '600',
  marginBottom: '4px',
};
