import {
  archiveButtonStyle,
  SETUP_TYPES,
  SOURCE_FILTERS,
  SORT_OPTIONS,
  TIERS,
} from '../../utils/archiveTabUtils';

export default function ArchiveFilters({
  filters,
  resetPage,
  setFilters,
}) {
  const setAndReset = (patch) => {
    setFilters(patch);
    resetPage();
  };

  return (
    <div style={{
      alignItems: 'center',
      background: 'var(--bg-panel)',
      border: '1px solid var(--border-color)',
      borderRadius: '8px',
      display: 'flex',
      flexWrap: 'wrap',
      gap: '8px',
      padding: '10px 16px',
    }}>
      <FilterButtons
        label="Source:"
        options={SOURCE_FILTERS}
        value={filters.sourceFilter}
        onChange={sourceFilter => setAndReset({ sourceFilter })}
      />
      <FilterButtons
        label="Tier:"
        options={TIERS.map(tier => [tier, tier === 'ALL' ? 'All' : tier])}
        value={filters.tierFilter}
        onChange={tierFilter => setAndReset({ tierFilter })}
      />
      <FilterButtons
        label="Type:"
        options={SETUP_TYPES.map(type => [type, type === 'ALL' ? 'All' : type])}
        value={filters.typeFilter}
        onChange={typeFilter => setAndReset({ typeFilter })}
      />
      <SortControl filters={filters} setAndReset={setAndReset} />
    </div>
  );
}

function FilterButtons({ label, onChange, options, value }) {
  return (
    <>
      <span style={{ color: 'var(--text-muted)', fontSize: '12px', fontWeight: '500', marginLeft: '8px', marginRight: '4px' }}>
        {label}
      </span>
      {options.map(([key, text]) => (
        <button key={key} onClick={() => onChange(key)} style={archiveButtonStyle(value === key)}>
          {text}
        </button>
      ))}
    </>
  );
}

function SortControl({ filters, setAndReset }) {
  return (
    <>
      <span style={{ color: 'var(--text-muted)', fontSize: '12px', fontWeight: '500', marginLeft: '8px', marginRight: '4px' }}>
        Sort:
      </span>
      <select
        value={filters.sortBy}
        onChange={event => setAndReset({ sortBy: event.target.value })}
        style={{
          background: 'var(--bg-main)',
          border: '1px solid var(--border-color)',
          borderRadius: '8px',
          color: 'var(--text-main)',
          cursor: 'pointer',
          fontFamily: 'inherit',
          fontSize: '12px',
          padding: '5px 10px',
        }}
      >
        {SORT_OPTIONS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
      </select>
      <button
        onClick={() => setAndReset({ sortDir: filters.sortDir === 'asc' ? 'desc' : 'asc' })}
        style={{ ...archiveButtonStyle(false), minWidth: '36px', padding: '5px 10px' }}
        title={filters.sortDir === 'desc' ? 'Descending' : 'Ascending'}
      >
        {filters.sortDir === 'desc' ? 'Down' : 'Up'}
      </button>
      <input
        type="text"
        placeholder="Search ticker..."
        value={filters.searchTerm}
        onChange={event => setAndReset({ searchTerm: event.target.value })}
        style={{
          background: 'var(--bg-main)',
          border: '1px solid var(--border-color)',
          borderRadius: '8px',
          color: 'var(--text-main)',
          fontFamily: 'inherit',
          fontSize: '12px',
          marginLeft: 'auto',
          outline: 'none',
          padding: '5px 14px',
          width: '160px',
        }}
      />
    </>
  );
}
