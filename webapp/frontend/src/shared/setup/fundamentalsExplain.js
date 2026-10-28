// What every part of the fundamentals sheet means and how the scan measured it
// (Wed 28/10/2026, his "add explanations on everything on the fundamental side to
// remind how this works"). Hover text only. Every cut point is quoted from the
// rules the grade carries (core/fundamentals/grade.py `rules`, the knobs in
// config/enrichment.py), never kept here (EC-28); a sheet from before the rules
// rode the wire is explained without the numbers.

const pct = (x) => `${Math.round(x * 100)}%`;
const rulesOf = (sheet) => sheet?.grade?.rules || null;
// How many reports and quarters the sheet holds, in words when the rules say it.
const lastN = (sheet) => (rulesOf(sheet)?.reports ? `last ${rulesOf(sheet).reports}` : 'last');

export const gradeExplain = (sheet) => {
  const r = rulesOf(sheet);
  const cuts = r
    ? `${r.letters.map(([floor, letter]) => `${letter} = ${pct(floor)}+`).join(', ')}, D = less. Fewer than ${r.min_checks} checks with data: no letter.`
    : 'A is the most passed, D the least; too few checks with data gives no letter.';
  return 'The fundamental grade: the business, graded apart from the chart. It never fires, blocks or ranks a setup. '
    + `The letter is the share of the nine checks that passed, counted only over the checks with data, so a missing figure never counts against the stock. ${cuts}`;
};

export const labelExplain = (sheet) => {
  const r = rulesOf(sheet);
  const strong = r
    ? `latest EPS up ${pct(r.eps_growth_min)}+ and sales up ${pct(r.sales_growth_min)}+ on the year, the operating margin held`
    : 'big EPS and sales growth on the year, the operating margin held';
  return 'A one-word read of the business, the first that fits: '
    + 'Accelerating growth = EPS growth rising three quarters running, and sales growth too (on the year, or on the quarter); '
    + `Strong growth = ${strong}; `
    + 'Turnaround = a loss turned to profit or narrowed, or a negative margin improving; '
    + 'otherwise Mixed / insufficient data.';
};

export const CODE33_EXPLAIN = "Minervini's Code 33: EPS growth, sales growth and the net margin each rising three quarters in a row, every figure known. Unknown when any of the nine figures is missing; never given on two good quarters.";

export const NEXT_REPORT_EXPLAIN = 'The next earnings report. "Confirmed" means the company has announced the date; "estimate" is the data provider\'s guess. A setup that breaks out just before a report can gap either way on the news.';

export const WHO_EXPLAIN = 'The company, its sector and industry, and its market value (cap).';

export const sectionExplain = (sheet) => ({
  checks: 'The nine checks the grade rests on, each passed (✓), failed (✗) or not known (–, no data), with the figure it was read from under it. Grouped by what they read; hover a check for how it is measured.',
  reports: `The ${lastN(sheet)} earnings reports, each against the same quarter a year earlier, the estimate, and how the stock traded on it.`,
  quarters: `The ${lastN(sheet)} fiscal quarters from the income statement.`,
  read: 'The lines the checks do not show on their own: where growth is heading, the estimates, and the quality of the earnings.',
});

export const GROUP_EXPLAIN = 'Checks passed out of the checks with data in this box. A check with no data (–) counts neither way.';

export const checkExplain = (sheet) => {
  const r = rulesOf(sheet);
  const m = r?.reaction;
  return {
    eps_growth: "The latest report's adjusted EPS (the figure analysts estimate) against the same quarter a year earlier. O'Neil's C: current earnings growth.",
    eps_accel: "Is the growth itself speeding up: the latest report's growth on the year against the report before it.",
    eps_steady: `Every one of the ${lastN(sheet)} reports up on the year, each against the same quarter a year earlier. Steady growth, not one good quarter.`,
    sales_growth: 'Sales from the income statement, the latest quarter against the same quarter a year earlier (the SEC filings fill the year-ago quarter when the statement no longer has it). Also passes when quarter-on-quarter growth rose three quarters running.',
    margins: 'Operating income as a share of sales, the latest quarter against the same quarter a year earlier. A business earning more on each dollar of sales.',
    beats: r
      ? `Reported EPS against the analysts' estimate on each of the ${lastN(sheet)} reports. Passes on ${r.beats_min}+ beats, the latest report one of them.`
      : "Reported EPS against the analysts' estimate on each of the last reports. Passes on the number of beats the check names, the latest report one of them.",
    estimates: "This year's EPS estimate now against 90 days ago, and how many analysts raised or cut it in the last 30 days. Passes when the estimate went up and raises are at least the cuts.",
    reaction: m
      ? `The market's verdict: the first trading day on each report, its move measured in daily ranges (the move divided by the ${m.adr_days}-day ADR before it) and its volume against the ${m.volume_days}-day average. Passes when one report closed up ${m.ranges}+ ranges on ${m.volume}x+ volume.`
      : "The market's verdict: the first trading day on each report, its move measured in daily ranges (the move divided by the ADR before it) and its volume against its average. Passes when one report closed up by the ranges, on the volume, the check names.",
    quality: 'Passes when none of the earnings-quality flags is raised (see Flags in the read).',
  };
};

export const REPORT_COLUMNS = {
  report: 'The day the company reported (dd/mm/yy), oldest first, the latest at the bottom.',
  eps: 'Adjusted EPS, the per-share profit figure analysts estimate (not the GAAP figure).',
  yoy: 'EPS against the same quarter a year earlier. Off a loss a percentage misleads, so it is said in words (loss → profit, loss narrowed, loss widened).',
  surprise: "Reported EPS against the analysts' estimate: beat or missed, by how much.",
  move: 'How the stock closed on the first trading day on the report, against the close before. Hover a figure for its daily ranges and volume.',
};

export const QUARTER_COLUMNS = {
  quarter: 'The fiscal quarter, by the month it ended. A quarter shows from the day it was reported, never before.',
  sales: 'Revenue for the quarter.',
  yoy: 'Sales against the same quarter a year earlier (hover for where the year-ago figure came from).',
  qoq: 'Sales against the quarter before.',
  margin: 'Operating income as a share of sales.',
  gaap: 'GAAP diluted EPS from the income statement, beside the adjusted figure above. Hover for its change on the year.',
};

export const lineExplain = (k, sheet) => {
  const f = rulesOf(sheet)?.flags;
  switch (k) {
    case 'Trend':
      return 'Each over its last three quarters: speeding up = rising each quarter, slowing = falling each quarter, mixed = neither. For the margin: expanding / shrinking.';
    case 'Estimates':
      return "This year's and next year's EPS estimate now against 90 days ago, and the analysts who raised or cut this year's estimate in the last 30 days. A snapshot of tonight, with no history behind it.";
    case 'Quality':
      return 'Operating cash flow against net income over the shown quarters (profits should arrive as cash), and stock-based pay as a share of sales.';
    case 'Flags':
      return 'Earnings-quality concerns: profits not backed by cash; '
        + (f
          ? `stock pay over ${pct(f.stock_pay_share)} of sales; one-time items worth ${pct(f.one_time_share)}+ of the latest net income; share count down ${pct(f.share_drop)}+ on the year (buybacks lift EPS); acquisitions worth ${pct(f.acquisition_share)}+ of sales.`
          : 'heavy stock pay; large one-time items; a shrinking share count (buybacks lift EPS); large acquisitions.');
    case 'Code 33':
      return CODE33_EXPLAIN;
    default:
      return undefined;
  }
};
