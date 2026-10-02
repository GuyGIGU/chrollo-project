// The save group of the calibration marking loop (Task 12): label, note, Save
// (POST, or PUT when editing a saved mark), the duplicate-collision resolve,
// and one status line. It opens the band's second row (operator ask
// 2026-10-02: two rows, not five), so nothing in it may wrap: the note shrinks
// and the status line ellipsizes instead — the band height never changes mid-
// mark. Dumb strip — all state in the parent.
function CalibrationSaveBar({
  disabled, canSave, saving, editingId,
  label, onLabel,
  note, onNote,
  onSave, onNewMark,
  conflict, onResolveConflict,
  saveError, tally, needs = [],
}) {
  // A blind save creates; only an explicitly-loaded edit (editingId) updates
  // in place. A duplicate collision is resolved by the operator's deliberate
  // click on "Update existing", never inferred (adversarial review 2026-07-12).
  const updating = editingId != null;
  const status = saveStatus({ disabled, canSave, saveError, tally, needs });
  return (
    <div className="ccb-group ccb-save">
      <input
        value={label}
        onChange={(e) => onLabel(e.target.value)}
        placeholder="label (optional)"
        aria-label="Mark label"
        disabled={disabled}
        style={{ width: 110, fontFamily: 'inherit' }}
      />
      {/* The per-setup annotation (operator ask 2026-07-21): why the engine
          might miss this setup / what would make it hit. Saved on the mark's
          note column, shown back in the rail (✎), and read when the engine is
          measured against the mark. Shrinks (never wraps) when the row is tight. */}
      <input
        className="ccb-note"
        value={note ?? ''}
        onChange={(e) => onNote(e.target.value)}
        placeholder="why it might miss / what would make it hit (optional)"
        aria-label="Setup note — why the engine might miss it or what would make it hit"
        title="Attached to this setup. Shown in the rail (✎) and read when the engine is measured against your mark."
        disabled={disabled}
        maxLength={500}
      />
      <button type="button" disabled={disabled || !canSave || saving} onClick={onSave}
              title={updating
                ? `Update mark #${editingId} (bumps revision) [Enter]`
                : 'Save a new mark [Enter]'}>
        {saving ? 'Saving…' : updating ? `Update #${editingId}` : 'Save'}
      </button>
      {editingId && (
        <button type="button" disabled={disabled} onClick={onNewMark}
                title="Stop editing — the next save creates a new mark">
          New
        </button>
      )}
      {conflict && (
        // A create collided with an existing mark for this frame + label. The
        // overwrite is the operator's explicit one click, never automatic.
        <button type="button" disabled={saving} onClick={onResolveConflict}
                title={`Overwrite the existing mark #${conflict.existingId} with what's drawn (bumps revision)`}
                style={{ borderColor: 'var(--accent-yellow)' }}>
          Update existing #{conflict.existingId}
        </button>
      )}

      {/* ONE status line — a failed save, else what's still needed to save (a
          disabled Save is never a silent dead-end), else "ready"; the sitting
          tally rides after it. Single line, ellipsized, full text on hover. */}
      {status.length > 0 && (
        <span className="ccb-status" title={status.map((s) => s.text).join(' · ')}>
          {status.map((s, i) => (
            <span key={s.text} style={{ color: s.color }}>{i > 0 ? ' · ' : ''}{s.text}</span>
          ))}
        </span>
      )}
    </div>
  );
}

// The status line's parts, in reading order. A failed save leads (red, and the
// ellipsis cuts from the end); then amber while incomplete, or a faint "ready"
// once it isn't.
function saveStatus({ disabled, canSave, saveError, tally, needs }) {
  if (disabled) return [];
  const parts = [];
  if (saveError) {
    parts.push({ text: `✗ ${saveError.class}: ${saveError.message}`, color: 'var(--danger)' });
  }
  if (needs.length) {
    parts.push({ text: `needs ${needs.join(' · ')}`, color: 'var(--warning)' });
  } else if (canSave && !saveError) {
    parts.push({ text: 'ready to save', color: 'var(--text-faint)' });
  }
  if (tally > 0 && !saveError) {
    parts.push({ text: `${tally} saved this sitting`, color: 'var(--text-faint)' });
  }
  return parts;
}

export default CalibrationSaveBar;
