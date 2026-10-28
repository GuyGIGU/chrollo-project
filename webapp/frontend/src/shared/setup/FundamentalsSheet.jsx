import { fmtMoneyCompact } from '../formatting/format';
import { cardHeader, checkGroups, gradeNote, nextEarningsLine, quarterRows, reportRows, sheetLines } from './fundamentalsSheetRead';
import {
  CHECK_EXPLAIN, CODE33_EXPLAIN, GROUP_EXPLAIN, NEXT_REPORT_EXPLAIN, QUARTER_COLUMNS, REPORT_COLUMNS, SECTION_EXPLAIN,
  WHO_EXPLAIN, gradeExplain, labelExplain, lineExplain,
} from './fundamentalsExplain';

// The grade, who the business is, and the next report where it cannot be missed.
// Every part explains itself on hover (Wed 28/10/2026).
function SheetHead({ sheet, marketCap }) {
  const head = cardHeader(sheet);
  const snap = sheet.snapshot || {};
  const where = [snap.industry, snap.sector, marketCap ? `cap ${fmtMoneyCompact(marketCap)}` : null].filter(Boolean).join(' · ');
  const next = sheet.next_earnings?.day ? nextEarningsLine(sheet.next_earnings) : null;
  return (
    <header className="fund-sheet-head">
      <div className="fund-sheet-verdict" data-grade={head.letter || 'none'}>
        <span className="fund-grade-tile" title={`${head.title}. ${gradeExplain(sheet)}`}>{head.letter || '–'}</span>
        <div className="fund-sheet-verdict-words">
          <span className="fund-sheet-label" title={labelExplain(sheet)}>{head.label}</span>
          <small>
            <span title={gradeExplain(sheet)}>{head.checks ? `${head.checks} passed` : gradeNote(sheet)}</span>
            {head.code33Word ? <> · <span title={`${head.code33Title}. ${CODE33_EXPLAIN}`}>{head.code33Word}</span></> : null}
          </small>
        </div>
        {head.code33 ? <span className="fund-card-badge" title={`${head.code33Title}. ${CODE33_EXPLAIN}`}>Code 33 ✓</span> : null}
      </div>
      <div className="fund-sheet-who">
        {snap.name ? <span className="fund-sheet-name" title={head.snapshotTitle}>{snap.name}</span> : null}
        {where ? <small title={WHO_EXPLAIN}>{where}</small> : null}
        {next ? <span className="fund-sheet-next" title={NEXT_REPORT_EXPLAIN}>Next report {next}</span> : null}
      </div>
    </header>
  );
}

// A check's mark as a small round glyph: passed, failed or not known.
function CheckMark({ state }) {
  const tone = state === true ? 'var(--success)' : state === false ? 'var(--warning)' : 'var(--text-faint)';
  return (
    <svg className="fund-check-mark" width="22" height="22" viewBox="0 0 24 24" aria-hidden="true" style={{ color: tone }}>
      <circle cx="12" cy="12" r="12" fill="currentColor" fillOpacity="0.16" />
      {state === true ? <path d="M7 12.5l3.2 3.2L17 9" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" /> : null}
      {state === false ? <path d="M8.5 8.5l7 7M15.5 8.5l-7 7" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" /> : null}
      {state == null ? <path d="M8 12h8" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" /> : null}
    </svg>
  );
}

// The nine checks the grade rests on, in three boxes, each with its own count.
function SheetChecks({ sheet }) {
  const groups = checkGroups(sheet);
  if (!groups.length) return null;
  return (
    <div className="fund-sheet-block">
      <h3 title={SECTION_EXPLAIN.checks}>The nine checks <small>hover anything on this page for how it is measured</small></h3>
      <div className="fund-check-groups">
        {groups.map((g) => (
          <div key={g.title} className="fund-check-group">
            <div className="fund-check-group-head">
              <span>{g.title}</span>
              <small title={GROUP_EXPLAIN}>{g.count}</small>
            </div>
            {g.rows.map((c) => (
              <div key={c.key} className="fund-check" title={CHECK_EXPLAIN[c.key]}>
                <CheckMark state={c.state} />
                <div>
                  <span>{c.label}</span>
                  {c.why ? <small>{c.why}</small> : null}
                </div>
              </div>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

// The two tables side by side, the latest row of each a step brighter.
function SheetTables({ sheet }) {
  const reports = reportRows(sheet);
  const quarters = quarterRows(sheet);
  return (
    <div className="fund-sheet-tables">
      {reports.length ? (
        <div className="fund-sheet-block">
          <h3 title={SECTION_EXPLAIN.reports}>Earnings reports</h3>
          <table className="fund-sheet-table">
            <thead>
              <tr>
                <th title={REPORT_COLUMNS.report}>Report</th>
                <th title={REPORT_COLUMNS.eps}>EPS adj.</th>
                <th title={REPORT_COLUMNS.yoy}>Year on year</th>
                <th title={REPORT_COLUMNS.surprise}>vs estimate</th>
                <th title={REPORT_COLUMNS.move}>Market move</th>
              </tr>
            </thead>
            <tbody>
              {reports.map((r) => (
                <tr key={r.key}>
                  <td>{r.day}</td>
                  <td>{r.eps}</td>
                  <td style={{ color: r.yoyTone }}>{r.yoy}</td>
                  <td style={{ color: r.beat == null ? undefined : r.beat ? 'var(--success)' : 'var(--warning)' }}>
                    {r.surprise}{r.beat == null ? '' : r.beat ? ' beat' : ' missed'}
                  </td>
                  <td title={r.moveTitle} style={{ color: r.moveTone }}>{r.move}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
      {quarters.length ? (
        <div className="fund-sheet-block">
          <h3 title={SECTION_EXPLAIN.quarters}>Quarters</h3>
          <table className="fund-sheet-table">
            <thead>
              <tr>
                <th title={QUARTER_COLUMNS.quarter}>Quarter</th>
                <th title={QUARTER_COLUMNS.sales}>Sales</th>
                <th title={QUARTER_COLUMNS.yoy}>Year on year</th>
                <th title={QUARTER_COLUMNS.qoq}>On the quarter</th>
                <th title={QUARTER_COLUMNS.margin}>Op. margin</th>
                <th title={QUARTER_COLUMNS.gaap}>EPS GAAP</th>
              </tr>
            </thead>
            <tbody>
              {quarters.map((q) => (
                <tr key={q.key}>
                  <td>{q.quarter}</td>
                  <td>{q.sales}</td>
                  <td title={q.yoyTitle} style={{ color: q.yoyTone }}>{q.yoy}</td>
                  <td style={{ color: q.qoqTone }}>{q.qoq}</td>
                  <td style={{ color: q.marginTone }}>{q.operatingMargin}</td>
                  <td title={q.gaapTitle}>{q.gaap}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </div>
  );
}

// The estimates, quality, flags and Code 33 lines (the next report sits in the head).
function SheetRead({ sheet }) {
  const lines = sheetLines(sheet).filter((line) => line.k !== 'Next report');
  return (
    <div className="fund-sheet-block">
      <h3 title={SECTION_EXPLAIN.read}>The read</h3>
      <dl className="fund-sheet-lines">
        {lines.map((line) => (
          <div key={line.k} title={lineExplain(line.k, sheet)}>
            <dt>{line.k}</dt>
            <dd style={{ color: line.tone }}>{line.v}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

// The fundamentals sheet (2026-10-12): his list, the business beside the stock,
// graded apart from the setup. It is the big chart's second page (2026-10-13, his
// "a second page rather then another block below"). Laid out again Wed 28/10/2026
// from the design canvas (his "this is unreadable"): the grade and the next report
// on top, the nine checks in three boxes, the two tables side by side in a larger
// type, then the read.
export default function FundamentalsSheet({ data }) {
  const sheet = data.fund_sheet;
  return (
    <section className="stock-lens-section fund-sheet">
      <SheetHead sheet={sheet} marketCap={data.market_cap} />
      <SheetChecks sheet={sheet} />
      <SheetTables sheet={sheet} />
      <SheetRead sheet={sheet} />
    </section>
  );
}
