function ScreenerPager({ currentPage, totalPages, onPageChange }) {
  if (totalPages <= 1) return null;

  return (
    <div style={{ display: 'flex', justifyContent: 'center', gap: '8px', marginTop: '20px', marginBottom: '20px' }}>
      <PagerButton disabled={currentPage === 1} onClick={() => onPageChange(currentPage - 1)}>
        Prev
      </PagerButton>
      {Array.from({ length: totalPages }, (_, index) => index + 1).map(page => (
        <PagerButton
          key={page}
          active={currentPage === page}
          onClick={() => onPageChange(page)}
        >
          {page}
        </PagerButton>
      ))}
      <PagerButton disabled={currentPage === totalPages} onClick={() => onPageChange(currentPage + 1)}>
        Next
      </PagerButton>
    </div>
  );
}

function PagerButton({ active = false, disabled = false, children, onClick }) {
  return (
    <button
      disabled={disabled}
      onClick={onClick}
      style={{
        padding: '6px 14px',
        borderRadius: '6px',
        border: '1px solid',
        borderColor: active ? 'var(--accent-active)' : 'var(--border-color)',
        background: active ? 'var(--accent-active)' : 'var(--bg-main)',
        color: active ? 'var(--myth-ink)' : 'var(--text-main)',
        cursor: disabled ? 'not-allowed' : 'pointer',
        opacity: disabled ? 0.5 : 1,
        fontWeight: active ? '600' : '400',
        fontFamily: 'inherit',
      }}
    >
      {children}
    </button>
  );
}

export default ScreenerPager;
