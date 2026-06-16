export const SUB_SCORE_CAPS = {
  box_tightness: 22,
  touch_density: 25,
  oscillation: 5,
  atr_squeeze: 8,
  lps_tightness: 20,
  vol_contraction: 20,
  base_age: 22,
  uptrend_bonus: 15,
  rs_bonus: 15,
  high_proximity: 8,
  breadth_bonus: 8,
  contraction: 12,
  ascending_support: 8,
  adr: 8,
};

const VISUAL_SCORE_KEYS = [
  'box_tightness',
  'touch_density',
  'oscillation',
  'atr_squeeze',
  'lps_tightness',
  'base_age',
  'contraction',
  'ascending_support',
];

const MARKET_SCORE_KEYS = [
  'vol_contraction',
  'uptrend_bonus',
  'rs_bonus',
  'high_proximity',
  'breadth_bonus',
  'adr',
];

// A sub-score is "measured" only if present and finite. Note Number(null) === 0
// (finite!), so we must reject null/undefined explicitly before the finite check
// — otherwise an unmeasured component would masquerade as a genuine 0.
const isMeasured = (subScores, key) => {
  const value = subScores?.[key];
  return value != null && Number.isFinite(Number(value));
};

const scoreValue = (subScores, key) => {
  const value = Number(subScores?.[key]);
  return Number.isFinite(value) ? Math.max(0, Math.min(value, SUB_SCORE_CAPS[key] || value)) : 0;
};

const scoreBucket = (subScores, keys) => {
  // Normalize only over *measured* components. Older archive rows have null for
  // newer sub-scores (adr, contraction, ascending_support); counting their caps
  // in the denominator would unfairly deflate those rows' pills vs. fresh scans.
  const present = keys.filter((key) => isMeasured(subScores, key));
  const cap = present.reduce((sum, key) => sum + (SUB_SCORE_CAPS[key] || 0), 0);
  const raw = present.reduce((sum, key) => sum + scoreValue(subScores, key), 0);
  return {
    raw,
    cap,
    score: cap > 0 ? Math.round((raw / cap) * 100) : null,
  };
};

export function deriveScoreBreakdown(subScores) {
  if (!subScores) {
    return {
      visual: { raw: 0, cap: 0, score: null },
      market: { raw: 0, cap: 0, score: null },
    };
  }

  const visual = scoreBucket(subScores, VISUAL_SCORE_KEYS);
  const market = scoreBucket(subScores, MARKET_SCORE_KEYS);

  return {
    visual,
    market,
  };
}
