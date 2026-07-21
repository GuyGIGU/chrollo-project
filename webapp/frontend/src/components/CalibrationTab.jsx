import { useEffect, useMemo, useReducer, useRef, useState } from 'react';
import { CrosshairMode } from 'lightweight-charts';
import CandleChart from './CandleChart';
import CalibrationMarkingBar from './CalibrationMarkingBar';
import CalibrationMarksList from './CalibrationMarksList';
import CalibrationSaveBar from './CalibrationSaveBar';
import CalibrationRail from './CalibrationRail';
import useCalibrationChart from '../hooks/useCalibrationChart';
import useCalibrationMarks from '../hooks/useCalibrationMarks';
import useEngineRead from '../hooks/useEngineRead';
import useMarkAgreement from '../hooks/useMarkAgreement';
import useMarkFired from '../hooks/useMarkFired';
import useTriggerGrade from '../hooks/useTriggerGrade';
import { CHART_FONT, baseChartOptions, surfaceOf } from './chartTheme';
import { attachCalibrationDraw } from './calibrationDraw';
import { attachHoverHighlight } from './calibrationHover';
import { attachAsOfDivider } from './calibrationAsOfLine';
import {
  chartTimeToIso,
  draftComplete,
  draftStarted,
  effectiveSpan,
  frameKeyOf,
  initialMarkingState,
  markPayloadFromDraft,
  markingReducer,
  saveNeeds,
  snapTrigger,
} from '../utils/calibrationMarking';

// The Calibration page (Calibration at Scale, Task 10): pull up ANY ticker at
// ANY historical as-of date on Chrollo's own data. The chart is the
// protagonist — one compact command band above a fixed, never-shifting chart
// pane whose lookup states (blank / loading / failure classes / ideal) render
// INSIDE the pane so the operator's eyes never lose their place between the
// dozens of lookups a marking sitting takes. The interactive marking layer
// (click-to-place rails, the per-setup rail, one-click engine test) sits on
// this shell; this page deliberately owns all its state — nothing in
// AppShell, no app-level context.
const fx = (v, d) => ((v == null || !Number.isFinite(Number(v))) ? '—' : Number(v).toFixed(d));

const FAILURE_HINTS = {
  bad_ticker: 'Tickers are 1-10 chars: A-Z, 0-9, dot or dash.',
  bad_date: 'Dates are YYYY-MM-DD, 2000 or later.',
  future_date: 'Pick a past session.',
  rate_limited: 'The data vendor is briefly throttling — any loaded chart stays up; wait a few seconds and retry.',
  no_data: 'Unknown/delisted ticker — or the vendor is briefly throttling; wait a moment and retry.',
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

  // Drafts are structurally keyed to the frame they were drawn on: loading
  // another session swaps to THAT frame's draft (or a fresh one), never
  // bleeding rails across frames.
  useEffect(() => {
    const key = frameKeyOf(chartData);
    if (key !== markingRef.current.frameKey) {
      dispatchMarking({ type: 'load', frameKey: key,
                        draft: draftsRef.current.get(key) ?? null });
      setLabel('');
      setNote('');       // the note is per-setup — it never follows the eye to a new frame
      clearConflict();   // a parked overwrite must not follow the eye to a new frame
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chartData]);

  // Stash the draft under ITS OWN frame key (they travel together in state,
  // so a chart swap can never stash a draft under the wrong frame).
  useEffect(() => {
    if (marking.frameKey) draftsRef.current.set(marking.frameKey, marking.draft);
  }, [marking.frameKey, marking.draft]);

  // A parked "Update existing" holds the geometry AS IT WAS when it collided;
  // the moment the operator redraws, that snapshot is stale — drop the
  // conflict so a later click can't write yesterday's rails. Re-Save re-parks
  // with the current draft.
  useEffect(() => {
    if (conflict) clearConflict();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [marking.draft]);

  // Bars by date, for snap-to-extreme rail placement.
  const barsByDate = useMemo(() => {
    const map = new Map();
    for (const c of chartData?.candles ?? []) map.set(c.time, c);
    return map;
  }, [chartData]);
  const barsRef = useRef(barsByDate);
  barsRef.current = barsByDate;

  // Save workflow (Task 12): marks CRUD + label.
  const { marks, saving, saveError, tally, setups, conflict,
          refresh, refreshSummary, saveMark, resolveConflict,
          clearConflict, removeMark, removeSetup } = useCalibrationMarks();
  useEffect(() => { refreshSummary(); },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    []);
  const [label, setLabel] = useState('');
  // The operator's per-setup annotation (why the engine might miss this setup,
  // or what would make it hit) — carried on the mark's `note` column, purpose-
  // built here (operator ask 2026-07-21). Loaded when a saved mark is edited,
  // cleared when the frame changes, surfaced back in the rail, and read when the
  // engine is measured against the mark.
  const [note, setNote] = useState('');
  // The data-restatement notice sits at the pane's bottom edge, over the date
  // axis — so it is dismissible (operator 2026-07-21). A new frame re-shows its
  // own warnings (they are per-frame facts, not a permanent preference).
  const [warningsOpen, setWarningsOpen] = useState(true);
  useEffect(() => { setWarningsOpen(true); }, [chartData?.frame_digest]);
  // A refused mark placement's reason — a geometry mark clicked PAST the as-of
  // line (only what was observed by then is markable), or a Trigger clicked
  // before as-of / at-or-before the last LPS bar (the buy is the forward entry).
  // Shown as a transient chip, cleared when the tool or frame changes.
  const [placeNotice, setPlaceNotice] = useState(null);
  useEffect(() => { setPlaceNotice(null); }, [marking.tool, chartData?.frame_digest]);

  useEffect(() => { refresh(chartData?.ticker); },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [chartData?.ticker]);

  // The engine overlay (default OFF, explicit toggle): the operator marks
  // FIRST and peeks after — anchoring on the engine read corrupts the ground
  // truth (council watchpoint). What it shows is the agreement harness's own
  // projection, so "what the engine thinks" here = what agreement scores.
  const [engineOn, setEngineOn] = useState(false);
  const { engineRead, engineStatus } = useEngineRead(chartData, engineOn);

  // Per-mark engine agreement for the ledger chip — the HEADLINE concordance
  // ("does the engine surface a setup at my pick"), one fetch for the loaded
  // ticker's whole ledger, keyed so a correction re-grades but a re-render
  // never re-fetches. Peeking here does NOT corrupt ground truth: it reads the
  // SAVED marks, not the live draft.
  const agreement = useMarkAgreement(chartData?.ticker, marks);

  // The sharper "pops-up-live" grade: would each pick have fired on the nightly
  // screener? Runs the full pipeline per box mark in a background worker, so
  // this polls and the Engine chip upgrades from concordance -> fired in place.
  const fired = useMarkFired(chartData?.ticker, marks);

  // The rail's one-click engine test: grade a setup on its exact frozen snapshot
  // (Box/R/S → LPS → Trigger timing). Lazy + on-demand — nothing computes until
  // the operator clicks Test on a rail row.
  const { grades, testing, test } = useTriggerGrade();

  // Saved marks drawn on THIS frame's chart, always (operator bug report
  // 2026-07-11: with only the draft rendered, saving and starting the next
  // mark visually erased everything). The mark being edited is excluded —
  // it IS the draft, already drawn in the operator hue.
  const savedForFrame = useMemo(() => {
    if (!chartData) return [];
    // Bind on the FULL frame identity (digest too): after a vendor restatement
    // a session's digest changes, and a mark bound to the OLD digest must not
    // draw on the new frame as if it were this frame's ground truth.
    return marks.filter((m) => m.as_of_date === chartData.as_of_session
      && m.frame_digest === chartData.frame_digest
      && m.verdict === 'box' && m.id !== marking.editingId);
  }, [marks, chartData, marking.editingId]);

  // Every mark on the loaded frame (ANY verdict, including one being edited) —
  // the set Re Mark deletes to let the operator start this setup over.
  const frameMarks = useMemo(() => {
    if (!chartData) return [];
    return marks.filter((m) => m.ticker === chartData.ticker
      && m.as_of_date === chartData.as_of_session
      && m.frame_digest === chartData.frame_digest);
  }, [marks, chartData]);

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
      // The span the draft's rails bind to (bounded, not edge-to-edge) — the
      // same geometry the mark will save. Null until both rails exist.
      draftSpan: effectiveSpan(marking.draft, chartData?.as_of_session),
      spanAnchor: marking.spanAnchor,
      committed: marking.editingId != null,
      saved: savedForFrame,
      engine: engineOn ? engineRead : null,
      candles: chartData?.candles ?? [],
    });
    api.hover.setArmed(marking.tool !== 'idle');
  });

  const canSave = !!chartData && draftComplete(marking.draft);

  // Assisted Trigger: arming the tool — or re-drawing the LPS while an ASSISTED
  // trigger stands — re-derives the snapped buy from the LAST LPS end-bar's High
  // and the first forward bar that clears it. A MANUALLY placed trigger is left
  // untouched (the operator put it there on purpose). Guarded against a dispatch
  // loop: it only writes when the snap actually differs from what's drawn.
  const lastLpsEnd = useMemo(() => (marking.draft.events || [])
    .filter((e) => e.event_type === 'lps' && e.end_date)
    .map((e) => e.end_date)
    .reduce((a, b) => (a >= b ? a : b), null),
    [marking.draft.events]);
  useEffect(() => {
    const d = markingRef.current.draft;
    if (d.verdict !== 'box') return;
    const armed = markingRef.current.tool === 'trigger';
    const assisted = d.triggerSource === 'assisted';
    if (!armed && !assisted) return;
    const snap = snapTrigger(d, chartData?.candles, chartData?.as_of_session);
    if (!snap) {
      // No breakout in the frozen window: an armed re-derive clears a now-stale
      // assisted value so the readout can say so; a manual trigger is untouched.
      if (armed && assisted && d.triggerDate != null) {
        dispatchMarking({ type: 'set-trigger', date: null });
      }
      return;
    }
    if (snap.date !== d.triggerDate || snap.price !== d.triggerPrice) {
      dispatchMarking({ type: 'set-trigger', date: snap.date, price: snap.price,
                        source: 'assisted' });
    }
  }, [marking.tool, lastLpsEnd, chartData]);

  // In-progress geometry lives only in memory (draftsRef); guard a reload/close
  // that would silently drop a complete, unsaved box. Armed only when there is
  // real drawn work to lose, so it never nags on an empty page.
  useEffect(() => {
    if (!canSave) return undefined;
    const warn = (e) => { e.preventDefault(); e.returnValue = ''; };
    window.addEventListener('beforeunload', warn);
    return () => window.removeEventListener('beforeunload', warn);
  }, [canSave]);

  const save = async () => {
    if (!canSave || saving) return;
    const payload = markPayloadFromDraft(marking.draft, chartData, { label, note });
    // A blind Save is a CREATE unless the operator explicitly loaded a mark to
    // edit (editingId). A create that collides parks a conflict the operator
    // resolves with one click — Save never silently overwrites prior ground
    // truth (adversarial review 2026-07-12).
    const saved = await saveMark(payload, marking.editingId);
    if (!saved) return; // draft stays intact — a failed/parked save never loses work
    // Return to a fresh CREATE draft: the just-saved mark stays on the chart
    // via savedForFrame, so nothing is visually lost, and the next box on this
    // frame is a NEW mark — never a silent PUT over the one just banked.
    dispatchMarking({ type: 'clear' });
  };

  // The operator's explicit "yes, overwrite that existing mark" after a
  // duplicate collision — the one place a create becomes an update, and only
  // on a deliberate click.
  const resolveSaveConflict = async () => {
    const saved = await resolveConflict();
    if (saved) dispatchMarking({ type: 'clear' });
  };

  // Re Mark: wipe this setup and start over (operator ask 2026-07-21 — the old
  // Clear only reset the in-flight draft, leaving the SAVED marks on the chart,
  // so it read as "did nothing"). Deletes every saved mark on the loaded frame,
  // then resets the draft. A destructive wipe of banked ground truth is
  // confirmed once; clearing a not-yet-saved draft is instant (nothing to lose).
  const reMark = async () => {
    if (saving) return;
    if (frameMarks.length > 0) {
      const ok = window.confirm(
        `Re-mark ${chartData.ticker} @ ${chartData.as_of_session}?\n\n`
        + `This deletes the ${frameMarks.length} saved mark(s) on this setup.`);
      if (!ok) return;
      await removeSetup(frameMarks.map((m) => m.id), chartData.ticker);
    }
    dispatchMarking({ type: 'clear' });
  };

  // Delete a whole setup from the rail (operator ask 2026-07-21): cascade every
  // mark at that (ticker, as_of), confirmed once. If it is the loaded setup, its
  // marks vanish from the chart and any in-flight edit of it is reset.
  const deleteSetup = async (row) => {
    const ids = (row.allMarks || []).map((m) => m.id);
    if (!ids.length) return;
    const ok = window.confirm(
      `Delete setup ${row.ticker} @ ${row.asOf}?\n\n`
      + `This removes ${ids.length} saved mark(s) and cannot be undone.`);
    if (!ok) return;
    await removeSetup(ids, chartData?.ticker);
    if (row.ticker === chartData?.ticker && row.asOf === chartData?.as_of_session) {
      dispatchMarking({ type: 'clear' });
    }
  };

  const editMark = (mark) => {
    // A mark is edited on the frame it was drawn on. The ledger lists every
    // session for the ticker, so a clicked row may belong to a DIFFERENT frame
    // than the one on screen; entering edit mode here would let Save re-stamp
    // the mark's provenance onto the loaded frame (the backend now refuses that
    // outright, but the operator should never have to hit it). Navigate to the
    // mark's own frame instead — a click once it is up enters edit cleanly.
    if (mark.ticker !== chartData?.ticker
        || mark.as_of_date !== chartData?.as_of_session) {
      setTicker(mark.ticker);
      lookup(mark.ticker, mark.as_of_date);
      return;
    }
    setLabel(mark.label ?? '');
    setNote(mark.note ?? '');
    clearConflict();   // don't leave a stale "Update existing" from a prior collision
    dispatchMarking({ type: 'edit-mark', mark });
  };

  // Keyboard loop (skipped while typing in any field): tools b/r/s/x,
  // events c/l/t, Enter saves, Escape disarms, e toggles the engine peek.
  const keyDeps = useRef({});
  keyDeps.current = { save };
  useEffect(() => {
    const onKey = (e) => {
      const tag = e.target?.tagName;
      if (tag === 'INPUT' || tag === 'SELECT' || tag === 'TEXTAREA') return;
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      const k = e.key.toLowerCase();
      const tool = { r: 'rail-r', s: 'rail-s', x: 'span',
                     c: 'event:phase_c', l: 'event:lps', t: 'event:spring_test',
                     b: 'trigger' }[k];
      if (tool) { dispatchMarking({ type: 'tool', tool }); e.preventDefault(); return; }
      if (e.key === 'Escape') { dispatchMarking({ type: 'tool', tool: 'idle' }); return; }
      if (k === 'e') { setEngineOn((v) => !v); e.preventDefault(); return; }
      if (e.key === 'Enter') { keyDeps.current.save(); }
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
    return result;
  };

  const submit = (event) => {
    event?.preventDefault();
    if (ticker.trim() && asOf) lookup(ticker, asOf);
  };

  const spec = useMemo(() => ({
    chartOptions: (container) => {
      const base = baseChartOptions('modal', container.clientWidth, container.clientHeight);
      return {
        ...base,
        // ResizeObserver-backed sizing (matches the mini/pulse charts): the pane
        // tracks its container through flex settling, rail-width changes and
        // window resizes on its own — no stale first-paint height, no jank when
        // zooming, no manual resize handler.
        autoSize: true,
        handleScroll: true,
        handleScale: true,
        // Reserve the bottom band for the volume histogram and autoscale the
        // price to the visible bars. Without a bottom margin the candles fill
        // the whole pane and the volume is hidden underneath (operator: "the
        // chart is cropped, leaving out the volume").
        rightPriceScale: { ...base.rightPriceScale,
                           scaleMargins: { top: 0.08, bottom: 0.22 }, autoScale: true },
        // Normal, not the library-default Magnet: Magnet snaps the crosshair
        // to each bar's CLOSE, so the line the operator sees jumps away from
        // the mouse while clicks land at the true pointer position — the
        // "cursor follows at some margin" placement bug (operator, 2026-07-11).
        crosshair: { mode: CrosshairMode.Normal },
      };
    },
    candles: chartData?.candles,
    volumes: chartData?.volumes,
    showVolume: true,
    volumeScaleTop: 0.82,
    onReady: (chart, series) => {
      // The marking controller: click placement + retained draft drawing.
      // The handler reads the CURRENT marking state through a ref (onReady
      // runs once per chart build; the tool changes many times per build).
      const draw = attachCalibrationDraw(chart, series);
      const hover = attachHoverHighlight(chart, series);
      const asOfLine = attachAsOfDivider(chart, series);
      asOfLine.setAsOf(chartData?.as_of_session ?? null);
      chartApiRef.current = { series, draw, hover, asOfLine };
      const onClick = (param) => {
        const st = markingRef.current;
        if (st.tool === 'idle') return;
        if (!param?.point || param.time == null) return;
        const price = series.coordinateToPrice(param.point.y);
        const date = chartTimeToIso(param.time);
        if (price == null || !Number.isFinite(price) || !date) return;
        const asOf = chartData?.as_of_session;
        // Placement guards — refuse a click that can't be a valid mark with a
        // plain reason at click time, never let it fail later at Save with a
        // cryptic "after as_of_date" (operator, 2026-07-21). Two windows:
        //  · the Trigger (buy) is FORWARD of as-of and strictly after the last
        //    LPS bar (mirrors marks_validity._validate_trigger);
        //  · every OTHER mark is something observed BY as-of, so it lands at or
        //    left of the divider (mirrors the box_end / event-end <= as_of rule).
        if (st.tool === 'trigger') {
          const lpsEnd = (st.draft.events || [])
            .filter((e) => e.event_type === 'lps' && e.end_date)
            .map((e) => e.end_date)
            .reduce((a, b) => (a >= b ? a : b), null);
          if (asOf && date < asOf) {
            setPlaceNotice('The buy can’t be left of the as-of line — it’s the forward entry.');
            return;
          }
          if (lpsEnd && date <= lpsEnd) {
            setPlaceNotice('The buy must be after your last LPS bar.');
            return;
          }
        } else if (asOf && date > asOf) {
          setPlaceNotice('That bar is past the as-of line — only the buy can be placed after it.');
          return;
        }
        setPlaceNotice(null);
        dispatchMarking({ type: 'chart-click', date,
                          price: Number(price.toFixed(4)),
                          bar: barsRef.current.get(date) });
      };
      chart.subscribeClick(onClick);
      // Open the view at the as-of divider: the chart reads as the stock "up
      // until that point" — how the setup looked in real time — with the forward
      // grading bars sitting just off the right edge for a Trigger (operator ask
      // 2026-07-21). Ending here (rather than fitContent over the whole
      // [-900d,+45d] window) also lets the price autoscale to the OBSERVED bars,
      // so the base is not squashed by the forward breakout, and keeps geometry
      // marks on the left where they belong. A rebuild only happens on a NEW
      // frame (deps: [chartData]), so this never fights a manual zoom mid-mark.
      const observedLast = chartData?.bar_count ? chartData.bar_count - 1 : null;
      if (observedLast != null) {
        chart.timeScale().setVisibleLogicalRange({ from: 0, to: observedLast + 3 });
      } else {
        chart.timeScale().fitContent();
      }
      return () => {
        chart.unsubscribeClick(onClick);
        hover.detach();
        draw.detach();
        asOfLine.detach();
        chartApiRef.current = null;
      };
    },
    deps: [chartData],
  }), [chartData]);

  return (
    <div className="calibration-page">
      <div className="calibration-main">
      {/* ONE command band (Task 8): lookup · mark · save read as a single
          continuous flow, the screener's proven folded pattern (one
          instrument-tile band, seams between groups). Each group WRAPS rather
          than clipping, so the full vocabulary stays visible. The lookup group
          keeps its own <form> so Enter there submits the lookup — and only the
          lookup (the label lives outside it). */}
      <div className="instrument-tile screener-command-band calibration-command-band">
      <form className="ccb-group" onSubmit={submit}
            style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 8 }}>
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
            <button type="button" aria-pressed={engineOn}
                    onClick={() => setEngineOn((v) => !v)}
                    title="Overlay the engine's read of this frame (the agreement harness's own lens) [e]. Mark FIRST, peek after — anchoring on the engine corrupts the ground truth.">
              Engine
            </button>
            {/* Provenance figures change on every load — mono + tabular so
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

      <span className="screener-command-seam" aria-hidden="true" />
      <CalibrationMarkingBar
        state={marking}
        dispatch={dispatchMarking}
        disabled={!chartData}
        asOfSession={chartData?.as_of_session}
        onReMark={reMark}
      />

      <span className="screener-command-seam" aria-hidden="true" />
      <CalibrationSaveBar
        disabled={!chartData}
        canSave={canSave}
        saving={saving}
        editingId={marking.editingId}
        label={label}
        onLabel={(v) => { setLabel(v); if (conflict) clearConflict(); }}
        note={note}
        onNote={setNote}
        onSave={save}
        onNewMark={() => dispatchMarking({ type: 'clear' })}
        conflict={conflict}
        onResolveConflict={resolveSaveConflict}
        saveError={saveError}
        tally={tally}
        needs={draftStarted(marking.draft) ? saveNeeds(marking.draft) : []}
      />
      </div>

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
              // frame stays up and the failure rides above it. A transient
              // rate-limit is not an error: it wears the calm warning ink, not
              // danger red, so a self-healing hiccup never trains distrust.
              <div style={{
                position: 'absolute', top: 8, left: 8, right: 8, zIndex: 5,
                padding: '6px 10px', borderRadius: 6, fontSize: 12,
                border: `1px solid ${surfaceOf('modal').border}`,
                borderLeft: `2px solid ${failure.class === 'rate_limited' ? 'var(--warning)' : 'var(--danger)'}`,
                background: 'rgba(23, 25, 34, 0.92)',
              }}>
                {failure.class === 'rate_limited'
                  ? `Vendor busy. ${paneBody(false, failure)}`
                  : `Lookup failed — ${failure.class}. ${paneBody(false, failure)}`}
              </div>
            )}
            {engineOn && (
              // What the engine thinks, in words — rails land on the chart in
              // engine ink; this chip carries the session/no-read verdict.
              <div title={engineTitle(engineRead)} style={{
                position: 'absolute', top: 8, right: 8, zIndex: 4,
                fontSize: 11, fontFamily: CHART_FONT, color: 'var(--text-muted)',
                fontVariantNumeric: 'tabular-nums',
                background: 'rgba(23, 25, 34, 0.85)', padding: '3px 8px',
                borderRadius: 6,
              }}>
                {engineLine(engineRead, engineStatus)}
              </div>
            )}
            {placeNotice && (
              // Why a click was refused (top-center, out of the rails' way): a
              // geometry mark placed past the as-of line, or a Trigger outside
              // its forward window. Neutral warning ink — a placement that does
              // not fit, not an error. Clears when the tool/frame changes or a
              // valid placement lands.
              <div style={{
                position: 'absolute', top: 8, left: '50%', transform: 'translateX(-50%)',
                zIndex: 6, fontSize: 11, color: 'var(--warning)',
                border: '1px solid color-mix(in srgb, var(--warning) 55%, transparent)',
                background: 'rgba(23, 25, 34, 0.92)', padding: '3px 10px',
                borderRadius: 6, whiteSpace: 'nowrap',
              }}>
                {placeNotice}
              </div>
            )}
            {chartData.warnings?.length > 0 && warningsOpen && (
              // Warnings live INSIDE the pane (bottom edge) — the chart's geometry
              // never shifts when a lookup gains or loses one. Dismissible with the
              // × since the banner can sit over the date axis (operator 2026-07-21);
              // it re-shows on the next frame that carries a notice.
              <div style={{
                position: 'absolute', bottom: 8, left: 8, zIndex: 5,
                maxWidth: 'calc(100% - 16px)',
                display: 'flex', alignItems: 'flex-start', gap: 6,
                fontSize: 11, color: 'var(--accent-yellow)',
                background: 'rgba(23, 25, 34, 0.85)', padding: '3px 8px',
                borderRadius: 6,
              }}>
                <div>{chartData.warnings.map((w) => <div key={w}>{w}</div>)}</div>
                <button type="button" onClick={() => setWarningsOpen(false)}
                        aria-label="Dismiss data notice"
                        title="Dismiss (re-shows on the next frame with a notice)"
                        style={{ background: 'none', border: 'none', color: 'inherit',
                                 cursor: 'pointer', fontSize: 13, lineHeight: 1,
                                 padding: '0 2px', opacity: 0.75 }}>
                  ×
                </button>
              </div>
            )}
          </>
        ) : (
          <PaneMessage
            title={paneTitle(loading, failure)}
            body={paneBody(loading, failure)}
            danger={!loading && !!failure && failure.class !== 'rate_limited'}
          />
        )}
      </div>

      <CalibrationMarksList
        marks={marks}
        editingId={marking.editingId}
        agreement={agreement}
        fired={fired}
        onEdit={editMark}
        onDelete={(id) => removeMark(id, chartData?.ticker)}
      />
      </div>

      {/* The calibrated-list navigator: every setup (ticker @ as_of), the unit
          the operator reviews/edits/tests. A click LOADS that setup for
          review/edit/test. */}
      <aside className="calibration-rail">
        <CalibrationRail
          setups={setups}
          activeTicker={chartData?.ticker}
          activeAsOf={chartData?.as_of_session}
          onPick={(t, asOf) => { setTicker(t); lookup(t, asOf); }}
          grades={grades}
          testing={testing}
          onTest={test}
          onDeleteSetup={deleteSetup}
        />
      </aside>
    </div>
  );
}

function engineLine(engineRead, engineStatus) {
  if (engineStatus === 'loading') return 'engine: reading…';
  if (engineStatus) return `engine: ${engineStatus}`;
  if (!engineRead) return 'engine: —';
  if (!engineRead.elected) {
    // Operator's terms (2026-07-21): a plain verdict, not the raw detector
    // reason ("no structure elects within the snap window") — that moves to the
    // chip's hover title for when the diagnostic is actually wanted.
    return 'engine: does NOT confirm your box here';
  }
  const snap = engineRead.snapped
    ? ` (snapped −${engineRead.snapped})` : '';
  return `engine finds a box — R ${fx(engineRead.R, 2)} / S ${fx(engineRead.S, 2)}`
    + ` · from ${engineRead.box_start_date} @ ${engineRead.eval_session}${snap}`;
}

// The raw detector reason, kept off the headline but one hover away — so "why
// didn't it confirm?" is answerable without cluttering the plain verdict.
function engineTitle(engineRead) {
  if (engineRead && !engineRead.elected && engineRead.reason) {
    return `engine detail: ${engineRead.reason}`;
  }
  return undefined;
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
