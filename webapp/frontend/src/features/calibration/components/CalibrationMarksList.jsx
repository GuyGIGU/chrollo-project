import { useMemo, useState } from 'react';
import InstrumentTable from '../../../shared/components/InstrumentTable';
import FrameThumb from './FrameThumb';
import { buildMarkRows, sortMarkRows } from '../model/calibrationTables';
import { fx, fmtDateShort, fmtInt } from '../../../shared/formatting/format';
import { confirmDialog } from '../../../shared/components/feedback';

// Saved calibration marks for the loaded ticker (Task 12/13, ported to the
// shared InstrumentTable): the editable ground truth as a dense, sortable
// ledger. Click a row to load it into the draft (Save becomes a
// revision-bumping update); the × hard-deletes (EC-9: the operator owns this
// population). Color doctrine: committed box marks wear the reserved operator
// hue; NEGATIVES ARE NEUTRAL, never danger-red — a no-structure verdict is
// information, not an alarm. The row being edited carries the active-row cue.
// Engine chip — the operator's calibration read on a mark: the FIRED-in-window
// verdict once it computes (green `fired · tier · Δ`, or red `missed · <state
// word>` — the reader's own word on his day, with its box and its reason in the
// title); a neutral dash while it computes. Green/red live ONLY here (engine
// agreement); untested / negatives stay neutral.
const KIND_TITLE = {
  fired: 'This pick would have surfaced on the nightly screener in-window',
  missed: "No fire in the fair window — the reader's own reason",
  unassessable: 'No faithful basis to replay the fair window (thin frame / engine error)',
  negative: 'A negative mark — no box for the engine to surface',
  error: 'The engine read failed for this mark',
  other: 'Untested',
};

function chipTitle(chip) {
  // Open enum: an unknown kind (a newer harness vocabulary than this build)
  // stays visible — surface the raw server value, never hide it behind a dash.
  let title = KIND_TITLE[chip.kind] || (chip.kind ? `Server verdict: ${chip.kind}` : 'Untested');
  if (chip.detail) title += ` · ${chip.detail}`; // the reader's words: its box, then why no LPS
  if (chip.stale) title += ' · engine changed since this mark was made';
  return title;
}

const railDelta = (chip) => (Number.isFinite(chip.rail_delta) ? ` · Δ${chip.rail_delta.toFixed(2)}` : '');

function firedLabel(chip) {
  if (chip.state === 'ok') return `fired${chip.tier ? ` · ${chip.tier}` : ''}${railDelta(chip)}`;
  if (chip.state === 'miss') return `missed${chip.stage ? ` · ${chip.stage}` : ''}`;
  return 'untested';
}

function EngineChip({ fired }) {
  // The fired verdict once it lands; a neutral dash before it — never a false red.
  if (fired && (fired.state === 'ok' || fired.state === 'miss')) {
    return <span className={`inst-chip ${fired.state}`} title={chipTitle(fired)}>{firedLabel(fired)}</span>;
  }
  if (fired && fired.state === 'untested') {
    return <span className="inst-chip untested" title={chipTitle(fired)}>untested</span>;
  }
  if (fired && fired.state && fired.state !== 'pending') {
    // Unknown state from a newer grading vocabulary: render NEUTRAL with the
    // raw value visible — never a false green/red, never an info-free dash.
    return <span className="inst-chip untested" title={chipTitle(fired)}>{String(fired.state)}</span>;
  }
  return <span style={{ color: 'var(--text-faint)' }}>—</span>;
}

function CalibrationMarksList({ marks, editingId, fired, onEdit, onDelete }) {
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
    {
      // The exact frozen frame with this mark's box drawn — scan without loading.
      key: 'frame',
      label: 'Frame',
      align: 'left',
      sortable: false,
      render: (row) => (
        <FrameThumb
          ticker={row.raw?.ticker}
          asOf={row.asOf}
          digest={row.frameDigest}
          isBox={row.isBox}
          r={row.resistance}
          s={row.support}
          boxStart={row.boxStart}
          boxEnd={row.boxEnd}
        />
      ),
    },
    { key: 'asOf', label: 'As-of', align: 'left', render: (row) => fmtDateShort(row.asOf) },
    {
      key: 'label',
      label: 'Label',
      align: 'left',
      render: (row) => (row.label ? row.label : <span style={{ color: 'var(--text-faint)' }}>—</span>),
    },
    {
      // Committed boxes wear the reserved operator hue; NEGATIVES ARE NEUTRAL,
      // never danger-red — a no-structure verdict is information, not an alarm.
      key: 'verdict',
      label: 'Verdict',
      align: 'left',
      render: (row) => (
        <span className={`inst-pill ${row.isBox ? 'box' : 'neg'}`}>{row.verdict}</span>
      ),
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
      // Would this pick fire on the nightly screener? Not sortable — the engine
      // maps fill in asynchronously and independently of the row order.
      key: 'engine',
      label: 'Engine',
      align: 'left',
      sortable: false,
      render: (row) => <EngineChip fired={fired?.[row.id]} />,
    },
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
      {/* Legend for the Engine column — the fired-in-window grade. */}
      <div style={{
        display: 'flex', flexWrap: 'wrap', gap: '6px 14px', alignItems: 'center',
        color: 'var(--text-faint)', fontSize: 11,
      }}>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
          <span className="inst-chip ok">fired · S</span> would have surfaced in-window (tier · Δ rail gap)
        </span>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
          <span className="inst-chip miss">missed · lines, no LPS yet</span> no fire; the reader's word on his day
        </span>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
          <span className="inst-chip untested">untested</span> negative, or no basis to replay
        </span>
      </div>
    </div>
  );
}

export default CalibrationMarksList;
