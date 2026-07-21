// The save row of the calibration marking loop (Task 12): label/note, Save
// (POST, or PUT when editing a saved mark), the one-keystroke negatives, the
// worklist queue, and the sitting tally. Dumb strip — all state in the parent.
function CalibrationSaveBar({
  disabled, canSave, saving, editingId,
  label, onLabel, note, onNote,
  onSave, onNewMark, onNegative,
  conflict, onResolveConflict,
  saveError, tally, needs = [],
  worklist, worklistLabelText, onWorklistText, onWorklistStep,
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
      <input
        value={note}
        onChange={(e) => onNote(e.target.value)}
        placeholder="note"
        aria-label="Mark note"
        disabled={disabled}
        style={{ width: 170, fontFamily: 'inherit' }}
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
      <button type="button" disabled={disabled || saving}
              onClick={() => onNegative('no_structure')}
              title="Save a no-structure mark for this frame [n]">
        No structure
      </button>
      <button type="button" disabled={disabled || saving}
              onClick={() => onNegative('engine_wrong')}
              title="Save an engine-wrong mark for this frame [w]">
        Engine wrong
      </button>

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

      <span style={{ marginLeft: 'auto', display: 'flex', gap: 6, alignItems: 'center' }}>
        {/* A textarea (one row tall) — a single-line input silently strips
            the newlines out of a pasted list, and nothing parses. */}
        <textarea
          rows={1}
          placeholder="worklist: TICKER YYYY-MM-DD per line (or ;-separated)"
          aria-label="Worklist"
          onChange={(e) => onWorklistText(e.target.value)}
          style={{ width: 220, fontFamily: 'inherit', resize: 'none' }}
        />
        {worklist.length > 0 && (
          <>
            <button type="button" onClick={() => onWorklistStep(-1)} title="Previous worklist entry">◀</button>
            <span style={{ color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>{worklistLabelText}</span>
            <button type="button" onClick={() => onWorklistStep(1)} title="Next worklist entry">▶</button>
          </>
        )}
      </span>
    </div>
  );
}

export default CalibrationSaveBar;
