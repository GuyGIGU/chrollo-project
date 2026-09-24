import { fmtDateShort, fmtInt, fmtMoney } from '../../model/tradeTableUtils';
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
  const riskClass = derived.position > 0 && derived.stopRiskTone ? ` risk-${derived.stopRiskTone}` : '';
  return (
    <>
      <tr className={`trade-row${riskClass}`}>
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
        <EditableCell {...editing} rowId={trade.id} field="stop_loss" displayValue={derived.stopVal != null ? <StopValue derived={derived} /> : ''} rawForEdit={trade.stop_loss} num inputType="number" step="0.01" />
        <EditableCell {...editing} rowId={trade.id} field="quantity" displayValue={derived.openQty != null ? fmtInt(derived.openQty) : ''} rawForEdit={trade.quantity} num inputType="number" />
        <ComputedCell num>{derived.totalWorth != null ? `$${fmtMoney(derived.totalWorth, 0)}` : '—'}</ComputedCell>
        <ComputedCell num divider>{derived.position != null ? fmtInt(derived.position) : '—'}</ComputedCell>
        <ComputedCell num><ExitValue derived={derived} /></ComputedCell>
        <ComputedCell num><PnlValue derived={derived} /></ComputedCell>
        <ComputedCell num>{derived.totalExit != null ? `$${fmtMoney(derived.totalExit, 0)}` : '—'}</ComputedCell>
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
  if (derived.currentExit == null) return '—';
  return (
    <span>
      ${fmtMoney(derived.currentExit)}
      {derived.currentExitSource === 'ibkr' && <span className="sub">IBKR</span>}
      {derived.currentExitSource === 'yf' && <span className="sub">LIVE</span>}
    </span>
  );
}

function StopValue({ derived }) {
  if (derived.stopVal == null) return '';
  const liveStopPct = formatPct(derived.distToStopPct);
  const liveStopR = formatR(derived.rToStop);
  const plannedPct = formatPct(derived.stopPct);
  const liveMeta = derived.position > 0 && liveStopPct && liveStopR
    ? `${liveStopPct} / ${liveStopR}`
    : null;
  const meta = liveMeta || plannedPct;
  return (
    <span className="cell-stack trade-stop-stack">
      <span>${fmtMoney(derived.stopVal)}</span>
      {meta && (
        <span className={`secondary ${derived.stopRiskTone ? `risk-${derived.stopRiskTone}` : ''}`}>
          {meta}
        </span>
      )}
    </span>
  );
}

function PnlValue({ derived }) {
  if (derived.pnl == null) return '—';
  const rValue = formatSignedR(derived.rValue);
  // The Status column already color-codes a CLOSED trade's outcome, so here the
  // P&L just carries the number (its +/- sign shows direction) — coloring it red
  // too would double-signal. An OPEN trade has no outcome in Status, so its live
  // P&L keeps the sign color. Symmetric on purpose: muting only losses would
  // flatter the book, which the honest-instrument rule forbids.
  const outcomeInStatus = derived.status === 'win' || derived.status === 'loss' || derived.status === 'wash';
  const signColor = (v) => (v > 0 ? 'var(--success)' : v < 0 ? 'var(--danger)' : 'var(--text-muted)');
  const color = outcomeInStatus ? 'var(--text-main)' : signColor(derived.pnl);
  const rColor = outcomeInStatus ? 'var(--text-faint)' : signColor(derived.rValue);
  return (
    <span style={{ color, fontWeight: 600 }}>
      {derived.pnl >= 0 ? '+' : '-'}${fmtMoney(Math.abs(derived.pnl))}
      {rValue && (
        <span className="sub" style={{ color: rColor, opacity: 0.85 }}>
          {rValue}
        </span>
      )}
    </span>
  );
}

const formatPct = (value) => {
  if (value == null || !Number.isFinite(Number(value))) return null;
  return `${Number(value).toFixed(1)}%`;
};

const formatR = (value) => {
  if (value == null || !Number.isFinite(Number(value))) return null;
  return `${Number(value).toFixed(2)}R`;
};

const formatSignedR = (value) => {
  if (value == null || !Number.isFinite(Number(value))) return null;
  return `${Number(value) >= 0 ? '+' : ''}${Number(value).toFixed(2)}R`;
};
