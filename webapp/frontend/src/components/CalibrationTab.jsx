import { useEffect, useMemo, useReducer, useRef, useState } from 'react';
import { CrosshairMode } from 'lightweight-charts';
import CandleChart from './CandleChart';
import CalibrationMarkingBar from './CalibrationMarkingBar';
import CalibrationMarksList from './CalibrationMarksList';
import CalibrationSaveBar from './CalibrationSaveBar';
import CalibrationTickerStrip from './CalibrationTickerStrip';
import useCalibrationChart from '../hooks/useCalibrationChart';
import useCalibrationMarks from '../hooks/useCalibrationMarks';
import useEngineRead from '../hooks/useEngineRead';
import { CHART_FONT, baseChartOptions, surfaceOf } from './chartTheme';
import { attachCalibrationDraw } from './calibrationDraw';
import { attachHoverHighlight } from './calibrationHover';
import {
  chartTimeToIso,
  draftComplete,
  emptyDraft,
  frameKeyOf,
  initialMarkingState,
  markPayloadFromDraft,
  markingReducer,
} from '../utils/calibrationMarking';
import { parseWorklist, worklistLabel } from '../utils/calibrationWorklist';

// The Calibration page (Calibration at Scale, Task 10): pull up ANY ticker at
// ANY historical as-of date on Chrollo's own data. The chart is the
// protagonist — one compact command band above a fixed, never-shifting chart
// pane whose lookup states (blank / loading / failure classes / ideal) render
// INSIDE the pane so the operator's eyes never lose their place between the
// dozens of lookups a marking sitting takes. The interactive marking layer
// (click-to-place rails, worklist loop, verdicts) lands on this shell next
// (Tasks 11-12); this page deliberately owns all its state — nothing in
// AppShell, no app-level context.
const fx = (v, d) => ((v == null || !Number.isFinite(Number(v))) ? '—' : Number(v).toFixed(d));

const FAILURE_HINTS = {
  bad_ticker: 'Tickers are 1-10 chars: A-Z, 0-9, dot or dash.',
  bad_date: 'Dates are YYYY-MM-DD, 2000 or later.',
  future_date: 'Pick a past session.',
  no_data: 'Unknown or delisted ticker — or the vendor hiccuped; retry once.',
  no_bars_at_date: 'This ticker has no history at that date; try a later one.',
  network: 'Start the dashboard service, then retry.',
  service_stale: 'Run update_dashboard.bat to load the new backend, then retry.',
  freeze_failed: 'Check disk space / calibration_frames permissions, then retry.',
  unknown: 'Retry once; if it persists, check the service log.',
};

function CalibrationTab() {
  const { chartData, loading, failure, load } = useCalibrationChart();
  const [ticker, setTicker] = useState('');
  const [asOf, setAsOf] = useState('');

  // Marking layer (Task 11): ONE state value (tool / span anchor / draft)
  // in a pure reducer; the chart is a retained surface — the controller
  // attaches once per chart build (onReady) and draft edits update price
  // lines and markers WITHOUT rebuilding, so zoom survives every click.
  const [marking, dispatchMarking] = useReducer(markingReducer, undefined,
    () => initialMarkingState());
  const markingRef = useRef(marking);
  markingRef.current = marking;
  const chartApiRef = useRef(null);   // { series, draw } while a chart is up
  const draftsRef = useRef(new Map()); // frameKey -> draft (per-frame, per-sitting)

  // Drafts are structurally keyed to the frame they were drawn on: scrubbing
  // to another session swaps to THAT frame's draft (or a fresh one), never
  // bleeding rails across frames.
  useEffect(() => {
    const key = frameKeyOf(chartData);
    if (key !== markingRef.current.frameKey) {
      dispatchMarking({ type: 'load', frameKey: key,
                        draft: draftsRef.current.get(key) ?? null });
      setLabel('');
      setNote('');
    }
  }, [chartData]);

  // Stash the draft under ITS OWN frame key (they travel together in state,
  // so a chart swap can never stash a draft under the wrong frame).
  useEffect(() => {
    if (marking.frameKey) draftsRef.current.set(marking.frameKey, marking.draft);
  }, [marking.frameKey, marking.draft]);

  // Bars by date, for snap-to-extreme rail placement.
  const barsByDate = useMemo(() => {
    const map = new Map();
    for (const c of chartData?.candles ?? []) map.set(c.time, c);
    return map;
  }, [chartData]);
  const barsRef = useRef(barsByDate);
  barsRef.current = barsByDate;

  // Save workflow (Task 12): marks CRUD + label/note + worklist queue.
  const { marks, saving, saveError, tally, summary,
          refresh, refreshSummary, saveMark, removeMark } = useCalibrationMarks();
  useEffect(() => { refreshSummary(); },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    []);
  const [label, setLabel] = useState('');
  const [note, setNote] = useState('');
  const [wlItems, setWlItems] = useState([]);
  const [wlIndex, setWlIndex] = useState(0);

  useEffect(() => { refresh(chartData?.ticker); },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [chartData?.ticker]);

  // The engine overlay (default OFF, explicit toggle): the operator marks
  // FIRST and peeks after — anchoring on the engine read corrupts the ground
  // truth (council watchpoint). What it shows is the agreement harness's own
  // projection, so "what the engine thinks" here = what agreement scores.
  const [engineOn, setEngineOn] = useState(false);
  const { engineRead, engineStatus } = useEngineRead(chartData, engineOn);

  // Saved marks drawn on THIS frame's chart, always (operator bug report
  // 2026-07-11: with only the draft rendered, saving and starting the next
  // mark visually erased everything). The mark being edited is excluded —
  // it IS the draft, already drawn in the operator hue.
  const savedForFrame = useMemo(() => {
    if (!chartData) return [];
    return marks.filter((m) => m.as_of_date === chartData.as_of_session
      && m.verdict === 'box' && m.id !== marking.editingId);
  }, [marks, chartData, marking.editingId]);

  // Retained redraw, deliberately dependency-free: it runs after every
  // commit (including the child chart effect's rebuilds), the draw is
  // idempotent and cheap, and no state combination can leave the chart
  // stale. Mythril while drawing; the reserved operator hue once the draft
  // IS a saved mark being corrected (Task 13 color doctrine).
  useEffect(() => {
    const api = chartApiRef.current;
    if (!api) return;
    api.draw.update({
      draft: marking.draft,
      spanAnchor: marking.spanAnchor,
      committed: marking.editingId != null,
      saved: savedForFrame,
      engine: engineOn ? engineRead : null,
    });
    api.hover.setArmed(marking.tool !== 'idle');
  });

  const canSave = !!chartData && draftComplete(marking.draft);

  const worklistStep = (delta) => {
    if (!wlItems.length) return;
    const next = Math.min(Math.max(wlIndex + delta, 0), wlItems.length - 1);
    setWlIndex(next);
    const entry = wlItems[next];
    setTicker(entry.ticker);
    lookup(entry.ticker, entry.asOf);
  };

  const save = async () => {
    if (!canSave || saving) return;
    const payload = markPayloadFromDraft(marking.draft, chartData, { label, note });
    const saved = await saveMark(payload, marking.editingId);
    if (!saved) return; // draft stays intact — a failed save never loses work
    dispatchMarking({ type: 'edit-mark', mark: saved });
    if (wlItems.length && wlIndex < wlItems.length - 1) worklistStep(1);
  };

  // One-keystroke negatives, gated on nothing: the frame itself IS the
  // assertion ("no structure here" / "the engine's read here is wrong").
  const saveNegative = async (verdict) => {
    if (!chartData || saving) return;
    const payload = markPayloadFromDraft(
      { ...emptyDraft(), verdict }, chartData, { label, note });
    const saved = await saveMark(payload, null);
    if (saved && wlItems.length && wlIndex < wlItems.length - 1) worklistStep(1);
  };

  const editMark = (mark) => {
    setLabel(mark.label ?? '');
    setNote(mark.note ?? '');
    dispatchMarking({ type: 'edit-mark', mark });
  };

  // Keyboard loop (skipped while typing in any field): tools b/r/s/x,
  // events c/l/t, negatives n/w, scrub ,/. , Enter saves, Escape disarms.
  const keyDeps = useRef({});
  keyDeps.current = { save, saveNegative };
  const scrubRef = useRef(() => {});
  useEffect(() => {
    const onKey = (e) => {
      const tag = e.target?.tagName;
      if (tag === 'INPUT' || tag === 'SELECT' || tag === 'TEXTAREA') return;
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      const k = e.key.toLowerCase();
      const tool = { r: 'rail-r', s: 'rail-s', x: 'span',
                     c: 'event:phase_c', l: 'event:lps', t: 'event:spring_test' }[k];
      if (tool) { dispatchMarking({ type: 'tool', tool }); e.preventDefault(); return; }
      if (e.key === 'Escape') { dispatchMarking({ type: 'tool', tool: 'idle' }); return; }
      const d = keyDeps.current;
      if (k === 'n') { d.saveNegative('no_structure'); e.preventDefault(); return; }
      if (k === 'w') { d.saveNegative('engine_wrong'); e.preventDefault(); return; }
      if (k === 'e') { setEngineOn((v) => !v); e.preventDefault(); return; }
      if (e.key === 'Enter') { d.save(); return; }
      if (e.key === ',') { scrubRef.current(-1); return; }
      if (e.key === '.') { scrubRef.current(1); }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  // On success the date input snaps to the RESOLVED session, so input,
  // provenance strip and chart always name the same session; on failure the
  // input keeps whatever the operator typed (nothing is poisoned).
  const lookup = async (t, date) => {
    const result = await load(t, date);
    if (result) setAsOf(result.as_of_session);
  };

  const submit = (event) => {
    event?.preventDefault();
    if (ticker.trim() && asOf) lookup(ticker, asOf);
  };

  // Day-scrub: step the SERVER-NAMED adjacent sessions (never guessed
  // calendar days — a Friday's "next day" is Monday, not a Saturday that
  // resolves straight back to Friday). Cached revisits are instant; each
  // NEW session costs one bounded fetch (it also freezes that session's
  // frame server-side, which a mark needs anyway).
  const scrub = (direction) => {
    const target = direction < 0 ? chartData?.prev_session : chartData?.next_session;
    if (target) lookup(chartData.ticker, target);
  };
  scrubRef.current = scrub;

  const spec = useMemo(() => ({
    chartOptions: (container) => ({
      ...baseChartOptions('modal', container.clientWidth, container.clientHeight),
      handleScroll: true,
      handleScale: true,
      // Normal, not the library-default Magnet: Magnet snaps the crosshair
      // to each bar's CLOSE, so the line the operator sees jumps away from
      // the mouse while clicks land at the true pointer position — the
      // "cursor follows at some margin" placement bug (operator, 2026-07-11).
      crosshair: { mode: CrosshairMode.Normal },
    }),
    candles: chartData?.candles,
    volumes: chartData?.volumes,
    showVolume: true,
    onReady: (chart, series) => {
      // The marking controller: click placement + retained draft drawing.
      // The handler reads the CURRENT marking state through a ref (onReady
      // runs once per chart build; the tool changes many times per build).
      const draw = attachCalibrationDraw(series);
      const hover = attachHoverHighlight(chart, series);
      chartApiRef.current = { series, draw, hover };
      const onClick = (param) => {
        if (markingRef.current.tool === 'idle') return;
        if (!param?.point || param.time == null) return;
        const price = series.coordinateToPrice(param.point.y);
        const date = chartTimeToIso(param.time);
        if (price == null || !Number.isFinite(price) || !date) return;
        dispatchMarking({ type: 'chart-click', date,
                          price: Number(price.toFixed(4)),
                          bar: barsRef.current.get(date) });
      };
      chart.subscribeClick(onClick);
      return () => {
        chart.unsubscribeClick(onClick);
        hover.detach();
        draw.detach();
        chartApiRef.current = null;
      };
    },
    onResize: (chart, container) => chart.applyOptions({
      width: container.clientWidth, height: container.clientHeight,
    }),
    deps: [chartData],
  }), [chartData]);

  return (
    <div className="calibration-page" style={{ display: 'flex', flexDirection: 'column', gap: 10, height: '100%' }}>
      <form className="instrument-tile screener-command-band" onSubmit={submit}>
        <span style={{ fontSize: 10, fontWeight: 600, letterSpacing: '0.08em',
                       textTransform: 'uppercase', color: 'var(--text-faint)' }}>
          Calibration
        </span>
        <input
          value={ticker}
          onChange={(e) => setTicker(e.target.value.toUpperCase())}
          placeholder="Ticker"
          aria-label="Ticker"
          style={{ width: 110, fontFamily: 'inherit' }}
        />
        <input
          type="date"
          value={asOf}
          onChange={(e) => setAsOf(e.target.value)}
          aria-label="As-of date"
        />
        <button type="submit" disabled={loading || !ticker.trim() || !asOf}>
          {loading ? 'Loading…' : 'Load'}
        </button>
        {chartData && (
          <>
            <button type="button" onClick={() => scrub(-1)}
                    disabled={loading || !chartData.prev_session}
                    title={chartData.prev_session ? 'Previous session' : 'At the left edge of the fetched window'}>
              ◀ day
            </button>
            <button type="button" onClick={() => scrub(1)}
                    disabled={loading || !chartData.next_session}
                    title={chartData.next_session ? 'Next session' : 'No later session in the fetched window'}>
              day ▶
            </button>
            <button type="button" aria-pressed={engineOn}
                    onClick={() => setEngineOn((v) => !v)}
                    title="Overlay the engine's read of this frame (the agreement harness's own lens) [e]. Mark FIRST, peek after — anchoring on the engine corrupts the ground truth.">
              Engine
            </button>
            {/* Provenance figures change on every scrub — mono + tabular so
                the eye can hold position across adjacent sessions. */}
            <span style={{ color: 'var(--text-muted)', fontFamily: CHART_FONT,
                           fontVariantNumeric: 'tabular-nums', fontSize: 11,
                           whiteSpace: 'nowrap' }}>
              {chartData.ticker} @ {chartData.as_of_session} · close {fx(chartData.anchor_close, 2)}
              {' '}· {chartData.bar_count} bars · {chartData.data_regime}
            </span>
          </>
        )}
      </form>

      <CalibrationMarkingBar
        state={marking}
        dispatch={dispatchMarking}
        disabled={!chartData}
        asOfSession={chartData?.as_of_session}
      />

      <CalibrationSaveBar
        disabled={!chartData}
        canSave={canSave}
        saving={saving}
        editingId={marking.editingId}
        label={label}
        onLabel={setLabel}
        note={note}
        onNote={setNote}
        onSave={save}
        onNewMark={() => dispatchMarking({ type: 'clear' })}
        onNegative={saveNegative}
        saveError={saveError}
        tally={tally}
        worklist={wlItems}
        worklistLabelText={worklistLabel(wlItems, wlIndex)}
        onWorklistText={(text) => { setWlItems(parseWorklist(text)); setWlIndex(0); }}
        onWorklistStep={worklistStep}
      />

      <div className="instrument-well"
           style={{ flex: 1, minHeight: 420, position: 'relative',
                    borderRadius: 8, overflow: 'hidden' }}>
        {chartData ? (
          <>
            <CandleChart
              spec={spec}
              className="calibration-chart"
              style={{ position: 'absolute', inset: 0 }}
              errorFallback={<PaneMessage title="Chart failed to draw" body="Reload the lookup." />}
              emptyFallback={<PaneMessage title="No drawable bars" body="Every bar in this window was non-finite." />}
            />
            {failure && (
              // A failed step never wipes the working chart — the last good
              // frame stays up and the failure rides above it, in danger ink
              // so it registers peripherally mid-sitting.
              <div style={{
                position: 'absolute', top: 8, left: 8, right: 8, zIndex: 5,
                padding: '6px 10px', borderRadius: 6, fontSize: 12,
                border: `1px solid ${surfaceOf('modal').border}`,
                borderLeft: '2px solid var(--danger)',
                background: 'rgba(23, 25, 34, 0.92)',
              }}>
                Lookup failed — {failure.class}. {paneBody(false, failure)}
              </div>
            )}
            {engineOn && (
              // What the engine thinks, in words — rails land on the chart in
              // engine ink; this chip carries the session/no-read verdict.
              <div style={{
                position: 'absolute', top: 8, right: 8, zIndex: 4,
                fontSize: 11, fontFamily: CHART_FONT, color: 'var(--text-muted)',
                fontVariantNumeric: 'tabular-nums',
                background: 'rgba(23, 25, 34, 0.85)', padding: '3px 8px',
                borderRadius: 6,
              }}>
                {engineLine(engineRead, engineStatus)}
              </div>
            )}
            {chartData.warnings?.length > 0 && (
              // Warnings live INSIDE the pane (bottom edge) — the chart's
              // geometry never shifts when a scrub step gains or loses one.
              <div style={{
                position: 'absolute', bottom: 8, left: 8, zIndex: 5,
                fontSize: 11, color: 'var(--accent-yellow)',
                background: 'rgba(23, 25, 34, 0.85)', padding: '3px 8px',
                borderRadius: 6,
              }}>
                {chartData.warnings.map((w) => <div key={w}>{w}</div>)}
              </div>
            )}
          </>
        ) : (
          <PaneMessage
            title={paneTitle(loading, failure)}
            body={paneBody(loading, failure)}
            danger={!loading && !!failure}
          />
        )}
      </div>

      <CalibrationMarksList
        marks={marks}
        editingId={marking.editingId}
        onEdit={editMark}
        onDelete={(id) => removeMark(id, chartData?.ticker)}
      />

      <CalibrationTickerStrip
        summary={summary}
        activeTicker={chartData?.ticker}
        onPick={(t, latestAsOf) => { setTicker(t); lookup(t, latestAsOf); }}
      />
    </div>
  );
}

function engineLine(engineRead, engineStatus) {
  if (engineStatus === 'loading') return 'engine: reading…';
  if (engineStatus) return `engine: ${engineStatus}`;
  if (!engineRead) return 'engine: —';
  if (!engineRead.elected) {
    return `engine: no read${engineRead.reason ? ` — ${engineRead.reason}` : ''}`;
  }
  const snap = engineRead.snapped
    ? ` (snapped −${engineRead.snapped})` : '';
  return `engine R ${fx(engineRead.R, 2)} / S ${fx(engineRead.S, 2)}`
    + ` · from ${engineRead.box_start_date} @ ${engineRead.eval_session}${snap}`;
}

function paneTitle(loading, failure) {
  if (loading) return 'Loading…';
  if (failure) return `Lookup failed — ${failure.class}`;
  return 'Pull up a chart';
}

function paneBody(loading, failure) {
  if (loading) return 'Fetching candles through the provider (bounded).';
  if (failure) {
    const hint = FAILURE_HINTS[failure.class];
    return hint ? `${failure.message}. ${hint}` : failure.message;
  }
  return 'Enter a ticker and an as-of date. The chart renders on Chrollo’s own '
    + 'data — marks drawn here are born on the exact frame the engine replays.';
}

function PaneMessage({ title, body, danger = false }) {
  // The pane states wear the modal chart's OWN skin (imported, never
  // hand-copied hexes) so blank/loading/failure and the drawn chart read as
  // one surface; a failure gets one restrained semantic cue.
  const skin = surfaceOf('modal');
  return (
    <div style={{
      position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column',
      alignItems: 'center', justifyContent: 'center', gap: 6,
      border: `1px solid ${skin.border}`, borderRadius: 8,
      background: skin.background,
    }}>
      <div style={{ fontWeight: 600,
                    color: danger ? 'var(--danger)' : 'var(--text-main)' }}>
        {title}
      </div>
      <div style={{ fontSize: 12, color: 'var(--text-faint)', maxWidth: 520,
                    textAlign: 'center' }}>
        {body}
      </div>
    </div>
  );
}

export default CalibrationTab;
