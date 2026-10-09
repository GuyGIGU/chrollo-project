// The leadership read (operator go-ahead 2026-10-02): the STOCK, kept apart from
// the setup's grade. Every value arrives measured from the scan; this module only
// labels and formats it (EC-28: no threshold, no judgment re-declared here).
import { EMPTY, finiteOrNull, fmtMoneyCompact, fmtSignedPctFrac } from '../formatting/format.js';

// Shown on IBD's 1-99 scale; the wire carries the raw 0-100 percentile.
export const rsLabel = (value) => {
  const n = finiteOrNull(value);
  return n == null ? EMPTY : String(Math.min(99, Math.max(1, Math.round(n))));
};

// Minervini's trend template has seven criteria; the wire carries how many pass.
export const trendTemplateLabel = (count) => {
  const n = finiteOrNull(count);
  return n == null ? EMPTY : `${n}/7`;
};

const NOT_GRADED = 'It describes the stock, not the setup, and never changes the grade or the tier.';

// One cell per read: `k` labels the detail grid, `card` is the compact header text.
export const leadershipCells = (data) => {
  const rs = rsLabel(data?.rs_rating);
  const trend = trendTemplateLabel(data?.stage2_trend_pass_count);
  const dollars = fmtMoneyCompact(data?.dollar_volume_50d);
  return [
    {
      k: 'RS rating',
      v: rs,
      card: `RS ${rs}`,
      title: `RS rating ${rs}: the stock's last twelve months, the latest quarter counted double, ranked against every stock Chrollo scans (1-99, higher is stronger). ${NOT_GRADED}`,
    },
    {
      k: 'Trend template',
      v: trend,
      card: trend,
      title: `Trend template ${trend}: how many of Minervini's seven trend criteria pass (moving averages stacked and rising, distance from the 52-week low and high). ${NOT_GRADED}`,
    },
    {
      k: 'Dollar volume',
      v: dollars,
      card: dollars,
      title: `Dollar volume ${dollars}: the average close times volume over the last 50 trading days. Shown only; no liquidity floor is applied.`,
    },
  ];
};

// The wire carries the 200-day average's one-month change already in percent.
export const ma200TrendLabel = (slopePct) => {
  const n = finiteOrNull(slopePct);
  return n == null ? EMPTY : fmtSignedPctFrac(n / 100);
};

// Where the stock stands in its life cycle (go-ahead 2026-10-03): detail panel
// only, the card keeps the three reads above.
export const stageCells = (data) => {
  const offLow = fmtSignedPctFrac(data?.stage2_52w_low_pct, 0);
  const ma200 = ma200TrendLabel(data?.stage2_ma200_slope_1m_pct);
  return [
    {
      k: 'Off 52-week low',
      v: offLow,
      title: `Off 52-week low ${offLow}: how far the price sits above the lowest low of the last 52 weeks (Minervini looks for 25-30% or more before calling a stage 2 advance). ${NOT_GRADED}`,
    },
    {
      k: '200-day trend',
      v: ma200,
      title: `200-day trend ${ma200}: how much the 200-day average moved over the last month (21 trading days); rising is the trend template's third criterion. ${NOT_GRADED}`,
    },
  ];
};

// A payload written before the leadership read existed carries none of it.
export const hasLeadershipRead = (data) =>
  [data?.rs_rating, data?.stage2_trend_pass_count, data?.dollar_volume_50d]
    .some((value) => finiteOrNull(value) != null);
