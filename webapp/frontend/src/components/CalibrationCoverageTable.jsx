import { useMemo, useState } from 'react';
import InstrumentTable from './ui/InstrumentTable';
import FrameThumb from './FrameThumb';
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
        <span style={{ display: 'inline-flex', alignItems: 'center' }}>
          <span style={{
            fontWeight: 700,
            color: row.ticker === activeTicker ? 'var(--myth-bright)' : 'var(--text-main)',
          }}>
            {row.ticker}
          </span>
          {/* Completeness: the latest mark here is fully specified (events +
              a knowable-from). Operator-domain state -> operator hue, not
              mythril (interactivity stays scarce) and not green (agreement). */}
          <span
            className={`inst-dot${row.latestComplete ? '' : ' off'}`}
            aria-hidden="true"
            title={row.latestComplete
              ? 'Latest mark fully specified (events + knowable-from)'
              : 'Latest mark not fully specified'}
          />
        </span>
      ),
    },
    {
      // The box share of a ticker's marks — how much committed ground truth it
      // carries — as an operator-hue meter over a neutral track. Keyed on
      // `boxes` so the header sorts by the meter's numerator (the calibration
      // analog of tier weight). The bold count keeps the raw box number visible.
      key: 'boxes',
      label: 'Coverage',
      align: 'left',
      render: (row) => {
        const pct = row.count > 0 ? Math.round((row.boxes / row.count) * 100) : 0;
        return (
          <span className="inst-cov">
            <span className="inst-bar" aria-hidden="true">
              {row.boxes > 0 && <i className="b" style={{ width: `${pct}%` }} />}
              {row.boxes < row.count && <i className="g" style={{ width: `${100 - pct}%` }} />}
            </span>
            <span className="lbl">
              {row.boxes > 0 ? <b>{row.boxes}</b> : row.boxes}/{row.count}
            </span>
          </span>
        );
      },
    },
    { key: 'count', label: 'Marks', align: 'right', render: (row) => fmtInt(row.count) },
    {
      // The ticker's latest marked frame, box drawn — a preview of its ground truth.
      key: 'frame',
      label: 'Frame',
      align: 'left',
      sortable: false,
      render: (row) => (
        <FrameThumb
          ticker={row.ticker}
          asOf={row.latestAsOf}
          digest={row.latestDigest}
          isBox={row.latestIsBox}
          r={row.latestResistance}
          s={row.latestSupport}
          boxStart={row.latestBoxStart}
          boxEnd={row.latestBoxEnd}
        />
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
