// The fundamentals read (operator go-ahead 2026-10-03): the BUSINESS, kept apart
// from the setup's grade like the leadership read. Every value arrives measured
// from the scan; this module only labels and formats it (EC-28: no threshold,
// no judgment re-declared here).
import { EMPTY, finiteOrNull, fmtMoneyCompact, fmtSignedPctFrac } from '../formatting/format.js';

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

// "2026-06-30" -> "Jun 2026 quarter". Read off the ISO text, never through
// Date, so no time zone can move a quarter end into the next month.
export const quarterLabel = (iso) => {
  const match = /^(\d{4})-(\d{2})-\d{2}$/.exec(iso || '');
  const month = match ? MONTHS[Number(match[2]) - 1] : null;
  return month ? `${month} ${match[1]} quarter` : null;
};

// Acceleration is one growth rate minus another: percentage POINTS, not percent.
export const accelLabel = (value) => {
  const n = finiteOrNull(value);
  if (n == null) return EMPTY;
  const points = Math.round(n * 100);
  return `${points >= 0 ? '+' : '−'}${Math.abs(points)} pts`;
};

const NOT_GRADED = 'It describes the business, not the setup, and never changes the grade or the tier.';

export const fundamentalsCells = (data) => {
  const quarter = quarterLabel(data?.fund_quarter_end) || 'latest available quarter';
  const cap = fmtMoneyCompact(data?.market_cap);
  const eps = fmtSignedPctFrac(data?.fund_eps_growth_yoy, 0);
  const sales = fmtSignedPctFrac(data?.fund_sales_growth_yoy, 0);
  const accel = accelLabel(data?.fund_eps_growth_accel);
  const surprise = fmtSignedPctFrac(data?.fund_earnings_surprise, 0);
  return [
    {
      k: 'Market cap',
      v: cap,
      title: `Market cap ${cap}: shares outstanding times the price at the scan. Setups under the scan's market-cap floor are left out.`,
    },
    {
      k: 'EPS growth',
      v: eps,
      title: `EPS growth ${eps}: diluted earnings per share of the ${quarter} against the same quarter a year earlier. ${NOT_GRADED}`,
    },
    {
      k: 'Sales growth',
      v: sales,
      title: `Sales growth ${sales}: revenue of the ${quarter} against the same quarter a year earlier. ${NOT_GRADED}`,
    },
    {
      k: 'EPS acceleration',
      v: accel,
      title: `EPS acceleration ${accel}: this quarter's EPS growth minus the previous quarter's (positive = growth speeding up). Needs six quarters of history, which many stocks lack. ${NOT_GRADED}`,
    },
    {
      k: 'Earnings surprise',
      v: surprise,
      title: `Earnings surprise ${surprise}: the last reported EPS against the analysts' estimate. ${NOT_GRADED}`,
    },
  ];
};

// Which quarter the growth numbers describe. A just-reported quarter stays out
// until 75 days after it ends (the filing lag keeps the archive honest), so this
// can trail the latest earnings report by a few weeks.
export const fundamentalsNote = (data) => quarterLabel(data?.fund_quarter_end) || 'the business, not the setup';

// A payload written before the fundamentals went live, or an ETF, carries none.
export const hasFundamentalsRead = (data) =>
  [data?.market_cap, data?.fund_eps_growth_yoy, data?.fund_sales_growth_yoy,
    data?.fund_eps_growth_accel, data?.fund_earnings_surprise]
    .some((value) => finiteOrNull(value) != null);
