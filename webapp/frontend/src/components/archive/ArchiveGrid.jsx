import { ITEMS_PER_PAGE } from '../../utils/archiveTabUtils';
import ArchiveCard from '../ArchiveCard';

export default function ArchiveGrid({
  bulkCharts,
  bulkLoading,
  currentPage,
  filteredSetups,
  onLabelChange,
  onOpenChart,
  pageSetups,
  setCurrentPage,
  totalPages,
}) {
  if (filteredSetups.length === 0) {
    return (
      <div style={{ color: 'var(--text-muted)', padding: '2rem', textAlign: 'center' }}>
        No setups in archive yet. Run a screener scan, seed historical setups, or use + Add Setup above.
      </div>
    );
  }

  return (
    <>
      <div style={{
        alignItems: 'center',
        color: 'var(--text-muted)',
        display: 'flex',
        fontSize: '11px',
        justifyContent: 'space-between',
      }}>
        <span>{rangeLabel(currentPage, filteredSetups.length)}</span>
        {bulkLoading && <span>loading charts...</span>}
      </div>
      <div style={{
        display: 'grid',
        gap: '20px',
        gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))',
      }}>
        {pageSetups.map(setup => (
          <ArchiveCard
            key={setup.id}
            chartData={bulkCharts[setup.id]}
            onClick={onOpenChart}
            onLabelChange={onLabelChange}
            setup={setup}
          />
        ))}
      </div>
      <ArchivePager currentPage={currentPage} setCurrentPage={setCurrentPage} totalPages={totalPages} />
    </>
  );
}

function ArchivePager({ currentPage, setCurrentPage, totalPages }) {
  if (totalPages <= 1) return null;
  return (
    <div style={{ display: 'flex', gap: '8px', justifyContent: 'center', marginBottom: '20px', marginTop: '8px' }}>
      <PagerButton disabled={currentPage === 1} onClick={() => setCurrentPage(page => page - 1)}>
        Prev
      </PagerButton>
      {Array.from({ length: totalPages }, (_, index) => index + 1).map(page => (
        <PagerButton key={page} active={currentPage === page} onClick={() => setCurrentPage(page)}>
          {page}
        </PagerButton>
      ))}
      <PagerButton disabled={currentPage === totalPages} onClick={() => setCurrentPage(page => page + 1)}>
        Next
      </PagerButton>
    </div>
  );
}

function PagerButton({ active, children, disabled, onClick }) {
  return (
    <button
      disabled={disabled}
      onClick={onClick}
      style={{
        background: active ? 'var(--accent-blue)' : 'var(--bg-main)',
        border: '1px solid',
        borderColor: active ? 'var(--accent-blue)' : 'var(--border-color)',
        borderRadius: '6px',
        color: active ? '#fff' : 'var(--text-main)',
        cursor: disabled ? 'not-allowed' : 'pointer',
        fontFamily: 'inherit',
        fontWeight: active ? '600' : '400',
        opacity: disabled ? 0.5 : 1,
        padding: '6px 14px',
      }}
    >
      {children}
    </button>
  );
}

const rangeLabel = (currentPage, total) => {
  const start = (currentPage - 1) * ITEMS_PER_PAGE + 1;
  const end = Math.min(currentPage * ITEMS_PER_PAGE, total);
  return `Showing ${start}-${end} of ${total}`;
};
