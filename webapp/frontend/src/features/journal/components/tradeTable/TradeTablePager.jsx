import Pager from '../../../../shared/components/Pager';

// The journal's pager row: the "Showing a-b of n" summary plus the shared Pager.
// No First/Last: the pager's window always shows page 1 and the last page.
export default function TradeTablePager({ currentPage, pageCount, pageEnd, pageStart, totalTrades, onPageChange }) {
  if (pageCount <= 1) return null;

  return (
    <div className="table-pager">
      <span>
        Showing {pageStart + 1}-{pageEnd} of {totalTrades}
      </span>
      <Pager page={currentPage} pageCount={pageCount} onPage={onPageChange} label="Trade pages" />
    </div>
  );
}
