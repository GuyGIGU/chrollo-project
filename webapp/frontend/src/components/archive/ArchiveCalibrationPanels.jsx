import { fixed, pct } from '../../utils/archiveTabUtils';

export default function ArchiveCalibrationPanels({ calibration }) {
  if (!calibration) return null;
  return (
    <div style={{ display: 'grid', gap: '16px', gridTemplateColumns: '1fr 1fr' }}>
      <CorrelationPanel calibration={calibration} />
      <BreakdownPanel calibration={calibration} />
    </div>
  );
}

function CorrelationPanel({ calibration }) {
  const keys = Object.keys(calibration.sub_score_correlations_20d || {}).sort((left, right) => {
    const leftScore = correlationStrength(calibration, left);
    const rightScore = correlationStrength(calibration, right);
    return rightScore - leftScore;
  });

  return (
    <div className="glass-panel">
      <div style={panelTitleStyle}>Sub-Score vs Forward Returns (Correlation)</div>
      <div style={{ color: 'var(--text-muted)', fontSize: '10px', marginBottom: '10px' }}>
        n = {calibration.total_with_returns} (20d) - {calibration.total_with_60d_returns} (60d) -
        higher = this component better predicts the horizon
      </div>
      <div style={{ color: 'var(--text-muted)', display: 'flex', fontSize: '10px', gap: '10px', marginBottom: '6px', paddingLeft: '110px' }}>
        <div style={{ flex: 1, paddingLeft: '10px' }}>20d</div>
        <div style={{ flex: 1, paddingLeft: '10px' }}>60d</div>
      </div>
      {keys.map(key => (
        <DualCorrelationBar
          key={key}
          label={key}
          value20={calibration.sub_score_correlations_20d[key]}
          value60={calibration.sub_score_correlations_60d?.[key]}
        />
      ))}
    </div>
  );
}

function BreakdownPanel({ calibration }) {
  return (
    <div className="glass-panel">
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

function DualCorrelationBar({ label, value20, value60 }) {
  return (
    <div style={{ alignItems: 'center', display: 'flex', fontSize: '11px', gap: '10px', marginBottom: '5px' }}>
      <div style={{ color: 'var(--text-muted)', flexShrink: 0, textTransform: 'capitalize', width: '110px' }}>
        {label.replace(/_/g, ' ')}
      </div>
      <CorrelationBar value={value20} />
      <CorrelationBar value={value60} />
    </div>
  );
}

function CorrelationBar({ value }) {
  const numberValue = Number(value);
  const hasValue = value != null && Number.isFinite(numberValue);
  const abs = hasValue ? Math.abs(numberValue) : 0;
  const width = Math.min(abs * 250, 100);
  const positive = hasValue && numberValue >= 0;
  return (
    <div style={{ alignItems: 'center', display: 'flex', flex: 1, gap: '6px' }}>
      <div style={{ background: 'rgba(255,255,255,0.04)', borderRadius: '3px', flex: 1, height: '12px', overflow: 'hidden' }}>
        <div style={{
          background: positive ? 'var(--success)' : 'var(--danger)',
          borderRadius: '3px',
          height: '100%',
          transition: 'width 0.5s ease',
          width: `${width}%`,
        }} />
      </div>
      <div style={{
        color: hasValue ? (positive ? 'var(--success)' : 'var(--danger)') : 'var(--text-muted)',
        fontFamily: "'JetBrains Mono', monospace",
        fontSize: '10px',
        fontWeight: 600,
        textAlign: 'right',
        width: '42px',
      }}>
        {fixed(value, 3)}
      </div>
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

const correlationStrength = (calibration, key) => {
  const corr20 = Math.abs(calibration.sub_score_correlations_20d[key] || 0);
  const corr60 = Math.abs(calibration.sub_score_correlations_60d?.[key] || 0);
  return (corr20 + corr60) / 2;
};
