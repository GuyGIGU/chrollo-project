import { fmtMoneyCompact } from '../formatting/format';
import { cardHeader, checkRows, gradeNote, quarterRows, reportRows, sheetLines } from './fundamentalsSheetRead';

// The verdict, the snapshot and the two small tables: the numbers.
function SheetNumbers({ sheet }) {
  const reports = reportRows(sheet);
  const quarters = quarterRows(sheet);
  const head = cardHeader(sheet);
  const snap = sheet.snapshot || {};
  return (
    <div className="fund-sheet-numbers">
      <div className="fund-sheet-verdict" data-grade={head.letter || 'none'} title={head.title}>
        <span className="fund-grade-tile">{head.letter || '–'}</span>
        <span style={{ color: head.labelTone }}>{head.label}</span>
        <small>{head.checks || gradeNote(sheet)}</small>
        {head.code33 ? <span className="fund-card-badge" title={head.code33Title}>Code 33 ✓</span> : null}
      </div>
      {head.snapshot || snap.summary ? (
        <div className="fund-sheet-snapshot">
          {[snap.name, head.snapshot].filter(Boolean).join(' · ')}
          {snap.summary ? <small>{snap.summary}</small> : null}
        </div>
      ) : null}
      {reports.length ? (
        <table className="fund-sheet-table">
          <thead>
            <tr><th>Report</th><th title="Adjusted EPS, the figure the analysts estimate">EPS adj.</th><th>Year on year</th><th>vs estimate</th><th>Move</th></tr>
          </thead>
          <tbody>
            {reports.map((r) => (
              <tr key={r.key}>
                <td>{r.day}</td>
                <td>{r.eps}</td>
                <td style={{ color: r.yoyTone }}>{r.yoy}</td>
                <td style={{ color: r.beat == null ? undefined : r.beat ? 'var(--success)' : 'var(--warning)' }}>{r.surprise}</td>
                <td title={r.moveTitle} style={{ color: r.moveTone }}>{r.move}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}
      {quarters.length ? (
        <table className="fund-sheet-table">
          <thead>
            <tr><th>Quarter</th><th>Sales</th><th>Year on year</th><th>On the quarter</th><th>Op. margin</th><th title="GAAP diluted EPS">EPS GAAP</th></tr>
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
      ) : null}
    </div>
  );
}

// The estimates and earnings-quality lines, then the nine checks: the words.
function SheetWords({ sheet }) {
  return (
    <div className="fund-sheet-words">
      <div className="fund-sheet-lines">
        {sheetLines(sheet).map((line) => (
          <div key={line.k}><span className="lens-k">{line.k}</span> <span style={{ color: line.tone }}>{line.v}</span></div>
        ))}
      </div>
      <ul className="fund-sheet-checks">
        {checkRows(sheet).map((c) => (
          <li key={c.key} title={c.why}>
            <span className="fund-check-mark" style={{ color: c.tone }}>{c.mark}</span>
            <span>{c.label}</span>
            <small>{c.why}</small>
          </li>
        ))}
      </ul>
    </div>
  );
}

// The fundamentals sheet (2026-10-12): his list, the business beside the stock,
// graded apart from the setup. Reports and quarters as two small tables, the
// estimates and earnings-quality lines, then the nine checks the grade rests on.
// It is the big chart's second page (2026-10-13, his "a second page rather then
// another block below"): the panel's whole width, the numbers on the left and
// the lines and checks beside them.
export default function FundamentalsSheet({ data }) {
  const sheet = data.fund_sheet;
  return (
    <section className="stock-lens-section fund-sheet">
      <div className="stock-lens-section-header">
        <span>Fundamentals</span>
        <small>cap {fmtMoneyCompact(data.market_cap)}</small>
      </div>
      <div className="fund-sheet-body">
        <SheetNumbers sheet={sheet} />
        <SheetWords sheet={sheet} />
      </div>
    </section>
  );
}
