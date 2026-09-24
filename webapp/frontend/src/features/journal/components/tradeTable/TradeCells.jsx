export const EditableCell = ({
  beginEdit,
  cellDraft,
  displayValue,
  editingCell,
  field,
  handleCellCommit,
  handleCellKey,
  inputType,
  num,
  rawForEdit,
  rowId,
  setCellDraft,
  step,
  sub,
}) => {
  const isEditing = editingCell?.rowId === rowId && editingCell?.field === field;
  const className = ['text', 'cell-editable', num ? 'num' : ''].filter(Boolean).join(' ');

  if (isEditing) {
    return (
      <td className={className}>
        <input
          autoFocus
          className={`cell-input ${num ? 'num' : ''}`}
          type={inputType || 'text'}
          step={step}
          value={cellDraft}
          onBlur={handleCellCommit}
          onChange={(event) => setCellDraft(event.target.value)}
          onKeyDown={handleCellKey}
        />
      </td>
    );
  }

  const valueForEdit = rawForEdit != null ? rawForEdit : displayValue;
  return (
    <td className={className} onClick={() => beginEdit(rowId, field, valueForEdit)}>
      <div className={`cell-shell ${num ? 'num' : ''}`}>
        {displayValue || <span style={{ color: 'var(--text-faint)' }}>-</span>}
        {sub && <span className="sub">{sub}</span>}
      </div>
    </td>
  );
};

export const ComputedCell = ({ center, children, divider, num }) => (
  <td className={['text', 'cell-computed', num ? 'num' : '', divider ? 'col-divider' : ''].filter(Boolean).join(' ')}>
    <div className={`cell-shell readonly ${num ? 'num' : ''} ${center ? 'center' : ''}`}>
      {children}
    </div>
  </td>
);
