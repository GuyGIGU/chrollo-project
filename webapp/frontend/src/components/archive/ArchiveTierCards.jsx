import { fixed, pct, signColor, tierColor } from '../../utils/archiveTabUtils';
import { EMPTY, finiteOrNull } from '../../utils/format';

export default function ArchiveTierCards({ performance }) {
  if (!performance || Object.keys(performance).length === 0) return null;
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '12px' }}>
      {['S', 'A', 'B', 'C', 'D'].map(tier =>
        performance[tier] ? <TierCard key={tier} data={performance[tier]} tier={tier} /> : null)}
    </div>
  );
}

function TierCard({ data, tier }) {
  return (
    <div className="instrument-tile" style={{
      background: 'var(--bg-panel)',
      border: '1px solid var(--border-color)',
      borderRadius: '10px',
      borderTop: `3px solid ${tierColor(tier)}`,
      flex: '1 1 0',
      padding: '16px 20px',
    }}>
      <div style={{ alignItems: 'center', display: 'flex', justifyContent: 'space-between', marginBottom: '12px' }}>
        <span style={{ color: tierColor(tier), fontSize: '18px', fontWeight: '700' }}>{tier} Tier</span>
        <span style={{ color: 'var(--text-muted)', fontSize: '11px' }}>{data.count} setups</span>
      </div>
      <div style={{ display: 'grid', fontSize: '12px', gap: '8px', gridTemplateColumns: '1fr 1fr 1fr' }}>
        <Metric label="Expectancy" value={rValue(data.expectancy_r)} color={signColor(data.expectancy_r)} sub={`n=${data.r_sample_size || 0}`} />
        <Metric label="Avg R 20d" value={rValue(data.avg_r_multiple_20d)} color={signColor(data.avg_r_multiple_20d)} />
        <Metric label="Win Rate" value={pct(data.win_rate)} />
        <Metric label="20d Return" value={pct(data.avg_fwd_20d)} color={signColor(data.avg_fwd_20d)} />
        <Metric label="Trigger Rate" value={pct(data.trigger_rate)} />
        <Metric label="Avg MFE 20d" value={pct(data.avg_mfe_20d)} color="var(--success)" />
      </div>
    </div>
  );
}

function Metric({ color, label, sub, value }) {
  return (
    <div>
      <div style={{ color: 'var(--text-muted)', fontSize: '10px', letterSpacing: '0.5px', textTransform: 'uppercase' }}>{label}</div>
      <div style={{ color: color || 'var(--text-main)', fontWeight: '700' }}>{value}</div>
      {sub && <div style={{ color: 'var(--text-muted)', fontSize: '9px', marginTop: '2px' }}>{sub}</div>}
    </div>
  );
}

// signColor imported from archiveTabUtils. Guard on the VALUE, never on the
// formatter's empty glyph.
const rValue = (value) => (finiteOrNull(value) == null ? EMPTY : `${fixed(value, 2)}R`);
