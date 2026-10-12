import { cardHeader, cardLines } from './fundamentalsSheetRead';
import FundamentalsParts from './FundamentalsParts';

// The card's second page (2026-10-12, his "a second page in the Mini Chart"): the
// business in the chart well's own space, so the board can be read both ways
// without opening the lens. Compact by design: the label, the four-quarter
// sequences, margins, the last report, estimates, quality, the next report.
// Every word arrives decided by the scan; this only lays it out. The colors
// (his "more color and style", same day): the grade's own tile and edge, green
// for growth, rose for decline, amber for caution.
export default function FundamentalsCardPage({ data }) {
  const head = cardHeader(data.fund_sheet);
  return (
    <div className="fund-card-page" data-grade={head.letter || 'none'}>
      <div className="fund-card-head">
        <span className="fund-grade-tile" title={head.title}>{head.letter || '–'}</span>
        <div className="fund-card-who">
          <span className="fund-card-verdict" title={head.title}>
            <span style={{ color: head.labelTone }}>{head.label}</span>
            {head.checks ? <small> · {head.checks}</small> : null}
          </span>
          {head.snapshot ? <span className="fund-card-snapshot" title={head.snapshotTitle}>{head.snapshot}</span> : null}
        </div>
        {head.code33 ? (
          <span className="fund-card-badge" title={head.code33Title}>Code 33 ✓</span>
        ) : null}
      </div>
      <div className="fund-card-lines">
        {cardLines(data.fund_sheet).map((line) => (
          <div className="fund-card-line" key={line.k} title={line.title}>
            <span className="fund-card-k">{line.k}</span>
            <span className="fund-card-v">
              {line.parts ? <FundamentalsParts parts={line.parts} /> : line.v}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
