// The fundamentals sheet and the fundamental grade (operator go-ahead 2026-10-12).
// Every number and every verdict arrives from the scan already decided
// (core/fundamentals/sheet.py and grade.py): each check is passed, failed or not
// known, with its own words. This module only labels and formats (EC-28: no
// threshold, no judgment re-declared here).
import { EMPTY, finiteOrNull, fmtMoneyCompact, fmtSignedPctFrac } from '../formatting/format.js';

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

// "2026-06-30" -> "Jun '26". Read off the ISO text, never through Date.
export const quarterShort = (iso) => {
  const match = /^(\d{4})-(\d{2})-\d{2}$/.exec(iso || '');
  const month = match ? MONTHS[Number(match[2]) - 1] : null;
  return month ? `${month} '${match[1].slice(2)}` : EMPTY;
};

// His date, short: "2026-09-02" -> "02/09/26" (dd/mm/yy), off the ISO text.
export const dayShort = (iso) => {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso || '');
  return match ? `${match[3]}/${match[2]}/${match[1].slice(2)}` : EMPTY;
};

const signed = (value) => fmtSignedPctFrac(value, 0);
const margin = (value) => {
  const n = finiteOrNull(value);
  return n == null ? EMPTY : `${n < 0 ? '−' : ''}${Math.abs(n * 100).toFixed(1)}%`;
};
// The compact money format drops the sign; a loss must read as one.
const money = (value) => {
  const n = finiteOrNull(value);
  return n == null ? EMPTY : `${n < 0 ? '−' : ''}${fmtMoneyCompact(Math.abs(n))}`;
};
const times = (value) => {
  const n = finiteOrNull(value);
  return n == null ? EMPTY : `${n.toFixed(1)}x`;
};
const ranges = (value) => {
  const n = finiteOrNull(value);
  return n == null ? EMPTY : `${n >= 0 ? '+' : '−'}${Math.abs(n).toFixed(1)}`;
};

export const hasFundamentalsSheet = (data) =>
  Boolean(data?.fund_sheet && (data.fund_sheet.eps?.length || data.fund_sheet.quarters?.length));

// The section's note: the letter and how many checks it rests on.
export const gradeNote = (sheet) => {
  const g = sheet?.grade;
  if (!g) return 'the business, not the setup';
  if (!g.letter) return `not enough data (${g.known} of 9 checks)`;
  return `grade ${g.letter}${g.label ? ` · ${g.label}` : ''} · ${g.passed} of ${g.known} checks`;
};

// One row per earnings report, oldest first, with the market's verdict on it.
export const reportRows = (sheet) => {
  const verdicts = new Map((sheet?.reactions || []).map((r) => [r.report_day, r]));
  return (sheet?.eps || []).map((e) => {
    const v = verdicts.get(e.day);
    return {
      key: e.day,
      day: dayShort(e.day),
      eps: finiteOrNull(e.eps) == null ? EMPTY : e.eps.toFixed(2),
      yoy: e.turn || signed(e.yoy),
      yoyTone: growthTone(e.yoy, e.turn),
      surprise: signed(e.surprise),
      beat: finiteOrNull(e.surprise) == null ? null : e.surprise > 0,
      move: v ? signed(v.change) : EMPTY,
      moveTone: v ? signTone(v.change) : undefined,
      moveTitle: v
        ? `Traded on it ${dayShort(v.day)}: ${signed(v.change)}, ${ranges(v.ranges)} daily ranges, on ${times(v.volume_ratio)} the 50-day volume`
        : 'No price data for the report day',
    };
  });
};

// One row per quarter, oldest first.
export const quarterRows = (sheet) => (sheet?.quarters || []).map((q) => ({
  key: q.end,
  quarter: quarterShort(q.end),
  sales: money(q.sales),
  yoy: signed(q.sales_yoy),
  yoyTone: signTone(q.sales_yoy),
  yoyTitle: q.sales_yoy_source === 'sec'
    ? 'The same quarter a year earlier, from the SEC filings'
    : 'The same quarter a year earlier',
  qoq: signed(q.sales_qoq),
  qoqTone: signTone(q.sales_qoq),
  operatingMargin: margin(q.operating_margin),
  marginTone: signTone(q.operating_margin),
  gaap: finiteOrNull(q.eps_gaap) == null ? EMPTY : q.eps_gaap.toFixed(2),
  gaapTitle: `GAAP diluted EPS; on the year: ${q.eps_gaap_turn || signed(q.eps_gaap_yoy)}`,
}));

// The two lines under the tables: estimates and earnings quality.
export const sheetLines = (sheet) => {
  const r = sheet?.revisions || {};
  const q = sheet?.quality || {};
  const t = sheet?.trends || {};
  const moves = r.up_30d == null || r.down_30d == null ? '' : ` · ${r.up_30d} raised / ${r.down_30d} cut in 30 days`;
  const sbc = finiteOrNull(q.sbc_share_of_sales);
  const trendParts = [
    t.eps ? `EPS ${trendWord(t.eps)}` : null,
    t.sales ? `sales ${trendWord(t.sales)}` : t.sales_qoq ? `sales on the quarter ${trendWord(t.sales_qoq)}` : null,
    t.margin ? `margin ${t.margin}` : null,
  ].filter(Boolean);
  const c33 = sheet?.grade?.code33;
  return [
    { k: 'Trend', v: trendParts.length ? trendParts.join(' · ') : EMPTY },
    {
      k: 'Estimates',
      v: finiteOrNull(r.this_year_change_90d) == null
        ? EMPTY
        : `this year ${signed(r.this_year_change_90d)}, next year ${signed(r.next_year_change_90d)} in 90 days${moves}`,
    },
    {
      k: 'Quality',
      v: `cash flow ${money(q.operating_cash_flow)} vs net income ${money(q.net_income)}`
        + (sbc == null ? '' : ` · stock pay ${(sbc * 100).toFixed(0)}% of sales`),
    },
    {
      k: 'Flags',
      v: q.flags_known ? ((q.flags || []).length ? q.flags.join(' · ') : 'none identified') : EMPTY,
      tone: q.flags_known ? ((q.flags || []).length ? CAUTION : UP) : undefined,
    },
    {
      k: 'Code 33',
      v: c33 ? `${c33.met === true ? 'met' : c33.met === false ? 'not met' : 'not known'}: ${c33.why}` : EMPTY,
      tone: c33?.met === true ? UP : undefined,
    },
    { k: 'Next report', v: nextEarningsLine(sheet?.next_earnings) },
  ];
};

// ── Color (2026-10-12, his "more color and style"): tones only, each looked up from a
// sign or a word the scan already decided, never a threshold of our own (EC-28). ──
const UP = 'var(--success)';
const DOWN = 'var(--danger)';
const CAUTION = 'var(--warning)';
const QUIET = 'var(--text-faint)';

// Green up, rose down, nothing for zero or unknown.
export const signTone = (value) => {
  const n = finiteOrNull(value);
  if (n == null || n === 0) return undefined;
  return n > 0 ? UP : DOWN;
};

const TURN_TONES = { 'loss → profit': UP, 'loss narrowed': UP, 'loss widened': DOWN };
const TREND_TONES = { accelerating: UP, expanding: UP, slowing: CAUTION, shrinking: CAUTION, mixed: QUIET };
const LABEL_TONES = {
  'Accelerating growth': UP, 'Strong growth': UP, Turnaround: 'var(--accent-blue)', 'Mixed / insufficient data': QUIET,
};
export const trendTone = (word) => TREND_TONES[word];
export const labelTone = (label) => LABEL_TONES[label] || QUIET;
// A growth figure's tone: the scan's words off a loss, else the sign.
export const growthTone = (growth, words) => (words ? TURN_TONES[words] : signTone(growth));

// "a → b → c", each figure in its own tone, the arrows quiet.
const toneSequence = (items) => items.flatMap((item, i) => (
  i ? [{ t: ' → ', tone: QUIET }, item] : [item]));
const trendPill = (word) => (word ? [{ t: trendWord(word), tone: trendTone(word), pill: true }] : []);

const MARKS = { true: '✓', false: '✗', null: '–' };
const TONES = { true: 'var(--success)', false: 'var(--warning)', null: 'var(--text-faint)' };

// The nine checks as the scan decided them: a mark, the words, and why.
export const checkRows = (sheet) => (sheet?.grade?.checks || []).map((c) => {
  const state = c.passed === true || c.passed === false ? c.passed : null;
  return { key: c.key, state, mark: MARKS[state], tone: TONES[state], label: c.label, why: c.why || '' };
});

// The sheet's three boxes of checks (Wed 28/10/2026, his "this is unreadable"): a
// grouping by the check's key, nothing more. A key the scan adds later lands in
// "Other" rather than vanishing.
const CHECK_GROUPS = [
  { title: 'Earnings', keys: ['eps_growth', 'eps_accel', 'eps_steady', 'beats'] },
  { title: 'Sales and margin', keys: ['sales_growth', 'margins'] },
  { title: 'Analysts and the market', keys: ['estimates', 'reaction', 'quality'] },
];

export const checkGroups = (sheet) => {
  const rows = checkRows(sheet);
  const placed = new Set(CHECK_GROUPS.flatMap((g) => g.keys));
  const groups = [
    ...CHECK_GROUPS.map((g) => ({ title: g.title, rows: g.keys.map((k) => rows.find((r) => r.key === k)).filter(Boolean) })),
    { title: 'Other', rows: rows.filter((r) => !placed.has(r.key)) },
  ];
  return groups.filter((g) => g.rows.length).map((g) => ({
    ...g,
    count: `${g.rows.filter((r) => r.state === true).length} of ${g.rows.filter((r) => r.state != null).length}`,
  }));
};

// ── The card's second page and the sheet's extra lines (second patch, 2026-10-12) ──

// One EPS figure on the year: the growth, or the scan's words when the year-ago
// figure was a loss (a percentage off a loss misleads).
export const epsChange = (growth, words) => (words || signed(growth));

// "a → b → c → d", the empty ones shown as the empty mark.
const sequence = (values) => values.map((v) => v ?? EMPTY).join(' → ');

const TREND_WORDS = { accelerating: 'speeding up', slowing: 'slowing', mixed: 'mixed' };
const trendWord = (value) => (value ? TREND_WORDS[value] || value : null);

export const nextEarningsLine = (next) => {
  if (!next?.day) return EMPTY;
  const state = next.confirmed === true ? 'confirmed' : next.confirmed === false ? 'estimate' : 'not said if confirmed';
  return `${dayShort(next.day)} (${state})`;
};

// The verdict line on top: the letter, the descriptive label, Code 33 when met.
export const cardHeader = (sheet) => {
  const g = sheet?.grade || {};
  const snap = sheet?.snapshot || {};
  const where = [snap.sector, snap.industry].filter(Boolean).join(' · ');
  return {
    letter: g.letter || null,
    label: g.label || 'Mixed / insufficient data',
    labelTone: labelTone(g.label || 'Mixed / insufficient data'),
    checks: g.letter ? `${g.passed} of ${g.known} checks` : null,
    title: g.letter ? `Fundamental grade ${g.letter}: ${g.passed} of ${g.known} checks with data passed` : 'Not enough data for a grade',
    code33: g.code33?.met === true,
    code33Word: g.code33?.met === true ? 'Code 33 met' : g.code33?.met === false ? 'Code 33 not met' : null,
    code33Title: g.code33?.why || '',
    snapshot: where || null,
    snapshotTitle: snap.summary || '',
  };
};

// The compact lines of the card's second page, in his order.
export const cardLines = (sheet) => {
  const eps = sheet?.eps || [];
  const quarters = sheet?.quarters || [];
  const t = sheet?.trends || {};
  const last = eps[eps.length - 1];
  const reaction = (sheet?.reactions || []).find((r) => r.report_day === last?.day);
  const salesKnown = quarters.filter((q) => finiteOrNull(q.sales_yoy) != null).length;
  const useQoq = salesKnown < 2;
  const first = quarters[quarters.length - 1] || {};
  const flags = sheet?.quality?.flags || [];
  const r = sheet?.revisions || {};
  const lines = [
    {
      k: 'EPS y/y',
      v: `${sequence(eps.map((e) => (e.turn || finiteOrNull(e.yoy) != null ? epsChange(e.yoy, e.turn) : null)))}`
        + (trendWord(t.eps) ? ` · ${trendWord(t.eps)}` : ''),
      parts: [
        ...toneSequence(eps.map((e) => (e.turn || finiteOrNull(e.yoy) != null
          ? { t: epsChange(e.yoy, e.turn), tone: growthTone(e.yoy, e.turn) }
          : { t: EMPTY, tone: QUIET }))),
        ...trendPill(t.eps),
      ],
      title: 'Adjusted EPS, the figure the analysts estimate, each report against the same quarter a year earlier',
    },
    useQoq
      ? {
        k: 'Sales q/q',
        v: sequence(quarters.map((q) => (finiteOrNull(q.sales_qoq) == null ? null : signed(q.sales_qoq))))
          + (trendWord(t.sales_qoq) ? ` · ${trendWord(t.sales_qoq)}` : ''),
        parts: [...toneSequence(quarters.map((q) => ({ t: signed(q.sales_qoq), tone: signTone(q.sales_qoq) }))), ...trendPill(t.sales_qoq)],
        title: 'Sales on the quarter before: too few year-ago quarters to compare on the year',
      }
      : {
        k: 'Sales y/y',
        v: sequence(quarters.map((q) => (finiteOrNull(q.sales_yoy) == null ? null : signed(q.sales_yoy))))
          + (trendWord(t.sales) ? ` · ${trendWord(t.sales)}` : ''),
        parts: [...toneSequence(quarters.map((q) => ({ t: signed(q.sales_yoy), tone: signTone(q.sales_yoy) }))), ...trendPill(t.sales)],
        title: 'Each quarter against the same quarter a year earlier',
      },
    {
      k: 'Op. margin',
      v: finiteOrNull(first.operating_margin) == null
        ? EMPTY
        : `${margin(first.operating_margin_year_ago)} → ${margin(first.operating_margin)}`
          + (t.margin ? ` · ${t.margin}` : ''),
      parts: finiteOrNull(first.operating_margin) == null ? null : [
        ...toneSequence([first.operating_margin_year_ago, first.operating_margin].map((m) => ({ t: margin(m), tone: signTone(m) }))),
        ...trendPill(t.margin),
      ],
      title: 'The latest quarter against the same quarter a year earlier; the word reads the last three quarters',
    },
    {
      k: 'Last report',
      v: last
        ? `${finiteOrNull(last.surprise) == null ? 'no estimate' : `${last.surprise > 0 ? 'beat' : 'missed'} ${signed(last.surprise)}`}`
          + (reaction ? ` · traded ${signed(reaction.change)} on ${times(reaction.volume_ratio)} vol` : '')
        : EMPTY,
      tone: last && finiteOrNull(last.surprise) != null ? (last.surprise > 0 ? 'var(--success)' : 'var(--warning)') : undefined,
      parts: last ? [
        finiteOrNull(last.surprise) == null
          ? { t: 'no estimate', tone: QUIET, pill: true }
          : { t: `${last.surprise > 0 ? 'beat' : 'missed'} ${signed(last.surprise)}`, tone: last.surprise > 0 ? UP : CAUTION, pill: true },
        ...(reaction ? [
          { t: ' traded ' },
          { t: signed(reaction.change), tone: signTone(reaction.change), strong: true },
          { t: ' on ' },
          { t: times(reaction.volume_ratio), strong: true },
          { t: ' vol' },
        ] : []),
      ] : null,
    },
    {
      k: 'Estimates',
      v: finiteOrNull(r.this_year_change_90d) == null
        ? EMPTY
        : `${signed(r.this_year_change_90d)} in 90 days`
          + (r.up_30d == null || r.down_30d == null ? '' : ` · ${r.up_30d} up / ${r.down_30d} down`),
      parts: finiteOrNull(r.this_year_change_90d) == null ? null : [
        { t: signed(r.this_year_change_90d), tone: signTone(r.this_year_change_90d), strong: true },
        { t: ' in 90 days' },
        ...(r.up_30d == null || r.down_30d == null ? [] : [
          { t: ' · ', tone: QUIET },
          { t: `${r.up_30d} up`, tone: r.up_30d ? UP : QUIET },
          { t: ' / ', tone: QUIET },
          { t: `${r.down_30d} down`, tone: r.down_30d ? DOWN : QUIET },
        ]),
      ],
      title: "This year's EPS estimate now against 90 days ago; analysts raising against cutting over 30 days",
    },
    {
      k: 'Quality',
      v: sheet?.quality?.flags_known ? (flags.length ? flags.join(' · ') : 'none identified') : EMPTY,
      tone: flags.length ? 'var(--warning)' : undefined,
      parts: !sheet?.quality?.flags_known ? null : flags.length
        ? flags.map((f) => ({ t: f, tone: CAUTION, pill: true }))
        : [{ t: '✓ none identified', tone: UP }],
    },
    {
      k: 'Next report',
      v: nextEarningsLine(sheet?.next_earnings),
      parts: sheet?.next_earnings?.day ? [
        { t: dayShort(sheet.next_earnings.day), strong: true },
        sheet.next_earnings.confirmed === true
          ? { t: 'confirmed', tone: 'var(--text-main)', pill: true }
          : { t: sheet.next_earnings.confirmed === false ? 'estimate' : 'not said', tone: QUIET, pill: true },
      ] : null,
    },
  ];
  return lines;
};
