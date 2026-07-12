import { useMemo, useState } from 'react';
import InstrumentTable from './ui/InstrumentTable';
import { buildMarkRows, sortMarkRows } from '../utils/calibrationTables';
import { fx, fmtDateShort, fmtInt } from '../utils/format';
import { confirmDialog } from './ui/feedback';

// Saved calibration marks for the loaded ticker (Task 12/13, ported to the
// shared InstrumentTable): the editable ground truth as a dense, sortable
// ledger. Click a row to load it into the draft (Save becomes a
// revision-bumping update); the × hard-deletes (EC-9: the operator owns this
// population). Color doctrine: committed box marks wear the reserved operator
// hue; NEGATIVES ARE NEUTRAL, never danger-red — a no-structure verdict is
// information, not an alarm. The row being edited carries the active-row cue.
function CalibrationMarksList({ marks, editingId, onEdit, onDelete }) {
  const [sort, setSort] = useState({ by: 'asOf', dir: 'desc' });

  const rows = useMemo(
    () => sortMarkRows(buildMarkRows(marks), sort.by, sort.dir),
    [marks, sort],
  );

  if (!rows.length) return null;

  const onSort = (key) =>
    setSort((current) =>
      current.by === key
        ? { by: key, dir: current.dir === 'asc' ? 'desc' : 'asc' }
        // labels/verdicts read A→Z; ids, dates and numbers read newest/most first.
        : { by: key, dir: key === 'label' || key === 'verdict' ? 'asc' : 'desc' });

  // Committed boxes wear the reserved operator hue via the CSS token (one source
  // of truth with every other operator-purple surface); negatives stay neutral.
  const verdictColor = (row) => (row.isBox ? 'var(--accent-purple)' : 'var(--text-muted)');

  const columns = [
    {
      key: 'edit',
      label: '',
      align: 'center',
      sortable: false,
      // A cue, not a second control: the row itself loads for edit. ✎ marks the
      // one currently in the draft, ↥ hints the rest are loadable.
      render: (row) => (
        <span aria-hidden="true" style={{
          color: editingId === row.id ? 'var(--myth-bright)' : 'var(--text-faint)',
        }}>
          {editingId === row.id ? '✎' : '↥'}
        </span>
      ),
    },
    { key: 'id', label: '#', align: 'right', render: (row) => <span style={{ color: 'var(--text-faint)' }}>{row.id}</span> },
    { key: 'asOf', label: 'As-of', align: 'left', render: (row) => fmtDateShort(row.asOf) },
    {
      key: 'label',
      label: 'Label',
      align: 'left',
      render: (row) => (row.label ? row.label : <span style={{ color: 'var(--text-faint)' }}>—</span>),
    },
    {
      key: 'verdict',
      label: 'Verdict',
      align: 'left',
      render: (row) => <span style={{ color: verdictColor(row) }}>{row.verdict}</span>,
    },
    { key: 'resistance', label: 'R', align: 'right', render: (row) => (row.isBox ? fx(row.resistance, 2) : '—') },
    { key: 'support', label: 'S', align: 'right', render: (row) => (row.isBox ? fx(row.support, 2) : '—') },
    {
      key: 'span',
      label: 'Span',
      align: 'left',
      sortable: false,
      render: (row) => (row.isBox && row.boxStart
        ? <span style={{ color: 'var(--text-muted)' }}>{fmtDateShort(row.boxStart)}→{fmtDateShort(row.boxEnd)}</span>
        : '—'),
    },
    {
      key: 'events',
      label: 'Ev',
      align: 'right',
      render: (row) => (row.events > 0 ? fmtInt(row.events) : <span style={{ color: 'var(--text-faint)' }}>—</span>),
    },
    { key: 'revision', label: 'Rev', align: 'right', render: (row) => <span style={{ color: 'var(--text-faint)' }}>{fmtInt(row.revision)}</span> },
    {
      key: 'delete',
      label: '',
      align: 'center',
      sortable: false,
      render: (row) => (
        <button
          type="button"
          className="row-remove"
          aria-label={`delete mark ${row.id}`}
          title="Hard delete"
          onClick={async (event) => {
            event.stopPropagation();
            // A misclick on a dense scrolling table shouldn't destroy hand-drawn
            // ground truth — one confirm (EC-9 delete stays allowed, just not a
            // hair-trigger).
            const ok = await confirmDialog({
              title: 'Delete this mark?',
              message: `Mark #${row.id} (${row.asOf} · ${row.verdict}) will be `
                + 'permanently deleted — ground truth you drew by hand.',
              confirmLabel: 'Delete',
              cancelLabel: 'Keep',
              danger: true,
            });
            if (ok) onDelete(row.id);
          }}
        >
          ×
        </button>
      ),
    },
  ];

  const ticker = marks[0]?.ticker;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      {/* Caption so the per-ticker marks ledger self-identifies against the
          look-alike coverage table stacked right below it. */}
      <div style={{ color: 'var(--text-faint)', fontSize: 11 }}>
        Marks{ticker ? ` — ${ticker}` : ''} · {rows.length} saved
      </div>
      <InstrumentTable
        columns={columns}
        rows={rows}
        rowKey={(row) => row.id}
        sortBy={sort.by}
        sortDir={sort.dir}
        onSort={onSort}
        onRowClick={(row) => onEdit(row.raw)}
        rowClassName={(row) => (editingId === row.id ? 'active-row' : '')}
        ariaLabel="Saved marks for the loaded ticker"
        maxHeight={168}
      />
    </div>
  );
}

export default CalibrationMarksList;
