import Pager from '../../../shared/components/Pager';
import Skeleton from '../../../shared/components/Skeleton';
import { Cell, HeaderCell } from './ArchiveTable';
import { calibrationResult } from '../model/calibrationList.js';
import {
  ITEMS_PER_PAGE,
  fixed,
  pct,
  rMultipleColor,
  signColor,
} from '../presentation/archiveTabUtils';

// His calibration setups, archived setups too (operator ruling 2026-10-03), each
// measured like a fire from the trading day before his buy. Their own table: the
// engine's columns (tier, score, scans) do not exist for a drawn setup.
const COLUMNS = [
  { key: 'ticker', label: 'Ticker', align: 'left' },
  { key: 'his_trigger_date', label: 'Buy day', align: 'left' },
  { key: 'his_trigger_price', label: 'Trigger', align: 'right', sortable: false },
  { key: '__type', label: 'Type', align: 'left', sortable: false },
  { key: 'mfe_to_date', label: 'Best gain', align: 'right' },
  { key: 'fwd_return_20d', label: '20d', align: 'right' },
  { key: 'r_multiple_20d', label: 'R', align: 'right' },
  { key: '__result', label: 'Result', align: 'left', sortable: false },
  { key: 'days_to_15pct', label: 'Days to +15%', align: 'right' },
  { key: 'bars_to_date', label: 'Days measured', align: 'right', sortable: false },
];

export default function CalibrationSetupsTable({
  currentPage,
  filteredSetups,
  loading,
  onSort,
  pageSetups,
  setCurrentPage,
  sortBy,
  sortDir,
  totalPages,
}) {
  if (loading) return <Skeleton rows={8} label="Loading calibration setups" />;

  if (filteredSetups.length === 0) {
    return (
      <div style={{ color: 'var(--text-muted)', padding: '2rem', textAlign: 'center' }}>
        No calibration setups yet. Draw one in the Calibration tab; its outcome is measured on the next outcome update.
      </div>
    );
  }

  return (
    <>
      <div style={{ color: 'var(--text-muted)', fontSize: '11px' }}>
        {rangeLabel(currentPage, filteredSetups.length)} · measured like the engine's fires from the
        day before your buy, with your support as the stop · compared with the fires, never pooled
      </div>
      <div className="instrument-well" style={{ border: '1px solid var(--border-color)', borderRadius: '8px', overflow: 'hidden' }}>
        <table style={{ borderCollapse: 'collapse', fontSize: '12px', width: '100%' }}>
          <thead>
            <tr>
              {COLUMNS.map(col => (
                <HeaderCell key={col.key} active={sortBy === col.key} col={col} onSort={onSort} sortDir={sortDir} />
              ))}
            </tr>
          </thead>
          <tbody>
            {pageSetups.map(row => <CalibrationRow key={row.mark_id} row={row} />)}
          </tbody>
        </table>
      </div>
      <Pager page={currentPage} pageCount={totalPages} onPage={setCurrentPage} label="Calibration setup pages" />
    </>
  );
}

function CalibrationRow({ row }) {
  const result = calibrationResult(row);
  return (
    <tr
      title={`${row.ticker}: your box from ${row.box_start_date ?? '—'}, support ${fixed(row.support)}, resistance ${fixed(row.resistance)}; measured from ${row.anchor_date ?? '—'}`}
      style={{ borderBottom: '1px solid var(--border-color)' }}
    >
      <Cell align="left"><span style={{ fontWeight: 700 }}>{row.ticker}</span></Cell>
      <Cell align="left" muted>{row.his_trigger_date ?? '—'}</Cell>
      <Cell align="right">{fixed(row.his_trigger_price)}</Cell>
      <Cell align="left">
        <span style={{
          border: '1px solid var(--accent-active)',
          borderRadius: '4px',
          color: 'var(--accent-active)',
          fontSize: '10px',
          fontWeight: 700,
          padding: '1px 6px',
        }}>
          Calibration
        </span>
      </Cell>
      <Cell align="right" color={signColor(row.mfe_to_date)}>{pct(row.mfe_to_date)}</Cell>
      <Cell align="right" color={signColor(row.fwd_return_20d)}>{pct(row.fwd_return_20d)}</Cell>
      <Cell align="right" color={rMultipleColor(row.r_multiple_20d)}>{fixed(row.r_multiple_20d, 2)}</Cell>
      <Cell align="left" muted={!row.barrier_label}>{result}</Cell>
      <Cell align="right">{row.days_to_15pct ?? '—'}</Cell>
      <Cell align="right" muted>{row.bars_to_date ?? '—'}</Cell>
    </tr>
  );
}

const rangeLabel = (currentPage, total) => {
  const start = (currentPage - 1) * ITEMS_PER_PAGE + 1;
  const end = Math.min(currentPage * ITEMS_PER_PAGE, total);
  return `Showing ${start}-${end} of ${total} calibration setups`;
};
