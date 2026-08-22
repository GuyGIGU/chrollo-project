import { useEffect, useRef, useState } from 'react';

import SetupStoryPanel from './SetupStoryPanel';
import { buildPhaseRegions } from './chartPhaseOverlay';
import {
  ABSENCE_COPY,
  NARRATIVE_STATUS,
  narrativeStatus,
  readCaveats,
  shapeTrace,
  tapeGlyphs,
} from './narrativeRead';
import { toast } from './ui/feedback';
import {
  ROOT_OUTCOME_LABELS,
  TRACE_STAGE_LABELS,
  TREND_STATE_LABELS,
  displayLabel,
} from './wireVocabulary';
import { API_BASE } from '../api';
import { fx, fmtDateShort } from '../utils/format';
import { triggerDistanceFrac } from '../utils/triggerProximity.js';

const pct = (value, digits = 1) => {
  const fixed = fx(value, digits, null);
  return fixed == null ? '-' : `${fixed}%`;
};

const finiteNumber = (value) => {
  if (value == null || value === '') return null;
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
};

const bars = (value) => {
  const number = finiteNumber(value);
  if (number == null) return '-';
  const rounded = Math.round(number);
  return `${rounded} bar${rounded === 1 ? '' : 's'}`;
};

const latestCandle = (data) => data?.candles?.[data.candles.length - 1] || null;

const distanceToTriggerPct = (data) => {
  // The shared judgment (EC-3): % move price must make to reach the trigger.
  const frac = triggerDistanceFrac(data, data?.price ?? latestCandle(data)?.close);
  return frac == null ? null : frac * 100;
};

const boxWidthPct = (data) => {
  const support = finiteNumber(data?.S);
  const resistance = finiteNumber(data?.R);
  if (support == null || resistance == null || support <= 0) return null;
  return ((resistance - support) / support) * 100;
};

const triggerRead = (value) => {
  if (value == null) return 'No trigger read yet';
  if (value < -0.25) return 'Already above trigger';
  if (value <= 0.75) return 'Right under trigger';
  if (value <= 2) return 'Close to trigger';
  return 'Needs more room';
};

const sectorLabel = (data) => data?.sector_etf || data?.sector_name || '-';

// Next-earnings cell for the detail grid. Shows the actual DATE (never the
// cryptic "ER"), tinted by proximity — caution amber inside ~10 days, danger
// inside 3 — with a plain-language tooltip. '-' when no upcoming date is known.
const earningsDisplay = (earnings) => {
  const date = earnings?.date;
  if (!date) return { value: '-', tone: undefined, title: 'No upcoming earnings date available' };
  const days = earnings?.days_until;
  let tone;
  if (days != null && days >= 0) {
    if (days <= 3) tone = 'var(--danger)';
    else if (days <= 10) tone = 'var(--warning)';
  }
  const title = days == null
    ? `Next earnings: ${date}`
    : days >= 0
      ? `Next earnings in ${days} day${days === 1 ? '' : 's'} (${date})`
      : `Last earnings ${-days} day${days === -1 ? '' : 's'} ago (${date})`;
  return { value: fmtDateShort(date), tone, title };
};

// The Finviz-style dense read: one tight grid of the engine's technical facts.
// Finviz fills this with fundamentals (P/E, EPS); Chrollo has none, so every cell
// is a measured structural fact from the scan payload — no invented data.
function TechnicalReadGrid({ data, earnings }) {
  const contractions = finiteNumber(data.contraction_count);
  const earn = earningsDisplay(earnings);

  const cells = [
    { k: 'Box width', v: pct(boxWidthPct(data)) },
    { k: 'ADR', v: pct(data.adr_pct) },
    { k: 'Base length', v: bars(data.base_len) },
    { k: 'LPS pullback', v: bars(data.lps_len) },
    { k: 'Contractions', v: contractions == null ? '-' : String(contractions) },
    { k: displayLabel('traversal_density'), v: fx(data.traversal_density, 2, '-') },
    { k: 'Sector', v: sectorLabel(data), tone: 'var(--accent-blue)', title: data?.sector_name || undefined },
    { k: 'Earnings', v: earn.value, tone: earn.tone, title: earn.title },
  ];

  return (
    <section className="stock-lens-section">
      <div className="stock-lens-section-header">
        <span>Technical read</span>
        <small>{data.setup || ''}</small>
      </div>
      <div className="lens-grid">
        {cells.map((cell) => (
          <div className="lens-cell" key={cell.k} title={cell.title}>
            <span className="lens-k">{cell.k}</span>
            <span className="lens-v" style={{ color: cell.tone || 'var(--text-main)' }}>{cell.v}</span>
          </div>
        ))}
      </div>
    </section>
  );
}

// ── The Engine's Read (Surface the Read) ─────────────────────────────────────
// The narrative panel: what the engine believes transpired on this chart —
// the rail-episode tape as a mono glyph strip (hover/focus locates each
// episode on the chart through the SAME activeRegion channel the phase bins
// drive), the electing-pool provenance, and the election trace as a
// collapsed, labeled, recessed readout. All judgments arrive pre-computed;
// this panel only lays them out (narrativeRead owns the shaping).

// All control/well styling lives in index.css (.narrative-* classes) so the
// panel speaks the same hover/:focus-visible grammar as .phase-bin-control
// beside it (council review 2026-08-05, finding 12 — inline styles can't
// express either).

const mutedLine = {
  color: 'var(--text-muted)',
  fontSize: 12,
};

const narrativeCountsLine = (data) => {
  const parts = [];
  const trend = TREND_STATE_LABELS[data.event_map_pre_box_trend] ?? data.event_map_pre_box_trend;
  if (trend != null) parts.push(`into the base: ${trend}`);
  const s = finiteNumber(data.event_map_completed_s);
  if (s != null) parts.push(`${s} completed support test${s === 1 ? '' : 's'}`);
  const r = finiteNumber(data.event_map_completed_r);
  if (r != null) parts.push(`${r} resistance rejection${r === 1 ? '' : 's'}`);
  const alt = finiteNumber(data.event_map_alternations);
  if (alt != null) parts.push(`${alt} alternation${alt === 1 ? '' : 's'}`);
  if (data.event_map_terminal_posture === 1) parts.push('ends engaging resistance');
  if (data.event_map_terminal_drift === 1) parts.push('ends drifting on support');
  return parts.join(' · ');
};

function ElectionTraceReadout({ trace }) {
  const shaped = shapeTrace(trace, { stages: TRACE_STAGE_LABELS, outcomes: ROOT_OUTCOME_LABELS });
  if (!shaped) {
    return <div style={{ ...mutedLine, marginTop: 8 }}>trace not captured for this scan</div>;
  }
  return (
    <div className="narrative-trace-well">
      {shaped.roots.map((root) => (
        <div key={root.id} style={{ marginBottom: 6 }}>
          <div>
            {`root ${root.climax ?? '—'} → ${root.ar ?? '—'}: ${root.outcome}`}
            {root.candidates ? ` · ${root.candidates} candidate framing${root.candidates === 1 ? '' : 's'}` : ''}
          </div>
          {root.refused.length > 0 && (
            <div style={{ paddingLeft: 12 }}>
              {root.refused.map((r) => `${r.count} refused at ${r.stage}`).join(' · ')}
            </div>
          )}
          {root.furthest && !root.furthest.passed && root.furthest.sentences.map((sentence) => (
            <div key={sentence} style={{ paddingLeft: 12 }}>{`closest framing died: ${sentence}`}</div>
          ))}
        </div>
      ))}
      {shaped.elected && (
        <div>
          {`elected: opens ${shaped.elected.start ?? '—'} · R ${fx(shaped.elected.R, 2, '—')} / S ${fx(shaped.elected.S, 2, '—')}`}
          {shaped.elected.nValid != null ? ` · ${shaped.elected.nValid} of ${shaped.elected.nCandidates ?? '—'} framings valid` : ''}
          {shaped.elected.rescued ? ' · rescued' : ''}
        </div>
      )}
    </div>
  );
}

// The read-reason vocabulary: about the READ (rails, story, posture), never
// recycled setup-skip reasons. Free choice, always skippable.
const READ_REASONS = ['rails', 'story', 'posture', 'phases', 'other'];

// One-tap concordance verdict on the ENGINE'S READ — a third axis (it judges
// the read, not the setup), bound verbatim to the payload's scan_identity
// triple and recorded through the reviews router's read-verdict path.
// Optimistic and never blocking. Council review 2026-08-05, findings 5+11:
// every async settle (the mount GET and the POST rollback) is guarded by the
// identity it was issued for — a stale resolution must never paint one
// ticker's verdict onto another, and a late GET must never stomp an
// optimistic write; failures surface through the shared toast channel and
// keep the composed reason; the disagree reason is an inline skippable chip
// row (window.prompt froze the chart the operator needs to look at).
function ReadVerdictControl({ ticker, scanIdentity }) {
  const scanDate = scanIdentity?.scan_date ?? null;
  const universeType = scanIdentity?.universe_type ?? null;
  const engineVersion = scanIdentity?.engine_config_version ?? null;
  const [verdict, setVerdict] = useState(null);
  const [note, setNote] = useState(null);
  const [reasonOpen, setReasonOpen] = useState(false);
  const [otherText, setOtherText] = useState('');
  const identityRef = useRef(null);
  const writeIssuedRef = useRef(false);

  useEffect(() => {
    const identity = `${ticker}|${scanDate}`;
    identityRef.current = identity;
    writeIssuedRef.current = false;
    setVerdict(null);
    setNote(null);
    setReasonOpen(false);
    setOtherText('');
    if (!ticker || !scanDate) return;
    const params = new URLSearchParams({ ticker, scan_date: scanDate });
    if (universeType) params.set('universe_type', universeType);
    fetch(`${API_BASE}/archive/reviews/read-verdict?${params.toString()}`)
      .then((response) => {
        if (!response.ok) throw new Error(`read-verdict GET ${response.status}`);
        return response.json();
      })
      .then((body) => {
        // Bail if the control moved on, or the operator already clicked —
        // the server's pre-write state must not repaint over a live write.
        if (identityRef.current !== identity || writeIssuedRef.current) return;
        setVerdict(body.verdict ?? null);
        setNote(body.note ?? null);
      })
      .catch((error) => {
        console.error(`Read-verdict fetch failed for ${ticker}`, error);
      });
  }, [ticker, scanDate, universeType]);

  const record = (next, nextNote) => {
    const identity = identityRef.current;
    const previous = verdict;
    const previousNote = note;
    writeIssuedRef.current = true;
    setVerdict(next);
    setNote(nextNote ?? null);
    fetch(`${API_BASE}/archive/reviews/read-verdict`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        ticker,
        scan_date: scanDate,
        universe_type: universeType,
        engine_config_version: engineVersion,
        verdict: next,
        note: nextNote ?? null,
      }),
    })
      .then((response) => { if (!response.ok) throw new Error(`read-verdict POST ${response.status}`); })
      .catch((error) => {
        console.error(`Read verdict failed for ${ticker}, reverting`, error);
        toast(`Read verdict for ${ticker} didn't save — reverted`, { tone: 'danger' });
        if (identityRef.current !== identity) return;   // paged away: never paint the old ticker's state here
        setVerdict(previous);
        setNote(previousNote);
      });
  };

  const disabled = !ticker || !scanDate;

  return (
    <div style={{ marginTop: 10 }}>
      <div
        style={{ display: 'flex', alignItems: 'center', gap: 6 }}
        title={disabled
          ? 'No scan identity for this view — the verdict must bind to an exact archived scan'
          : 'Judge the READ, not the setup: does the engine tell this chart the way you would?'}
      >
        <span style={{ fontSize: 11, color: 'var(--text-faint)' }}>The read:</span>
        <button
          type="button" disabled={disabled}
          className={`narrative-verdict-btn${verdict === 'agree' ? ' is-active' : ''}`}
          onClick={() => { setReasonOpen(false); record(verdict === 'agree' ? null : 'agree'); }}
        >
          tells it right
        </button>
        <button
          type="button" disabled={disabled}
          className={`narrative-verdict-btn${verdict === 'disagree' ? ' is-active' : ''}`}
          onClick={() => {
            if (verdict === 'disagree') { setReasonOpen(false); record(null); return; }
            // Record immediately — the reason is optional refinement, never a
            // gate; the chart stays live under the chip row.
            record('disagree', note);
            setReasonOpen(true);
          }}
        >
          reads it wrong
        </button>
      </div>
      {reasonOpen && verdict === 'disagree' && (
        <div style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 4, marginTop: 6 }}>
          <span style={{ fontSize: 11, color: 'var(--text-faint)' }}>what&apos;s off?</span>
          {READ_REASONS.map((reason) => (
            <button
              key={reason} type="button"
              className={`narrative-reason-chip${note === reason ? ' is-active' : ''}`}
              onClick={() => {
                if (reason === 'other') { setNote('other'); return; }
                record('disagree', reason);
                setReasonOpen(false);
              }}
            >
              {reason}
            </button>
          ))}
          {note === 'other' && (
            <input
              type="text" value={otherText} autoFocus
              className="narrative-reason-input" placeholder="what's off? (Enter)"
              onChange={(event) => setOtherText(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter') {
                  record('disagree', otherText.trim() || null);
                  setReasonOpen(false);
                }
                if (event.key === 'Escape') setReasonOpen(false);
              }}
            />
          )}
          <button
            type="button" className="narrative-reason-chip"
            title="Keep the verdict without a reason"
            onClick={() => setReasonOpen(false)}
          >
            skip
          </button>
        </div>
      )}
    </div>
  );
}

function NarrativePanel({ activeRegion, data, onRegionChange, scanIdentity, ticker }) {
  const [traceOpen, setTraceOpen] = useState(false);
  // Deliberate reset-on-cycle: the trace is diagnostic, consulted per chart —
  // paging Prev/Next must never carry an open trace into the next ticker.
  // Keyed to the TICKER (the modal's own activeRegion reset key), never the
  // data object: the store swaps object identity on a background refresh and
  // that must not snap a trace shut mid-read (council review 2026-08-05).
  useEffect(() => setTraceOpen(false), [ticker]);

  const status = narrativeStatus(data);
  // This wire never carried the narrative family (e.g. an artifact from
  // before the read shipped) — the panel can't say anything honest about the
  // row, so it says nothing at all (council F4: the old copy diagnosed
  // "predates the read" on rows that were measured).
  if (status === NARRATIVE_STATUS.NOT_CARRIED) return null;

  const pool = data?.elected_pool;
  const poolLabel = pool != null ? displayLabel(pool) : null;
  const glyphs = tapeGlyphs(data);
  const traceAvailable = data?.election_trace != null;
  // Both read-honesty caveats ride the one channel (narrativeRead owns the
  // composition): unreadable bars (NaN) and starved geometry (the zones
  // consume the box) each keep their zero from masquerading as the
  // junk-separator zero.
  const caveat = readCaveats(data);
  const counts = narrativeCountsLine(data);

  return (
    <section className="stock-lens-section">
      <div className="stock-lens-section-header">
        <span>The Engine&apos;s Read</span>
        {poolLabel ? <small title={pool === 'story'
          ? `Admitted by its own story read: ${data.story_admission_profile ?? '—'} (admission basis — the archived substrate is a separate read and may legally disagree)`
          : undefined}
        >{poolLabel}</small> : null}
      </div>
      {status === NARRATIVE_STATUS.NOT_MEASURED && (
        <div style={mutedLine}>{ABSENCE_COPY.not_measured}</div>
      )}
      {status === NARRATIVE_STATUS.EMPTY && (
        // The measured zero is a finding — but only when the tape could READ
        // the bars: the readability caveat keeps zero-by-unreadable from
        // masquerading as the junk-separator zero (council F10).
        <div style={mutedLine}>{caveat ? `${ABSENCE_COPY.empty} — ${caveat}` : ABSENCE_COPY.empty}</div>
      )}
      {status === NARRATIVE_STATUS.READY && (
        <>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {glyphs.map((glyph) => (
              <span
                key={glyph.id}
                className={`narrative-glyph${activeRegion === glyph.id ? ' is-active' : ''}${glyph.span ? '' : ' is-inert'}`}
                title={`${glyph.label}${glyph.span ? ` · ${glyph.span[0]} → ${glyph.span[1]}` : ' · chart anchor unavailable for this row'}${glyph.unknowable ? ' · not yet fixed (merge horizon open)' : ''}`}
                onMouseEnter={glyph.span ? () => onRegionChange(glyph.id) : undefined}
                onMouseLeave={glyph.span ? () => onRegionChange(null) : undefined}
                onFocus={glyph.span ? () => onRegionChange(glyph.id) : undefined}
                onBlur={glyph.span ? () => onRegionChange(null) : undefined}
                tabIndex={glyph.span ? 0 : undefined}
              >
                {glyph.token}
              </span>
            ))}
          </div>
          <div style={{ ...mutedLine, marginTop: 8 }}>
            {caveat ? `${counts}${counts ? ' · ' : ''}${caveat}` : counts}
          </div>
        </>
      )}
      {status !== NARRATIVE_STATUS.NOT_MEASURED && (
        <button
          type="button"
          className="narrative-trace-toggle"
          onClick={() => setTraceOpen((open) => !open)}
        >
          {`Election trace${traceAvailable ? '' : ' (not captured)'} ${traceOpen ? '▴' : '▾'}`}
        </button>
      )}
      {traceOpen && <ElectionTraceReadout trace={data?.election_trace} />}
      <ReadVerdictControl
        key={`${ticker}|${scanIdentity?.scan_date ?? ''}`}
        ticker={ticker}
        scanIdentity={scanIdentity}
      />
    </section>
  );
}

export default function ScreenerStockLens({ activeRegion, data, earnings, interval = 'D', onRegionChange, scanIdentity = null, ticker = null }) {
  const showDailyStructure = interval === 'D';
  // The phase spans belong to the DAILY read — on a weekly/monthly pane there is
  // nothing on screen for them to point at, so the story rows keep their grades
  // and drop their highlights rather than lighting bars that aren't there.
  const regions = showDailyStructure ? buildPhaseRegions(data) : [];
  return (
    <div className="stock-lens">
      {/* The protagonist leads (operator 2026-08-12): the fused read is the
          first and widest thing in the panel; the measured grid and the
          narrative sit under it. */}
      <SetupStoryPanel
        data={data}
        note={triggerRead(distanceToTriggerPct(data))}
        onRegionChange={onRegionChange}
        regions={regions}
      />
      <div className="stock-lens-bottom">
        <TechnicalReadGrid data={data} earnings={earnings} />
        {showDailyStructure ? (
          <NarrativePanel
            activeRegion={activeRegion}
            data={data}
            onRegionChange={onRegionChange}
            scanIdentity={scanIdentity}
            ticker={ticker}
          />
        ) : null}
      </div>
    </div>
  );
}
