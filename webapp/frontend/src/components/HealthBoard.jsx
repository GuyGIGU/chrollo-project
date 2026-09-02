import ScreenerCard from './ScreenerCard';
import { groupHealthMembers } from './healthBoardSort';

// The Market & Sector Health Board: a full-time, state-classified read of every
// member of a non-equity universe (the firing engine fires zero setups on broad
// ETFs by design, so these tabs would otherwise be empty). It re-frames the SAME
// reading-room card as a health READ — decision-point members surfaced first in
// labeled state bands — and is deliberately quiet: zero hue on state, no score /
// tier / buy language anywhere.
//
// Presentational only. The engine owns each member's classification; this
// component orders, groups, and renders — it never recomputes a state.

const REASON_LABEL = {
  short_history: 'not enough history to read yet',
  not_available: 'no data in this scan',
  error: 'could not be read this scan',
};

function formatScanTime(scannedAt) {
  if (!scannedAt) return null;
  const t = new Date(scannedAt);
  if (Number.isNaN(t.getTime())) return null;
  return t.toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}

function HealthBoard({ board, universeLabel, scannedAt, onDrilldown }) {
  const members = Array.isArray(board?.members) ? board.members : [];
  const unreadable = Array.isArray(board?.unreadable) ? board.unreadable : [];
  const bands = groupHealthMembers(members);
  const total = Number.isFinite(board?.member_count) ? board.member_count : members.length + unreadable.length;
  const asOf = formatScanTime(scannedAt);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
      {/* Persistent board-mode header — sets the reading before the eye hits the
          first card: this is a position-in-cycle READ, sorted decision-point-first,
          and an end-of-scan snapshot (not a real-time feed). */}
      <div style={headerStyle}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, flexWrap: 'wrap' }}>
          <span style={{ color: 'var(--text-main)', fontSize: 13, fontWeight: 700 }}>
            {universeLabel} · Health read
          </span>
          <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>
            where each member sits in its cycle — not a list of setups to buy
          </span>
        </div>
        <div style={{ color: 'var(--text-faint)', fontSize: 11, marginTop: 6, lineHeight: 1.5 }}>
          Sorted decision-point first (near a rail / just broke out), dormant last · {total} members
          {unreadable.length > 0 ? ` · ${unreadable.length} unavailable` : ''}
          {asOf ? ` · as of last scan ${asOf}` : ''}.
          {' '}A fresh move may take a few sessions to show — the board re-labels on the next scan.
        </div>
      </div>

      {members.length === 0 && unreadable.length === 0 ? (
        <div style={emptyStyle}>
          No members were read for {universeLabel} in the latest scan. This universe is
          refreshed by the scheduled daily scan.
        </div>
      ) : null}

      {bands.map((band) => (
        <StateBand key={band.key} band={band} onDrilldown={onDrilldown} />
      ))}

      {unreadable.length > 0 ? <UnreadableBand items={unreadable} /> : null}
    </div>
  );
}

// One labeled state section with a count. Decision-point bands carry a little more
// presence (accent tick + brighter label); dormant ones recede — a two-tone
// attention ramp, spending no color on the state itself.
function StateBand({ band, onDrilldown }) {
  return (
    <section>
      <div style={bandHeaderStyle(band.decision)}>
        <span style={{ color: band.decision ? 'var(--text-main)' : 'var(--text-muted)', fontSize: 12, fontWeight: 700, letterSpacing: '0.03em', textTransform: 'uppercase' }}>
          {band.label}
        </span>
        <span style={{ color: 'var(--text-faint)', fontSize: 12, fontWeight: 700 }}>· {band.members.length}</span>
        <span style={{ color: 'var(--text-faint)', fontSize: 11, fontWeight: 400 }}>{band.blurb}</span>
      </div>
      <div style={gridStyle}>
        {band.members.map((member) => (
          <ScreenerCard
            key={member.ticker}
            health
            ticker={member.ticker}
            data={member}
            onDrilldown={onDrilldown}
          />
        ))}
      </div>
    </section>
  );
}

// The honest "can't read this member yet" bucket — a partial fetch or a too-short
// history must never blank or silently shrink the board.
function UnreadableBand({ items }) {
  const byReason = items.reduce((acc, item) => {
    (acc[item.reason] || (acc[item.reason] = [])).push(item.ticker);
    return acc;
  }, {});
  return (
    <section>
      <div style={bandHeaderStyle(false)}>
        <span style={{ color: 'var(--text-muted)', fontSize: 12, fontWeight: 700, letterSpacing: '0.03em', textTransform: 'uppercase' }}>
          Can’t read yet
        </span>
        <span style={{ color: 'var(--text-faint)', fontSize: 12, fontWeight: 700 }}>· {items.length}</span>
      </div>
      <div style={{ ...unreadableCardStyle }}>
        {Object.entries(byReason).map(([reason, tickers]) => (
          <div key={reason} style={{ marginBottom: 6 }}>
            <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>{REASON_LABEL[reason] || reason}: </span>
            <span style={{ color: 'var(--text-faint)', fontSize: 12, fontFamily: "'JetBrains Mono', monospace" }}>
              {tickers.join(', ')}
            </span>
          </div>
        ))}
      </div>
    </section>
  );
}

const headerStyle = {
  background: 'var(--bg-panel)',
  border: '1px solid var(--border-color)',
  borderRadius: 'var(--radius-sm)',
  padding: '12px 14px',
};

const emptyStyle = {
  padding: '2rem',
  textAlign: 'center',
  color: 'var(--text-muted)',
};

const bandHeaderStyle = (decision) => ({
  alignItems: 'baseline',
  borderLeft: `2px solid ${decision ? 'var(--accent-blue)' : 'var(--border-color)'}`,
  display: 'flex',
  gap: 8,
  flexWrap: 'wrap',
  margin: '0 0 10px 0',
  opacity: decision ? 1 : 0.82,
  padding: '2px 0 2px 10px',
});

const unreadableCardStyle = {
  background: 'var(--bg-panel)',
  border: '1px solid var(--border-color)',
  borderRadius: 'var(--radius-sm)',
  padding: '12px 14px',
};

const gridStyle = {
  display: 'grid',
  gridTemplateColumns: 'repeat(auto-fill, minmax(620px, 1fr))',
  gap: '14px',
  width: '100%',
};

export default HealthBoard;
