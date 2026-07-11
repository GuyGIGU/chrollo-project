import { CHART_COLORS, CHART_FONT } from './chartTheme';

// Saved calibration marks for the loaded ticker (Task 12/13): the editable
// ground truth, listed dense and mono — click a row to load it into the
// draft (Save becomes a revision-bumping update), × hard-deletes (EC-9: the
// operator owns this population). Color doctrine: committed box marks wear
// the reserved operator hue; NEGATIVES ARE NEUTRAL, never danger-red — a
// no-structure verdict is information, not an alarm.
const fx = (v, d) => ((v == null || !Number.isFinite(Number(v))) ? '—' : Number(v).toFixed(d));

function CalibrationMarksList({ marks, editingId, onEdit, onDelete }) {
  if (!marks.length) return null;
  return (
    <div style={{ maxHeight: 96, overflowY: 'auto', fontSize: 11,
                  fontFamily: CHART_FONT, fontVariantNumeric: 'tabular-nums' }}>
      {marks.map((mark) => (
        <div key={mark.id}
             style={{ display: 'flex', gap: 8, alignItems: 'center',
                      padding: '1px 0' }}>
          <button type="button" onClick={() => onEdit(mark)}
                  title="Load this mark for correction (bumps revision on save)"
                  aria-pressed={editingId === mark.id}>
            {editingId === mark.id ? '✎' : '↥'}
          </button>
          <span style={{ whiteSpace: 'nowrap',
                         color: mark.verdict === 'box'
                           ? CHART_COLORS.operator : 'var(--text-muted)' }}>
            #{mark.id} {mark.as_of_date}{mark.label ? ` · ${mark.label}` : ''} · {mark.verdict}
            {mark.verdict === 'box'
              && ` · R ${fx(mark.resistance, 2)} / S ${fx(mark.support, 2)}`
              + ` · ${mark.box_start_date} → ${mark.box_end_date}`}
            {mark.events?.length > 0 && ` · ${mark.events.length} event(s)`}
            {` · rev ${mark.revision}`}
          </span>
          <button type="button" aria-label={`delete mark ${mark.id}`}
                  onClick={() => onDelete(mark.id)} title="Hard delete">
            ×
          </button>
        </div>
      ))}
    </div>
  );
}

export default CalibrationMarksList;
