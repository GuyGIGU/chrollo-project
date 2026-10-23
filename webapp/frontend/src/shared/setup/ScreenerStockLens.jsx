import { useEffect, useState } from 'react';

import SetupStoryPanel from './SetupStoryPanel';
import { buildPhaseRegions } from '../charts/chartPhaseOverlay';
import {
  ABSENCE_COPY,
  NARRATIVE_STATUS,
  narrativeStatus,
  readCaveats,
  shapeTrace,
  tapeGlyphs,
} from './narrativeRead';
import ReadVerdictControl from './ReadVerdictControl';
import {
  ROOT_OUTCOME_LABELS,
  TRACE_STAGE_LABELS,
  TREND_STATE_LABELS,
  displayLabel,
} from '../presentation/wireVocabulary';
import { API_BASE } from '../../api/base';
import { EMPTY, fx, fmtDateShort, fmtDay, fmtPct } from '../formatting/format';
import { triggerDistanceFrac } from './triggerProximity.js';
import { leadershipCells, stageCells } from './leadershipRead';
import { fundamentalsCells, fundamentalsNote, hasFundamentalsRead } from './fundamentalsRead';
import FundamentalsSheet from './FundamentalsSheet';
import { hasFundamentalsSheet } from './fundamentalsSheetRead';
import { hasVolumeRead, volumeCells } from './volumeRead';
import { twoEyesTechnicalCells } from './twoEyesStory';

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

const sectorLabel = (data) => data?.sector_etf || data?.sector_name || EMPTY;

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
// Every cell is a measured structural fact from the scan payload — no invented
// data; the fundamentals have their own page. A row the two-eyes reader wrote
// carries none of the old engine's counts (they printed as dashes, Tue
// 13/10/2026): it shows its own read's facts instead.
function TechnicalReadGrid({ data, earnings, regions }) {
  const contractions = finiteNumber(data.contraction_count);
  const earn = earningsDisplay(earnings);
  const earningsCell = { k: 'Earnings', v: earn.value, tone: earn.tone, title: earn.title };

  const cells = data.two_eyes ? [...twoEyesTechnicalCells(data, regions), earningsCell] : [
    { k: 'Box width', v: pct(boxWidthPct(data)) },
    { k: 'Base length', v: bars(data.base_len) },
    { k: 'LPS pullback', v: bars(data.lps_len) },
    { k: 'Contractions', v: contractions == null ? '-' : String(contractions) },
    { k: displayLabel('traversal_density'), v: fx(data.traversal_density, 2, '-') },
    earningsCell,
  ];

  return <LensGridSection title="Technical read" note={data.setup || ''} cells={cells} />;
}

// The leadership read (2026-10-02): the STOCK, kept apart from the setup's grade —
// RS rating, trend template and dollar volume, where the stock stands in its
// life cycle (2026-10-03: off the 52-week low, the 200-day's month), plus the
// two stock traits that used to sit in the technical read (ADR and sector).
function LeadershipGrid({ data }) {
  const cells = [
    ...leadershipCells(data),
    ...stageCells(data),
    { k: 'ADR', v: fmtPct(data.adr_pct) },
    { k: 'Sector', v: sectorLabel(data), tone: 'var(--accent-blue)', title: data?.sector_name || undefined },
  ];
  return <LensGridSection title="Leadership" note="the stock, not the setup" cells={cells} />;
}

// The fundamentals read (2026-10-03): the business beside the stock, apart from
// the setup's grade. The note names the quarter the growth numbers describe.
// From 2026-10-12 a scan carries the whole sheet and the fundamental grade, and
// from 2026-10-13 the sheet is the panel's second page (LensPageTabs); an older
// payload keeps the four-number grid here.
function FundamentalsGrid({ data }) {
  if (hasFundamentalsSheet(data) || !hasFundamentalsRead(data)) return null;
  return <LensGridSection title="Fundamentals" note={fundamentalsNote(data)} cells={fundamentalsCells(data)} />;
}

const LENS_PAGES = [
  { key: 'read', label: 'The read' },
  { key: 'fundamentals', label: 'Fundamentals' },
];

// The panel's two pages (Tue 13/10/2026, his "show the fundamental card as a
// second page rather then another block below"): F flips them, as on a card.
function LensPageTabs({ page, onPageChange }) {
  return (
    <div className="lens-page-tabs" role="tablist" aria-label="Panel page">
      {LENS_PAGES.map((tab) => (
        <button
          aria-selected={page === tab.key}
          className={`lens-page-tab${page === tab.key ? ' is-active' : ''}`}
          key={tab.key}
          onClick={() => onPageChange(tab.key)}
          role="tab"
          title={`${tab.label} (F flips the page)`}
          type="button"
        >
          {tab.label}
        </button>
      ))}
      <span className="lens-page-hint">F</span>
    </div>
  );
}

// Volume at key points (2026-10-04): the LPS pullback and the Phase C spring
// against the 50-day average — his key points, read with price, never graded.
function VolumeGrid({ data }) {
  if (!hasVolumeRead(data)) return null;
  return <LensGridSection title="Volume at key points" note="against the 50-day average" cells={volumeCells(data)} />;
}

function LensGridSection({ title, note, cells }) {
  return (
    <section className="stock-lens-section">
      <div className="stock-lens-section-header">
        <span>{title}</span>
        <small>{note}</small>
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

// "fired Wed 11/02/2026, crossed Thu 12/02/2026" (the final method, point 23): a
// lookup of the two dates the archive already stores for this ticker's latest
// fire (scan_date, trigger_date), never a new pick. Silent until it arrives or
// when the ticker was never archived; a backend hiccup logs and shows nothing.
function FiredCrossedLine({ ticker }) {
  const [row, setRow] = useState(null);
  useEffect(() => {
    setRow(null);
    if (!ticker) return undefined;
    let live = true;
    const params = new URLSearchParams({
      ticker, universe_type: 'all', limit: '1', sort_by: 'scan_date', sort_dir: 'desc',
    });
    fetch(`${API_BASE}/archive/setups?${params.toString()}`)
      .then((res) => (res.ok ? res.json() : null))
      .then((body) => { if (live) setRow(Array.isArray(body) && body.length ? body[0] : null); })
      .catch((err) => { console.warn('fired/crossed', ticker, err); });
    return () => { live = false; };
  }, [ticker]);
  if (!row) return null;
  const crossed = row.trigger_date ? `crossed ${fmtDay(row.trigger_date)}` : 'not crossed yet';
  return (
    <div className="stock-lens-fired" style={{ color: 'var(--text-faint)', fontSize: 11, padding: '0 2px 4px' }}>
      fired {fmtDay(row.scan_date)}, {crossed}
    </div>
  );
}

// `story`: false when the host draws "Why It Stands Out" in a block of its own (the lens page, Thu 16/10/2026).
export default function ScreenerStockLens({
  activeRegion, data, earnings, interval = 'D', onPageChange = null, onRegionChange, page = 'read',
  scanIdentity = null, ticker = null,
 story = true }) {
  const showDailyStructure = interval === 'D';
  // The phase spans belong to the DAILY read — on a weekly/monthly pane there is
  // nothing on screen for them to point at, so the story rows keep their grades
  // and drop their highlights rather than lighting bars that aren't there. The
  // technical read counts its days on the daily bars whichever pane is up.
  const dailyRegions = buildPhaseRegions(data);
  const regions = showDailyStructure ? dailyRegions : [];
  const tabs = onPageChange ? <LensPageTabs onPageChange={onPageChange} page={page} /> : null;

  if (page === 'fundamentals' && hasFundamentalsSheet(data)) {
    return (
      <div className="stock-lens">
        {tabs}
        <FundamentalsSheet data={data} />
      </div>
    );
  }

  // The narrative panel speaks the OLD reader's tape; a two-eyes row is "not
  // carried" there, so its read takes the whole width in two even columns.
  const narrative = showDailyStructure && !data?.two_eyes;
  return (
    <div className="stock-lens">
      {tabs}
      {/* The protagonist leads (operator 2026-08-12): the fused read is the
          first and widest thing in the panel; the measured grid and the
          narrative sit under it. */}
      {story ? (
        <SetupStoryPanel
          data={data}
          note={triggerRead(distanceToTriggerPct(data))}
          onRegionChange={onRegionChange}
          regions={regions}
        />
      ) : null}
      {ticker ? <FiredCrossedLine ticker={ticker} /> : null}
      {showDailyStructure && data?.two_eyes ? (
        <section className="stock-lens-section">
          <ReadVerdictControl ticker={ticker} scanIdentity={scanIdentity} />
        </section>
      ) : null}
      {narrative ? (
        <div className="stock-lens-bottom">
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10, minWidth: 0 }}>
            <LeadershipGrid data={data} />
            <FundamentalsGrid data={data} />
            <TechnicalReadGrid data={data} earnings={earnings} regions={dailyRegions} />
            <VolumeGrid data={data} />
          </div>
          <NarrativePanel
            activeRegion={activeRegion}
            data={data}
            onRegionChange={onRegionChange}
            scanIdentity={scanIdentity}
            ticker={ticker}
          />
        </div>
      ) : (
        <div className="stock-lens-bottom is-even">
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10, minWidth: 0 }}>
            <TechnicalReadGrid data={data} earnings={earnings} regions={dailyRegions} />
            <VolumeGrid data={data} />
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10, minWidth: 0 }}>
            <LeadershipGrid data={data} />
            <FundamentalsGrid data={data} />
          </div>
        </div>
      )}
    </div>
  );
}
