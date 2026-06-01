export const SUB_SCORE_CAPS = {
  box_tightness: 15,
  touch_density: 25,
  oscillation: 5,
  atr_squeeze: 8,
  lps_tightness: 20,
  vol_contraction: 20,
  base_age: 35,
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

const scoreValue = (subScores, key) => {
  const value = Number(subScores?.[key]);
  return Number.isFinite(value) ? Math.max(0, Math.min(value, SUB_SCORE_CAPS[key] || value)) : 0;
};

const scoreBucket = (subScores, keys) => {
  const cap = keys.reduce((sum, key) => sum + (SUB_SCORE_CAPS[key] || 0), 0);
  const raw = keys.reduce((sum, key) => sum + scoreValue(subScores, key), 0);
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
      fusion: null,
    };
  }

  const visual = scoreBucket(subScores, VISUAL_SCORE_KEYS);
  const market = scoreBucket(subScores, MARKET_SCORE_KEYS);
  const hasBoth = visual.score != null && market.score != null;

  return {
    visual,
    market,
    fusion: hasBoth ? Math.round(Math.sqrt(visual.score * market.score)) : null,
  };
}

