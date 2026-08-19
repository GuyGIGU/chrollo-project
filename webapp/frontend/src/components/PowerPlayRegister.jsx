// The Power-Play mark register (program Task 14) — MARK-register chrome by
// ruling: muted, narrow, plain words. A species candidacy is a note in the
// margin ("MAN — watched, ungraded"), NEVER chip/pill chrome, never a tier
// color; promotion to chip chrome is the flip's visible record. Muting rides
// the app's text tokens (--text-muted / --text-faint), not stacked opacities,
// so the register stays on the designed contrast ramp on any surface; the
// meta line uses the app's JetBrains Mono numeric standard (2026-08-17
// review, Saarinen).
//
// NOT MOUNTED YET, by design: the screener surfaces are mid-flight on the
// operator's watchlist branch, so the one-line mount
// (`<PowerPlayRegister marketContext={payload.market_context} />`) lands at
// merge time. The projection it renders is node-tested independently
// (powerPlayRegister.test.js), and the data already rides the one screener
// payload through market_context — no second store, no second fetch.

import { powerPlayCounts, powerPlayRows } from './powerPlayRegister.js';

export default function PowerPlayRegister({ marketContext }) {
  const rows = powerPlayRows(marketContext);
  if (!rows.length) return null;
  const counts = powerPlayCounts(marketContext);
  return (
    <section
      aria-label="Power Play register"
      style={{ maxWidth: 420, color: 'var(--text-muted)', fontSize: 12, lineHeight: 1.5 }}
    >
      <div style={{ letterSpacing: '0.06em', textTransform: 'uppercase', color: 'var(--text-faint)' }}>
        Power Play register
      </div>
      <ul style={{ listStyle: 'none', margin: 0, padding: 0 }}>
        {rows.map((row) => (
          <li key={`${row.ticker}:${row.status}`} style={{ padding: '2px 0' }}>
            <span style={{ fontWeight: 600 }}>{row.ticker}</span>
            {' — '}
            <span>{row.statusTail}</span>
            <div style={{ fontFamily: "'JetBrains Mono', monospace", color: 'var(--text-faint)' }}>
              {row.meta}
            </div>
          </li>
        ))}
      </ul>
      {counts ? (
        <div style={{ color: 'var(--text-faint)', paddingTop: 2 }}>
          {Object.entries(counts).map(([k, v]) => `${k} ${v}`).join(' · ')}
        </div>
      ) : null}
    </section>
  );
}
