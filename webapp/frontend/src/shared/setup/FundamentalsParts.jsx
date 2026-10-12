// One line of the fundamentals read, piece by piece: each piece in the tone the
// read module gave it (fundamentalsSheetRead.js), a pill for a verdict word.
export default function FundamentalsParts({ parts }) {
  return parts.map((part, i) => (
    <span
      key={i}
      className={part.pill ? 'fund-pill' : part.strong ? 'fund-strong' : undefined}
      style={part.tone ? { '--tone': part.tone, color: 'var(--tone)' } : undefined}
    >
      {part.t}
    </span>
  ));
}
