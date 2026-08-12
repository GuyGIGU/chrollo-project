import { useCallback, useEffect, useMemo, useState } from 'react';
import ScreenerModal from './ScreenerModal';
import useWatchlist from '../hooks/useWatchlist';
import { fetchReplay, useWatchlistHistory } from '../hooks/useWatchlistHistory';
import { adaptReplaySnapshot, replayProvenance } from './replayAdapter';
import { toast } from './ui/feedback';
import { tierColor } from '../theme';
import { fixed } from '../utils/archiveTabUtils';
import { fmtSignedPctFrac } from '../utils/format';

// The weekly review surface (Finviz plan Task 9). Core gesture = the flip:
// as-saved replay <-> the current chart of the same ticker, in the SAME
// viewer at the same screen position, one action each way. As-saved mode is
// structural, not decorative: scanIdentity is null (the read-verdict control
// goes inert), price/change come from the STORED entry, and a persistent
// mono provenance frame states what is being looked at. Score/tier on a row
// and inside its replay quote the same stored bytes (EC-28) — they cannot
// disagree.
function WeeklyReview({ open, onClose, screenerData }) {
  const { weeks, error, reload } = useWatchlistHistory(open);
  const { watchlist, toggleWatchlist } = useWatchlist();
  const [replay, setReplay] = useState(null); // { save, env }
  const [showCurrent, setShowCurrent] = useState(false);

  const flatSaves = useMemo(
    () => (weeks || []).flatMap((week) => week.saves), [weeks]);

  const openReplay = useCallback((save) => {
    setShowCurrent(false);
    fetchReplay(save.id)
      .then((env) => setReplay({ save, env }))
      .catch((err) => {
        console.error('Replay load failed', err);
        toast('Replay failed to load', { tone: 'danger' });
      });
  }, []);

  // Walk the week's saves with the trained modal-pager rhythm (wraparound).
  const step = useCallback((delta) => {
    if (!replay || flatSaves.length === 0) return;
    const index = flatSaves.findIndex((s) => s.id === replay.save.id);
    const next = (index + delta + flatSaves.length) % flatSaves.length;
    openReplay(flatSaves[next]);
  }, [replay, flatSaves, openReplay]);

  // Escape closes the LIST only while no replay is open — the modal owns
  // Escape while it is mounted (double-close guard).
  useEffect(() => {
    if (!open || replay) return undefined;
    const onKey = (event) => {
      if (event.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [open, replay, onClose]);

  if (!open) return null;

  const onToggleStar = (save) => {
    const wasOn = watchlist.has(save.ticker);
    Promise.resolve(toggleWatchlist(save.ticker)).finally(reload);
    if (wasOn) {
      toast('Removed from watchlist — its saved weeks stay in review', { tone: 'info' });
    }
  };

  return (
    <div style={overlayStyle} onClick={onClose}>
      <div style={panelStyle} onClick={(event) => event.stopPropagation()}>
        <div style={headerStyle}>
          <span style={{ fontWeight: 700, fontSize: 14, color: 'var(--text-main)' }}>
            Weekly review
          </span>
          <span style={{ color: 'var(--text-faint)', fontSize: 12 }}>
            saves grouped by the scan week they pinned
          </span>
          <button type="button" className="focus-ring" onClick={onClose} style={closeButtonStyle}
                  aria-label="Close review">×</button>
        </div>

        {weeks == null && !error && <div style={mutedStyle}>Loading…</div>}
        {error && (
          <div style={mutedStyle}>
            Couldn&apos;t load review history.{' '}
            <button type="button" onClick={reload} style={linkButtonStyle}>Try again</button>
          </div>
        )}
        {weeks != null && !error && weeks.length === 0 && (
          <div style={mutedStyle}>
            No saves yet — star a setup and it will appear here under its scan week.
          </div>
        )}

        {(weeks || []).map((week) => (
          <div key={week.week_start} style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            <div style={weekHeaderStyle}>week of {week.week_start}</div>
            {week.saves.map((save) => (
              <ReviewRow
                key={save.id}
                save={save}
                starred={watchlist.has(save.ticker)}
                onOpen={() => openReplay(save)}
                onToggleStar={() => onToggleStar(save)}
              />
            ))}
          </div>
        ))}
      </div>

      {replay && (
        <ReplayViewer
          replay={replay}
          screenerData={screenerData}
          showCurrent={showCurrent}
          onFlip={() => setShowCurrent((value) => !value)}
          onClose={() => setReplay(null)}
          onPrev={() => step(-1)}
          onNext={() => step(1)}
        />
      )}
    </div>
  );
}

function ReviewRow({ save, starred, onOpen, onToggleStar }) {
  return (
    <div style={{ ...rowStyle, opacity: save.active ? 1 : 0.62 }}>
      <button
        type="button"
        onClick={onToggleStar}
        style={starButtonStyle}
        title={starred ? 'Remove from watchlist (history stays here)' : 'Re-add to watchlist'}
        aria-label={starred ? `Unstar ${save.ticker}` : `Star ${save.ticker}`}
      >
        {starred ? '★' : '☆'}
      </button>
      <button type="button" className="focus-ring" onClick={onOpen} style={rowMainStyle}>
        <span style={{
          color: save.pinned ? tierColor(save.tier) : 'var(--text-muted)',
          fontWeight: 700, minWidth: 52, textAlign: 'left',
        }}>
          {save.ticker}
        </span>
        <span style={cellStyle}>{save.tier || '—'}</span>
        <span style={{ ...cellStyle, ...monoCellStyle }}>{fixed(save.score, 0)}</span>
        <span style={{ ...cellStyle, minWidth: 64 }}>{save.setup || '—'}</span>
        <span style={{ ...cellStyle, ...monoCellStyle, minWidth: 86 }}>
          {save.pin_scan_date || 'no setup'}
        </span>
        <span style={{ ...cellStyle, color: 'var(--text-faint)' }}>
          {save.active ? 'active' : 'unstarred'}
          {save.pinned && !save.has_snapshot ? ' · no snapshot' : ''}
        </span>
      </button>
    </div>
  );
}

function ReplayViewer({ replay, screenerData, showCurrent, onFlip, onClose, onPrev, onNext }) {
  const { save, env } = replay;
  const adapted = adaptReplaySnapshot(env.snapshot);
  const provenance = replayProvenance(env);
  const currentEntry = screenerData?.chart_data?.[save.ticker] ?? null;
  const liveIdentity = screenerData?.scan_identity ?? null;

  const mode = showCurrent && currentEntry ? 'current' : adapted ? 'saved' : 'none';

  // The modal owns Escape while mounted; the no-snapshot fallback card has no
  // modal, so it closes itself.
  useEffect(() => {
    if (mode !== 'none') return undefined;
    const onKey = (event) => {
      if (event.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [mode, onClose]);

  if (mode === 'none') {
    // Nothing stored to draw: state it in place instead of a broken chart.
    return (
      <div style={fallbackOverlayStyle} onClick={onClose}>
        <div style={fallbackCardStyle} onClick={(event) => event.stopPropagation()}>
          <div style={stampStyle}>
            SAVED {provenance.savedOn || '—'}
            {provenance.unstarred ? ' · unstarred' : ''} · {save.ticker}
          </div>
          <div style={{ color: 'var(--text-muted)', fontSize: 13 }}>
            No stored snapshot for this save. {provenance.archiveNote}
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            {currentEntry && (
              <button type="button" style={flipButtonStyle} onClick={onFlip}>
                View current chart
              </button>
            )}
            <button type="button" style={flipButtonStyle} onClick={onClose}>Close</button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <ScreenerModal
      ticker={save.ticker}
      data={mode === 'current' ? currentEntry : adapted.entry}
      // As-saved is structural: a null identity turns the live read-verdict
      // control inert; the stored entry supplies price/change as of the save.
      scanIdentity={mode === 'current' ? liveIdentity : null}
      onClose={onClose}
      onPrev={onPrev}
      onNext={onNext}
      footer={(
        <div style={footerStyle}>
          <span style={stampStyle}>
            {mode === 'current'
              ? `CURRENT · scan ${liveIdentity?.scan_date || '—'}`
              : `AS SCANNED ${provenance.asScanned || '—'} · saved ${provenance.savedOn || '—'}${provenance.unstarred ? ' · unstarred' : ''}`}
          </span>
          {mode === 'saved' && (
            <span style={noteStyle}>{provenance.archiveNote}</span>
          )}
          {mode === 'saved' && env.archive && env.archive.ret_to_date != null && (
            <span style={{ ...noteStyle, ...monoCellStyle }}>
              since: {fmtSignedPctFrac(env.archive.ret_to_date)}
              {env.archive.win_barrier ? ` · ${env.archive.win_barrier}` : ''}
            </span>
          )}
          <button
            type="button"
            style={{
              ...flipButtonStyle,
              opacity: (mode === 'saved' ? currentEntry : adapted) ? 1 : 0.45,
            }}
            disabled={mode === 'saved' ? !currentEntry : !adapted}
            title={mode === 'saved'
              ? (currentEntry ? 'Flip to the current chart' : 'Not in the latest scan')
              : (adapted ? 'Flip back to the as-saved chart' : 'No snapshot stored')}
            onClick={onFlip}
          >
            {mode === 'current' ? 'View as saved' : 'View current'}
          </button>
        </div>
      )}
    />
  );
}

const overlayStyle = {
  position: 'fixed', inset: 0, zIndex: 4900,
  background: 'rgba(10, 12, 18, 0.72)',
  display: 'flex', alignItems: 'flex-start', justifyContent: 'center',
  padding: '40px 16px', overflowY: 'auto',
};

const panelStyle = {
  background: 'var(--bg-panel)',
  border: '1px solid var(--border-color)',
  borderRadius: 'var(--radius-sm)',
  display: 'flex', flexDirection: 'column', gap: 12,
  maxWidth: 860, width: '100%',
  padding: '14px 16px',
};

const headerStyle = {
  alignItems: 'baseline', display: 'flex', gap: 10,
};

const closeButtonStyle = {
  background: 'transparent', border: 'none', color: 'var(--text-muted)',
  cursor: 'pointer', fontSize: 18, lineHeight: 1, marginLeft: 'auto',
  padding: '2px 6px',
};

const weekHeaderStyle = {
  color: 'var(--text-faint)', fontSize: 11, fontWeight: 600,
  letterSpacing: '0.08em', textTransform: 'uppercase',
};

const rowStyle = {
  alignItems: 'center', display: 'flex', gap: 6,
};

const rowMainStyle = {
  alignItems: 'center',
  background: 'transparent',
  border: '1px solid var(--border-color)',
  borderRadius: 'var(--radius-sm)',
  color: 'var(--text-main)',
  cursor: 'pointer',
  display: 'flex', flex: 1, gap: 12,
  fontFamily: 'inherit', fontSize: 13,
  padding: '6px 10px', textAlign: 'left',
};

const cellStyle = { color: 'var(--text-main)', minWidth: 34 };

const monoCellStyle = {
  fontFamily: "'JetBrains Mono', ui-monospace, monospace",
  fontVariantNumeric: 'tabular-nums',
};

const starButtonStyle = {
  background: 'transparent', border: 'none', color: 'var(--accent-active)',
  cursor: 'pointer', fontSize: 15, padding: '2px 4px',
};

const mutedStyle = { color: 'var(--text-muted)', fontSize: 13, padding: '8px 0' };

const linkButtonStyle = {
  background: 'transparent', border: 'none', color: 'var(--accent-active)',
  cursor: 'pointer', fontFamily: 'inherit', fontSize: 13, padding: 0,
  textDecoration: 'underline',
};

const fallbackOverlayStyle = {
  position: 'fixed', inset: 0, zIndex: 5000,
  background: 'rgba(10, 12, 18, 0.72)',
  display: 'flex', alignItems: 'center', justifyContent: 'center',
  padding: 16,
};

const fallbackCardStyle = {
  background: 'var(--bg-panel)',
  border: '1px solid var(--border-color)',
  borderRadius: 'var(--radius-sm)',
  display: 'flex', flexDirection: 'column', gap: 12,
  maxWidth: 460, padding: '16px 18px',
};

const footerStyle = {
  alignItems: 'center', display: 'flex', flexWrap: 'wrap', gap: 12,
  padding: '8px 2px 2px',
};

const stampStyle = {
  color: 'var(--text-faint)', fontSize: 11, fontWeight: 600,
  fontFamily: "'JetBrains Mono', ui-monospace, monospace",
  letterSpacing: '0.08em',
};

const noteStyle = { color: 'var(--text-muted)', fontSize: 12 };

const flipButtonStyle = {
  background: 'transparent',
  border: '1px solid var(--border-color)',
  borderRadius: 'var(--radius-sm)',
  color: 'var(--text-main)',
  cursor: 'pointer',
  fontFamily: 'inherit', fontSize: 12,
  marginLeft: 'auto',
  padding: '4px 12px',
};

export default WeeklyReview;
