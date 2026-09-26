export default function TradeTablePager({ currentPage, pageCount, pageEnd, pageStart, totalTrades, onPageChange }) {
  if (pageCount <= 1) return null;

  return (
    <div className="table-pager">
      <span>
        Showing {pageStart + 1}-{pageEnd} of {totalTrades}
      </span>
      <div className="pager-actions">
        <button type="button" onClick={() => onPageChange(1)} disabled={currentPage === 1}>First</button>
        <button type="button" onClick={() => onPageChange(currentPage - 1)} disabled={currentPage === 1}>Previous</button>
        <span>Page {currentPage} of {pageCount}</span>
        <button type="button" onClick={() => onPageChange(currentPage + 1)} disabled={currentPage === pageCount}>Next</button>
        <button type="button" onClick={() => onPageChange(pageCount)} disabled={currentPage === pageCount}>Last</button>
      </div>
    </div>
  );
}
