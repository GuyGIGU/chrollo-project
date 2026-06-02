import { fmtDateShort, fmtInt, fmtMoney } from '../../utils/tradeTableUtils';
import { ComputedCell, EditableCell } from './TradeCells';

export default function DraftTradeRow({ draftRow, editing, onCancel, onToggleSide }) {
  if (!draftRow) return null;
  const rowId = 'draft';
  const isLong = draftRow.direction !== 'SHORT';

  return (
    <tr className="trade-row draft">
      <td className="text">
        <div className="cell-shell readonly center">
          <button
            onClick={onCancel}
            style={{
              background: 'transparent',
              border: 'none',
              color: 'var(--text-faint)',
              cursor: 'pointer',
              fontSize: '13px',
            }}
            title="Discard draft"
          >
            x
          </button>
        </div>
      </td>
      <EditableCell {...editing} rowId={rowId} field="opening_date" displayValue={fmtDateShort(draftRow.opening_date)} rawForEdit={draftRow.opening_date} inputType="date" />
      <EditableCell {...editing} rowId={rowId} field="ticker" displayValue={draftRow.ticker ? <span className="symbol-cell">{draftRow.ticker}</span> : ''} rawForEdit={draftRow.ticker} />
      <ComputedCell><span className="status-cell draft">DRAFT</span></ComputedCell>
      <td className="text cell-editable">
        <div className="cell-shell center" onClick={onToggleSide}>
          <span className={`side-arrow ${isLong ? 'long' : 'short'}`}>{isLong ? 'L' : 'S'}</span>
        </div>
      </td>
      <EditableCell {...editing} rowId={rowId} field="entry_price" displayValue={draftRow.entry_price ? `$${fmtMoney(draftRow.entry_price)}` : ''} rawForEdit={draftRow.entry_price} num inputType="number" step="0.01" />
      <EditableCell {...editing} rowId={rowId} field="stop_loss" displayValue={draftRow.stop_loss ? `$${fmtMoney(draftRow.stop_loss)}` : ''} rawForEdit={draftRow.stop_loss} num inputType="number" step="0.01" />
      <EditableCell {...editing} rowId={rowId} field="quantity" displayValue={draftRow.quantity ? fmtInt(draftRow.quantity) : ''} rawForEdit={draftRow.quantity} num inputType="number" />
      <ComputedCell num>
        {draftRow.entry_price && draftRow.quantity
          ? `$${fmtMoney(Number(draftRow.entry_price) * Number(draftRow.quantity), 0)}`
          : '-'}
      </ComputedCell>
      <ComputedCell num divider>-</ComputedCell>
      <ComputedCell num>-</ComputedCell>
      <ComputedCell num>-</ComputedCell>
      <ComputedCell num>-</ComputedCell>
      <ComputedCell>-</ComputedCell>
      <td className="text"><div className="cell-shell readonly center" /></td>
    </tr>
  );
}
