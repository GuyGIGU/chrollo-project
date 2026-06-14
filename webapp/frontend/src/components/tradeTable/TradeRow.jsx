import { fmtDateShort, fmtInt, fmtMoney } from '../../utils/tradeTableUtils';
import { ComputedCell, EditableCell } from './TradeCells';
import FillsRow from './FillsRow';

export default function TradeRow({
  derived,
  editing,
  fills,
  fillsActions,
  isExpanded,
  onDetailClick,
  onToggleExpand,
  onToggleSide,
  trade,
}) {
  return (
    <>
      <tr className="trade-row">
        <td className="text">
          <div className="cell-shell readonly center">
            <span
              className={`expand-chev ${isExpanded ? 'open' : ''}`}
              onClick={() => onToggleExpand(trade.id)}
              title="Show fills"
            >
              &gt;
            </span>
          </div>
        </td>
        <EditableCell {...editing} rowId={trade.id} field="opening_date" displayValue={fmtDateShort(trade.opening_date)} rawForEdit={trade.opening_date} inputType="date" />
        <EditableCell {...editing} rowId={trade.id} field="ticker" displayValue={<span className="symbol-cell">{trade.ticker}</span>} rawForEdit={trade.ticker} />
        <ComputedCell><span className={`status-cell ${derived.status}`}>{derived.status}</span></ComputedCell>
        <td className="text cell-editable">
          <div className="cell-shell center" onClick={() => onToggleSide(trade)}>
            <span className={`side-arrow ${derived.isLong ? 'long' : 'short'}`}>{derived.isLong ? 'L' : 'S'}</span>
          </div>
        </td>
        <EditableCell {...editing} rowId={trade.id} field="entry_price" displayValue={derived.entryVwap != null ? `$${fmtMoney(derived.entryVwap)}` : ''} rawForEdit={trade.entry_price} num inputType="number" step="0.01" />
        <EditableCell {...editing} rowId={trade.id} field="stop_loss" displayValue={derived.stopVal != null ? `$${fmtMoney(derived.stopVal)}` : ''} rawForEdit={trade.stop_loss} sub={derived.stopPct != null ? `${derived.stopPct.toFixed(1)}%` : null} num inputType="number" step="0.01" />
        <EditableCell {...editing} rowId={trade.id} field="quantity" displayValue={derived.openQty != null ? fmtInt(derived.openQty) : ''} rawForEdit={trade.quantity} num inputType="number" />
        <ComputedCell num>{derived.totalWorth != null ? `$${fmtMoney(derived.totalWorth, 0)}` : '-'}</ComputedCell>
        <ComputedCell num divider>{derived.position != null ? fmtInt(derived.position) : '-'}</ComputedCell>
        <ComputedCell num><ExitValue derived={derived} /></ComputedCell>
        <ComputedCell num><PnlValue derived={derived} /></ComputedCell>
        <ComputedCell num>{derived.totalExit != null ? `$${fmtMoney(derived.totalExit, 0)}` : '-'}</ComputedCell>
        <ComputedCell>{fmtDateShort(derived.exitDate)}</ComputedCell>
        <td className="text" style={{ cursor: 'pointer' }} onClick={() => onDetailClick?.(trade)} title="Open detail drawer">
          <div className="cell-shell readonly center" style={{ color: 'var(--text-muted)', letterSpacing: '2px' }}>...</div>
        </td>
      </tr>
      {isExpanded && (
        <FillsRow
          {...fillsActions}
          fills={fills}
          onSave={() => fillsActions.saveFills(trade)}
          trade={trade}
        />
      )}
    </>
  );
}

function ExitValue({ derived }) {
  if (derived.currentExit == null) return '-';
  return (
    <span>
      ${fmtMoney(derived.currentExit)}
      {derived.currentExitSource === 'ibkr' && <span className="sub">IBKR</span>}
      {derived.currentExitSource === 'yf' && <span className="sub">LIVE</span>}
    </span>
  );
}

function PnlValue({ derived }) {
  if (derived.pnl == null) return '-';
  const color = derived.pnl > 0
    ? 'var(--success)'
    : derived.pnl < 0 ? 'var(--danger)' : 'var(--text-muted)';
  return (
    <span style={{ color, fontWeight: 600 }}>
      {derived.pnl >= 0 ? '+' : '-'}${fmtMoney(Math.abs(derived.pnl))}
      {derived.rValue != null && (
        <span
          className="sub"
          style={{
            color: derived.rValue > 0
              ? 'var(--success)'
              : derived.rValue < 0 ? 'var(--danger)' : 'var(--text-faint)',
            opacity: 0.85,
          }}
        >
          {derived.rValue >= 0 ? '+' : ''}{derived.rValue.toFixed(2)}R
        </span>
      )}
    </span>
  );
}
