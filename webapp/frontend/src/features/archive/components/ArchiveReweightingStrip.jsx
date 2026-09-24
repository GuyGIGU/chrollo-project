import { fixed } from '../presentation/archiveTabUtils';

export default function ArchiveReweightingStrip({ basis, data }) {
  if (!data || data.length === 0) return null;
  const totalCurrent = data.reduce((sum, row) => sum + (Number(row.current) || 0), 0);
  const totalSuggested = data.reduce((sum, row) => sum + (Number(row.suggested) || 0), 0);

  return (
    <div className="glass-panel instrument-tile">
      <div style={{ fontSize: '13px', fontWeight: 600, marginBottom: '4px' }}>Suggested Re-weighting</div>
      <div style={{ color: 'var(--text-muted)', fontSize: '10px', marginBottom: '12px' }}>
        Basis: {basisLabel(basis)}, renormalized to preserve total cap ({fixed(totalCurrent, 0)} pts).
        Read-only - edit config/settings.py manually if applying.
      </div>
      <table style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '11px', width: '100%' }}>
        <thead>
          <tr style={{ borderBottom: '1px solid var(--border-color)', color: 'var(--text-muted)' }}>
            <TableHead>Sub-score</TableHead>
            <TableHead align="right">Current</TableHead>
            <TableHead align="right">Suggested</TableHead>
            <TableHead align="right">Delta</TableHead>
            <TableHead align="right">|corr|</TableHead>
          </tr>
        </thead>
        <tbody>
          {data.map(row => <WeightRow key={row.name} row={row} />)}
          <tr style={{ borderTop: '1px solid var(--border-color)' }}>
            <td style={cellStyle}>Total</td>
            <td style={rightCellStyle}>{fixed(totalCurrent, 0)}</td>
            <td style={rightCellStyle}>{fixed(totalSuggested, 1)}</td>
            <td colSpan={2} />
          </tr>
        </tbody>
      </table>
    </div>
  );
}

function WeightRow({ row }) {
  return (
    <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.03)' }}>
      <td style={{ ...cellStyle, textTransform: 'capitalize' }}>{row.name.replace(/_/g, ' ')}</td>
      <td style={rightCellStyle}>{fixed(row.current, 0)}</td>
      <td style={rightCellStyle}>{fixed(row.suggested, 1)}</td>
      <td style={{ ...rightCellStyle, color: deltaColor(row.delta), fontWeight: 600 }}>
        {row.delta > 0 ? '+' : ''}{fixed(row.delta, 1)}
      </td>
      <td style={{ ...rightCellStyle, color: 'var(--text-muted)' }}>{fixed(row.avg_abs_corr, 3)}</td>
    </tr>
  );
}

function TableHead({ align = 'left', children }) {
  return <th style={{ padding: '4px 6px', textAlign: align }}>{children}</th>;
}

const cellStyle = { color: 'var(--text-muted)', padding: '4px 6px' };
const rightCellStyle = { ...cellStyle, textAlign: 'right' };
const deltaColor = (value) => (value > 0.5 ? '#ff8c00' : value < -0.5 ? 'var(--accent-blue)' : 'var(--text-muted)');
const basisLabel = (basis) => {
  if (basis === '20d+60d_avg') return 'avg |corr| across 20d + 60d horizons';
  if (basis === '20d_only') return '20d |corr| only (60d sample too small)';
  return 'insufficient data';
};
