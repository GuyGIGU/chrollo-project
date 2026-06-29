// Small shared formatters for the Home command-center. Edge figures arrive as
// FRACTIONS (0.0728 = 7.28%); render them as percents WITHOUT re-deriving the
// underlying number — format only, so the tile never drifts from the source.

export const pct = (frac, digits = 1) => (
  frac == null || !Number.isFinite(Number(frac))
    ? null
    : `${(Number(frac) * 100).toFixed(digits)}%`
);

export const signedPct = (frac, digits = 1) => {
  if (frac == null || !Number.isFinite(Number(frac))) return null;
  const v = Number(frac) * 100;
  return `${v >= 0 ? '+' : '−'}${Math.abs(v).toFixed(digits)}%`;
};
