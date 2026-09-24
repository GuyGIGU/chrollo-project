// Small shared formatters for the Home command-center. Edge figures arrive as
// FRACTIONS (0.0728 = 7.28%); render them as percents WITHOUT re-deriving the
// underlying number — format only, so the tile never drifts from the source.
// Null in -> null out (the zones own their fallback glyph).

import { fmtPctFrac, fmtSignedPctFrac } from '../../../shared/formatting/format';

export const pct = (frac, digits = 1) => fmtPctFrac(frac, digits, null);

export const signedPct = (frac, digits = 1) => fmtSignedPctFrac(frac, digits, null);
