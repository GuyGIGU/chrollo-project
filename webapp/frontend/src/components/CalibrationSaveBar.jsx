// The save row of the calibration marking loop (Task 12): label, Save (POST, or
// PUT when editing a saved mark), the duplicate-collision resolve, and the
// sitting tally. Dumb strip — all state in the parent.
function CalibrationSaveBar({
  disabled, canSave, saving, editingId,
  label, onLabel,
  onSave, onNewMark,
  conflict, onResolveConflict,
  saveError, tally, needs = [],
}) {
  // A blind save creates; only an explicitly-loaded edit (editingId) updates
  // in place. A duplicate collision is resolved by the operator's deliberate
  // click on "Update existing", never inferred (adversarial review 2026-07-12).
  const updating = editingId != null;
  return (
    // A cohesive, WRAPPING group in the one command band (Task 8).
    <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap',
                  minHeight: 30, fontSize: 12 }}>
      <input
        value={label}
        onChange={(e) => onLabel(e.target.value)}
        placeholder="label (optional)"
        aria-label="Mark label"
        disabled={disabled}
        style={{ width: 110, fontFamily: 'inherit' }}
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

      {/* Always-visible "what's still needed to save" — a disabled Save is never
          a silent dead-end. Amber while incomplete, faint "ready" once it isn't. */}
      {!disabled && (
        <span style={{ fontSize: 11, whiteSpace: 'nowrap',
                       color: needs.length ? 'var(--warning)' : 'var(--text-faint)' }}>
          {needs.length ? `needs ${needs.join(' · ')}` : (canSave ? 'ready to save' : '')}
        </span>
      )}

      {saveError && (
        <span style={{ color: 'var(--danger)', fontSize: 11 }}>
          ✗ {saveError.class}: {saveError.message}
        </span>
      )}
      {tally > 0 && !saveError && (
        <span style={{ color: 'var(--text-faint)' }}>{tally} saved this sitting</span>
      )}
    </div>
  );
}

export default CalibrationSaveBar;
