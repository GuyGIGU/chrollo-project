import { test } from 'node:test';
import assert from 'node:assert/strict';
import { EMPTY } from '../formatting/format.js';
import {
  cardHeader, cardLines, checkRows, dayShort, epsChange, gradeNote, nextEarningsLine, hasFundamentalsSheet, quarterRows, quarterShort, reportRows, sheetLines,
} from './fundamentalsSheetRead.js';

const SHEET = {
  eps: [
    { day: '2026-05-27', eps: 0.39, yoy: 0.625, surprise: 0.2195 },
    { day: '2026-09-02', eps: 0.62, yoy: 0.771, surprise: -0.04 },
  ],
  quarters: [
    { end: '2026-04-30', sales: 1391000000, sales_yoy: 0.3, sales_yoy_source: 'sec', sales_qoq: 0.083, operating_margin: -0.234 },
    { end: '2026-07-31', sales: 1547000000, sales_yoy: 0.351, sales_yoy_source: 'yahoo', sales_qoq: 0.112, operating_margin: -0.17 },
  ],
  reactions: [{ report_day: '2026-09-02', day: '2026-09-03', change: 0.166, ranges: 4.2, volume_ratio: 4.2 }],
  revisions: { this_year_change_90d: 0.15, next_year_change_90d: 0.12, up_30d: 43, down_30d: 1 },
  quality: { operating_cash_flow: 1253000000, net_income: -1091000000, sbc_share_of_sales: 0.302,
    flags: ['stock pay 30% of sales'], flags_known: true },
  trends: { eps: 'accelerating', sales: null, sales_qoq: 'accelerating', margin: 'expanding' },
  snapshot: { name: 'Snowflake Inc.', sector: 'Technology', industry: 'Software - Application', summary: 'Snowflake Inc. provides a cloud data platform.' },
  next_earnings: { day: '2026-12-02', confirmed: false },
  grade: {
    letter: 'A', passed: 8, known: 9, label: 'Accelerating growth',
    code33: { met: null, why: 'not enough comparable history: sales growth' },
    checks: [
      { key: 'eps_growth', label: 'EPS up 25%+ on the year', passed: true, why: 'latest report +77%' },
      { key: 'quality', label: 'No earnings-quality concern', passed: false, why: 'stock pay 30% of sales' },
      { key: 'eps_steady', label: 'EPS up on the year in each of the last four reports', passed: null, why: 'needs 4' },
    ],
  },
};

test('quarterShort: month and two-digit year off the ISO text', () => {
  assert.equal(quarterShort('2026-07-31'), "Jul '26");
  assert.equal(quarterShort('nope'), EMPTY);
});

test('dayShort: dd/mm/yy off the ISO text', () => {
  assert.equal(dayShort('2026-09-02'), '02/09/26');
  assert.equal(dayShort(null), EMPTY);
});

test('gradeNote: the letter and the checks it rests on, or why there is none', () => {
  assert.equal(gradeNote(SHEET), 'grade A · Accelerating growth · 8 of 9 checks');
  assert.equal(gradeNote({ grade: { letter: null, known: 3 } }), 'not enough data (3 of 9 checks)');
  assert.equal(gradeNote(null), 'the business, not the setup');
});

test('reportRows: each report with its growth, its beat and the market verdict on it', () => {
  const rows = reportRows(SHEET);
  assert.deepEqual(rows.map((r) => [r.day, r.eps, r.yoy, r.surprise, r.beat, r.move]),
    [['27/05/26', '0.39', '+63%', '+22%', true, EMPTY], ['02/09/26', '0.62', '+77%', '−4%', false, '+17%']]);
  assert.match(rows[1].moveTitle, /4\.2 daily ranges, on 4\.2x the 50-day volume/);
});

test('quarterRows: sales, growth on the year and on the quarter, the margin; the SEC source named', () => {
  const rows = quarterRows(SHEET);
  assert.deepEqual(rows.map((r) => [r.quarter, r.sales, r.yoy, r.qoq, r.operatingMargin]),
    [["Apr '26", '$1.4B', '+30%', '+8%', '−23.4%'], ["Jul '26", '$1.5B', '+35%', '+11%', '−17.0%']]);
  assert.match(rows[0].yoyTitle, /SEC/);
  assert.doesNotMatch(rows[1].yoyTitle, /SEC/);
});

test('sheetLines: estimates and quality in words; a missing estimate reads empty', () => {
  const lines = Object.fromEntries(sheetLines(SHEET).map((l) => [l.k, l]));
  const { Estimates: estimates, Quality: quality } = lines;
  assert.equal(estimates.v, 'this year +15%, next year +12% in 90 days · 43 raised / 1 cut in 30 days');
  assert.equal(quality.v, 'cash flow $1.3B vs net income −$1.1B · stock pay 30% of sales');
  assert.equal(lines.Flags.v, 'stock pay 30% of sales');
  assert.equal(lines['Code 33'].v, 'not known: not enough comparable history: sales growth');
  assert.equal(lines['Next report'].v, '02/12/26 (estimate)');
  assert.equal(lines.Trend.v, 'EPS speeding up · sales on the quarter speeding up · margin expanding');
  assert.deepEqual(sheetLines({}).map((l) => l.v).filter((v) => v !== EMPTY && !v.startsWith('cash flow')), []);
});

test('checkRows: the scan decides, the panel marks: passed, failed, not known', () => {
  assert.deepEqual(checkRows(SHEET).map((c) => c.mark), ['✓', '✗', '–']);
  assert.deepEqual(checkRows({}), []);
});

test('hasFundamentalsSheet: only a payload that carries reports or quarters', () => {
  assert.equal(hasFundamentalsSheet({ fund_sheet: SHEET }), true);
  assert.equal(hasFundamentalsSheet({ fund_sheet: { eps: [], quarters: [] } }), false);
  assert.equal(hasFundamentalsSheet({}), false);
});

test('epsChange: words off a loss, the growth otherwise', () => {
  assert.equal(epsChange(0.42, null), '+42%');
  assert.equal(epsChange(null, 'loss → profit'), 'loss → profit');
  assert.equal(epsChange(null, null), EMPTY);
});

test('nextEarningsLine: the day and whether it is confirmed', () => {
  assert.equal(nextEarningsLine({ day: '2026-11-03', confirmed: true }), '03/11/26 (confirmed)');
  assert.equal(nextEarningsLine({ day: '2026-11-03', confirmed: null }), '03/11/26 (not said if confirmed)');
  assert.equal(nextEarningsLine(null), EMPTY);
});

test('cardHeader: letter, label, Code 33 only when met, sector and industry', () => {
  const head = cardHeader(SHEET);
  assert.equal(head.letter, 'A');
  assert.equal(head.label, 'Accelerating growth');
  assert.equal(head.code33, false);
  assert.equal(head.snapshot, 'Technology · Software - Application');
  assert.equal(cardHeader({ grade: { code33: { met: true, why: 'x' } } }).code33, true);
  assert.equal(cardHeader({}).label, 'Mixed / insufficient data');
});

test('cardLines: the compact page, sales on the quarter when the year-ago quarters are missing', () => {
  const lines = Object.fromEntries(cardLines(SHEET).map((l) => [l.k, l.v]));
  assert.equal(lines['EPS y/y'], '+63% → +77% · speeding up');
  assert.equal(lines['Sales y/y'], '+30% → +35%');
  const noYearAgo = { ...SHEET, quarters: SHEET.quarters.map((q) => ({ ...q, sales_yoy: null })) };
  assert.equal(Object.fromEntries(cardLines(noYearAgo).map((l) => [l.k, l.v]))['Sales q/q'], '+8% → +11% · speeding up');
  assert.equal(lines['Op. margin'], `${EMPTY} → −17.0% · expanding`);
  assert.equal(lines['Last report'], 'missed −4% · traded +17% on 4.2x vol');
  assert.equal(lines.Estimates, '+15% in 90 days · 43 up / 1 down');
  assert.equal(lines.Quality, 'stock pay 30% of sales');
  assert.equal(lines['Next report'], '02/12/26 (estimate)');
  const full = { ...SHEET, quarters: SHEET.quarters.map((q) => ({ ...q, sales_yoy: 0.3 })) };
  assert.ok(cardLines(full).some((l) => l.k === 'Sales y/y'));
  const turned = { eps: [{ day: '2026-01-01', yoy: null, turn: 'loss → profit' }] };
  assert.equal(cardLines(turned)[0].v, 'loss → profit');
});
