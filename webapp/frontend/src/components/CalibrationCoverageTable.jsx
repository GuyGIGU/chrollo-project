import { useMemo, useState } from 'react';
import InstrumentTable from './ui/InstrumentTable';
import { sortCoverageRows } from '../utils/calibrationTables';
import { fmtDateShort, fmtInt } from '../utils/format';

// "What have I calibrated" — every ticker the operator has marked, as a dense
// sortable ledger (the same InstrumentTable the watchlist uses). Replaces the
// old chip strip: a row per ticker with its mark count, how many are committed
// boxes (the real ground truth, in the operator hue) and the latest session
// worked; click a row to reload that ticker at its newest mark. Data is the
// marks hook's coverage summary; sort is controlled here, never in the table.
function CalibrationCoverageTable({ summary, activeTicker, onPick }) {
  const [sort, setSort] = useState({ by: 'latestAsOf', dir: 'desc' });

  const rows = useMemo(
    () => sortCoverageRows(summary ?? [], sort.by, sort.dir),
    [summary, sort],
  );

  // Nothing marked yet -> nothing to show (density: the panel only appears once
  // it carries information), mirroring the strip it replaces.
  if (!rows.length) return null;

  const onSort = (key) =>
    setSort((current) =>
      current.by === key
        ? { by: key, dir: current.dir === 'asc' ? 'desc' : 'asc' }
        // dates + counts read newest/most first; the ticker name reads A→Z.
        : { by: key, dir: key === 'ticker' ? 'asc' : 'desc' });

  const totalMarks = rows.reduce((sum, r) => sum + r.count, 0);

  const columns = [
    {
      key: 'ticker',
      label: 'Ticker',
      align: 'left',
      render: (row) => (
        <span style={{
          fontWeight: 700,
          color: row.ticker === activeTicker ? 'var(--myth-bright)' : 'var(--text-main)',
        }}>
          {row.ticker}
        </span>
      ),
    },
    { key: 'count', label: 'Marks', align: 'right', render: (row) => fmtInt(row.count) },
    {
      key: 'boxes',
      label: 'Box',
      align: 'right',
      render: (row) => (
        <span style={{ color: row.boxes > 0 ? 'var(--accent-purple)' : 'var(--text-faint)' }}>
          {fmtInt(row.boxes)}
        </span>
      ),
    },
    {
      key: 'latestAsOf',
      label: 'Latest',
      align: 'left',
      render: (row) => <span style={{ color: 'var(--text-muted)' }}>{fmtDateShort(row.latestAsOf)}</span>,
    },
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      <div style={{ color: 'var(--text-faint)', fontSize: 11 }}>
        Calibrated — {rows.length} {rows.length === 1 ? 'ticker' : 'tickers'} · {totalMarks} marks
      </div>
      <InstrumentTable
        columns={columns}
        rows={rows}
        rowKey={(row) => row.ticker}
        sortBy={sort.by}
        sortDir={sort.dir}
        onSort={onSort}
        onRowClick={(row) => onPick(row.ticker, row.latestAsOf)}
        rowClassName={(row) => (row.ticker === activeTicker ? 'active-row' : '')}
        ariaLabel="Calibrated tickers"
        maxHeight={168}
      />
    </div>
  );
}

export default CalibrationCoverageTable;
