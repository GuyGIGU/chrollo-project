// The one loading look (DESIGN.md §5 Loading), promoted from Home's zone
// skeleton: shimmer rows the shape of what is coming, never a bare "Loading…"
// line in a pane that will hold content. Card grids draw `.skeleton-card`
// blocks instead of rows.
export default function Skeleton({ rows = 3, label = 'Loading' }) {
  return (
    <div className="skeleton" role="status" aria-label={label}>
      {Array.from({ length: rows }, (_, i) => <div key={i} className="skeleton-block skeleton-row" />)}
    </div>
  );
}
