import { fx, fmtDay } from '../utils/format';

// The watch lane (the final method, point 22): the charts the walk read lines
// on but that have no LPS yet, apart from the leaderboard. Every row arrives
// resolved from the engine (market_context.watch: one state word from one
// table, the rails, the open day, the age, the turns at each rail); the panel
// only lays it out. Absent flag-off (the block is not on the wire), so it
// renders nothing until the method flips.
const cell = { padding: '4px 10px', whiteSpace: 'nowrap' };
const head = { ...cell, color: 'var(--text-faint)', fontSize: 11, fontWeight: 600, textAlign: 'left' };
const mono = { ...cell, fontFamily: "'JetBrains Mono', monospace", fontSize: 12 };

const stateLine = (row) => (row.why ? `${row.state}: ${row.why}` : row.state);

export default function WatchLanePanel({ watch }) {
  const rows = Array.isArray(watch?.candidates) ? watch.candidates : [];
  if (!rows.length) return null;
  const counts = watch.counts || {};
  const summary = Object.entries(counts).map(([state, n]) => `${state} ${n}`).join(' · ');
  return (
    <section
      aria-label="Watch lane"
      style={{
        background: 'var(--bg-panel)',
        border: '1px solid var(--border-color)',
        borderRadius: 'var(--radius-sm)',
        marginTop: 14,
        overflowX: 'auto',
      }}
    >
      <div style={{ alignItems: 'baseline', display: 'flex', gap: 10, padding: '8px 10px 2px' }}>
        <span style={{ color: 'var(--text-main)', fontSize: 13, fontWeight: 700 }}>Watch lane</span>
        <span style={{ color: 'var(--text-faint)', fontSize: 11 }}>
          lines, no LPS yet — {rows.length} charts{summary ? ` (${summary})` : ''}
        </span>
      </div>
      <table style={{ borderCollapse: 'collapse', width: '100%' }}>
        <thead>
          <tr>
            <th style={head}>Ticker</th>
            <th style={head}>State</th>
            <th style={head}>R / S</th>
            <th style={head}>Open</th>
            <th style={head}>Days</th>
            <th style={head}>Turns R / S</th>
            <th style={head}>Close</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.ticker} style={{ borderTop: '1px solid rgba(255,255,255,0.055)' }}>
              <td style={{ ...mono, color: 'var(--text-main)', fontWeight: 700 }}>{row.ticker}</td>
              <td style={{ ...cell, color: 'var(--text-muted)', fontSize: 12 }}>{stateLine(row)}</td>
              <td style={mono}>{fx(row.R, 2)} / {fx(row.S, 2)}</td>
              <td style={mono}>{fmtDay(row.open)}</td>
              <td style={mono}>{fx(row.age, 0)}</td>
              <td style={mono}>{fx(row.turns_at_r, 0)} / {fx(row.turns_at_s, 0)}</td>
              <td style={mono}>{fx(row.close, 2)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
