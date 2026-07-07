// MetricTile — the shared label / value / sub metric block used by the account
// summary strip and the per-position insight grid. One primitive, two sizes:
//   size="lg" — account summary tiles (bigger value, panel background)
//   size="sm" — position-insight cards (denser, faint white wash)
// The DOM structure is identical across sizes; only the tokens below differ.
// A risk tone signals through the VALUE color, not decorative chrome; callers
// that already computed a concrete color pass it via `color` (wins over tone).
const SIZES = {
  lg: { background: 'var(--bg-panel)', padding: '14px 16px', minHeight: 82, labelWeight: 700, labelMb: 8, valueSize: 20 },
  sm: { background: 'rgba(255,255,255,0.025)', padding: '10px 12px', minHeight: 76, labelWeight: 800, labelMb: 7, valueSize: 15 },
};

const MetricTile = ({ label, value, sub, color, tone = 'default', title, size = 'lg' }) => {
  const s = SIZES[size] || SIZES.lg;
  const valueColor = color || (tone === 'risk' ? 'var(--warning)' : 'var(--text-main)');
  return (
    <div
      style={{
        background: s.background,
        border: '1px solid var(--border-color)',
        borderRadius: 8,
        padding: s.padding,
        minHeight: s.minHeight,
        cursor: title ? 'help' : 'default',
      }}
      title={title}
    >
      <div style={{ color: 'var(--text-muted)', fontSize: 10, fontWeight: s.labelWeight, textTransform: 'uppercase', marginBottom: s.labelMb }}>
        {label}
      </div>
      <div style={{ color: valueColor, fontSize: s.valueSize, fontWeight: 800, lineHeight: 1.1, fontVariantNumeric: 'tabular-nums' }}>
        {value}
      </div>
      {sub && (
        <div style={{ color: 'var(--text-muted)', fontSize: 11, marginTop: 6 }}>
          {sub}
        </div>
      )}
    </div>
  );
};

export default MetricTile;
