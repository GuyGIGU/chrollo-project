import { fmtMoneyCompact } from '../formatting/format';
import { cardHeader, checkRows, gradeNote, quarterRows, reportRows, sheetLines } from './fundamentalsSheetRead';

// The fundamentals sheet (2026-10-12): his list, the business beside the stock,
// graded apart from the setup. Reports and quarters as two small tables, the
// estimates and earnings-quality lines, then the nine checks the grade rests on.
export default function FundamentalsSheet({ data }) {
  const sheet = data.fund_sheet;
  const reports = reportRows(sheet);
  const quarters = quarterRows(sheet);
  const head = cardHeader(sheet);
  const snap = sheet.snapshot || {};
  return (
    <section className="stock-lens-section fund-sheet">
      <div className="stock-lens-section-header">
        <span>Fundamentals</span>
        <small>{gradeNote(sheet)} · cap {fmtMoneyCompact(data.market_cap)}</small>
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
                <td>{r.yoy}</td>
                <td style={{ color: r.beat == null ? undefined : r.beat ? 'var(--success)' : 'var(--warning)' }}>{r.surprise}</td>
                <td title={r.moveTitle}>{r.move}</td>
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
                <td title={q.yoyTitle}>{q.yoy}</td>
                <td>{q.qoq}</td>
                <td>{q.operatingMargin}</td>
                <td title={q.gaapTitle}>{q.gaap}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}
      <div className="fund-sheet-lines">
        {sheetLines(sheet).map((line) => (
          <div key={line.k}><span className="lens-k">{line.k}</span> {line.v}</div>
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
    </section>
  );
}
