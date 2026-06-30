import { useEffect, useMemo, useState } from 'react';
import useTradeCellEditing from '../hooks/useTradeCellEditing';
import useTradeFills from '../hooks/useTradeFills';
import { DEFAULT_PAGE_SIZE, deriveTradeRow } from '../utils/tradeTableUtils';
import DraftTradeRow from './tradeTable/DraftTradeRow';
import TradeRow from './tradeTable/TradeRow';
import TradeTablePager from './tradeTable/TradeTablePager';

const COLUMNS = [
  30, 80, 88, 86, 54, 92, 110, 78, 108, 80, 118, 130, 108, 86, 38,
];

export default function TradeTable({
  draftRow,
  onDetailClick,
  onTradeUpdate,
  pageSize = DEFAULT_PAGE_SIZE,
  riskFor,
  setDraftRow,
  trades = [],
}) {
  const [currentPage, setCurrentPage] = useState(1);
  // Open rows come from the server (live overlay); closed/draft rows fall back to
  // the price-independent client derivation. `riskFor` already encodes both.
  const getRisk = riskFor || deriveTradeRow;
  const pageCount = Math.max(1, Math.ceil(trades.length / pageSize));
  const pageStart = (currentPage - 1) * pageSize;
  const pageEnd = Math.min(pageStart + pageSize, trades.length);
  const pageTrades = useMemo(
    () => trades.slice(pageStart, pageStart + pageSize),
    [pageSize, pageStart, trades],
  );
  const editing = useTradeCellEditing({ draftRow, onTradeUpdate, setDraftRow, trades });
  const fills = useTradeFills({
    commitTradeCell: editing.commitTradeCell,
    onTradeUpdate,
    trades,
  });

  useEffect(() => {
    setCurrentPage(page => Math.min(Math.max(page, 1), pageCount));
  }, [pageCount]);

  useEffect(() => {
    if (draftRow) setCurrentPage(1);
  }, [draftRow]);

  const goToPage = (page) => {
    setCurrentPage(Math.min(Math.max(page, 1), pageCount));
  };

  return (
    <div className="trade-table-wrap">
      <div className="trade-table-scroll">
        <table className="trade-table">
          <colgroup>
            {COLUMNS.map((width, index) => <col key={index} style={{ width }} />)}
          </colgroup>
          <thead>
            <tr className="group-row">
              <th colSpan={9}>Plan</th>
              <th colSpan={6} className="group-execution">Execution</th>
            </tr>
            <tr className="col-row">
              <th />
              <th>Date</th>
              <th>Symbol</th>
              <th>Status</th>
              <th>Side</th>
              <th className="num">Entry</th>
              <th className="num">Stop</th>
              <th className="num">Qty</th>
              <th className="num">Total $</th>
              <th className="num col-divider">Pos</th>
              <th className="num">Current/Exit</th>
              <th className="num">P&amp;L</th>
              <th className="num">Total Exit</th>
              <th>Exit Date</th>
              <th />
            </tr>
          </thead>
          <tbody>
            <DraftTradeRow
              draftRow={draftRow}
              editing={editing}
              onCancel={editing.cancelDraft}
              onToggleSide={editing.toggleDraftSide}
            />
            {pageTrades.map(trade => (
              <TradeRow
                key={trade.id}
                derived={getRisk(trade)}
                editing={editing}
                fills={fills.fillsBuffer[trade.id] || []}
                fillsActions={fills}
                isExpanded={fills.expandedFills.has(trade.id)}
                onDetailClick={onDetailClick}
                onToggleExpand={fills.toggleExpand}
                onToggleSide={editing.toggleSide}
                trade={trade}
              />
            ))}
          </tbody>
        </table>
      </div>

      <TradeTablePager
        currentPage={currentPage}
        onPageChange={goToPage}
        pageCount={pageCount}
        pageEnd={pageEnd}
        pageStart={pageStart}
        totalTrades={trades.length}
      />

      {trades.length === 0 && !draftRow && <EmptyTradeTable />}
    </div>
  );
}

function EmptyTradeTable() {
  return (
    <div style={{
      background: 'var(--bg-panel)',
      border: '1px solid var(--border-color)',
      borderRadius: 'var(--radius-md)',
      color: 'var(--text-muted)',
      fontSize: '12px',
      margin: '3rem auto',
      padding: '2rem',
      textAlign: 'center',
      width: '50%',
    }}>
      No trades to display. Click <strong style={{ color: 'var(--text-main)' }}>+ New Trade</strong> to add one,
      or import an IBKR Activity Statement.
    </div>
  );
}
