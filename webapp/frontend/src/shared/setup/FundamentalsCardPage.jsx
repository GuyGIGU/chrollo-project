import { cardHeader, cardLines } from './fundamentalsSheetRead';

// The card's second page (2026-10-12, his "a second page in the Mini Chart"): the
// business in the chart well's own space, so the board can be read both ways
// without opening the lens. Compact by design: the label, the four-quarter
// sequences, margins, the last report, estimates, quality, the next report.
// Every word arrives decided by the scan; this only lays it out.
export default function FundamentalsCardPage({ data }) {
  const head = cardHeader(data.fund_sheet);
  return (
    <div className="fund-card-page">
      <div className="fund-card-head">
        <span className="fund-card-title">Fundamentals</span>
        <span className="fund-card-verdict" title={head.title}>
          {head.letter ? <b>{head.letter}</b> : null}
          {head.letter ? ' · ' : null}
          {head.label}
        </span>
        {head.code33 ? (
          <span className="fund-card-badge" title={head.code33Title}>Code 33</span>
        ) : null}
      </div>
      {head.snapshot ? <div className="fund-card-snapshot" title={head.snapshotTitle}>{head.snapshot}</div> : null}
      <div className="fund-card-lines">
        {cardLines(data.fund_sheet).map((line) => (
          <div className="fund-card-line" key={line.k} title={line.title}>
            <span className="fund-card-k">{line.k}</span>
            <span className="fund-card-v" style={line.tone ? { color: line.tone } : undefined}>{line.v}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
