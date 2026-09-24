// Panel — the app's base surface block: --bg-panel, hairline border, sm radius.
// A dumb presentational wrapper; callers extend via style/className for padding
// and one-off needs. Encodes the surface ramp's "panel" step (DESIGN.md Tonal-
// Depth Rule) so future surfaces compose the ramp instead of re-picking hexes.
const baseStyle = {
  background: 'var(--bg-panel)',
  border: '1px solid var(--border-color)',
  borderRadius: 'var(--radius-sm)',
};

function Panel({ style, className, children, ...rest }) {
  return (
    <div className={className} style={{ ...baseStyle, ...style }} {...rest}>
      {children}
    </div>
  );
}

export default Panel;
