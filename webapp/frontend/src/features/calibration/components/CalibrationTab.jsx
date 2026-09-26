import { useEffect, useMemo, useReducer, useRef, useState } from 'react';
import CalibrationChartPane from './CalibrationChartPane';
import CalibrationLookupForm from './CalibrationLookupForm';
import CalibrationMarkingBar from './CalibrationMarkingBar';
import CalibrationMarksList from './CalibrationMarksList';
import CalibrationSaveBar from './CalibrationSaveBar';
import CalibrationRail from './CalibrationRail';
import useCalibrationChart from '../hooks/useCalibrationChart';
import useCalibrationCanvas from '../hooks/useCalibrationCanvas';
import useCalibrationMarks from '../hooks/useCalibrationMarks';
import useEngineRead from '../hooks/useEngineRead';
import useMarkAgreement from '../hooks/useMarkAgreement';
import useMarkFired from '../hooks/useMarkFired';
import useTriggerGrade from '../hooks/useTriggerGrade';
import {
  assistedTriggerAction,
  draftComplete,
  draftHasUnsavedWork,
  draftStarted,
  frameKeyOf,
  initialMarkingState,
  lastLpsEndDate,
  latestObservedDate,
  markPayloadFromDraft,
  markingReducer,
  saveNeeds,
  trimDraftForAsOf,
} from '../model/calibrationMarking';
import {
  autoEditStep,
  eveOfBuyDate,
  frameSwap,
  marksOnFrame,
  representativeBoxFor,
  savedBoxesForFrame,
} from '../model/calibrationFrame';
import { HOTKEY_TOOLS, isMarkingKeystroke } from '../model/calibrationHotkeys';
import { armLeaveGuard, disarmLeaveGuard } from '../../../shared/navigation/leaveGuard';

// The Calibration page (Calibration at Scale, Task 10): pull up ANY ticker at
// ANY historical as-of date on Chrollo's own data. The chart is the
// protagonist — one compact command band above a fixed, never-shifting chart
// pane whose lookup states (blank / loading / failure classes / ideal) render
// INSIDE the pane so the operator's eyes never lose their place between the
// dozens of lookups a marking sitting takes. The interactive marking layer
// (click-to-place rails, the per-setup rail, one-click engine test) sits on
// this shell; this page deliberately owns all its state — nothing in
// AppShell, no app-level context.

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
  const draftsRef = useRef(new Map()); // frameKey -> draft (per-frame, per-sitting)
  const dateInputRef = useRef(null);   // focused by "Add instance" (request 7)
  // A draft handed forward to the NEXT frame that loads — the date-change carry
  // and the eve-of-buy snapshot lock preserve the current marks (+ label/note)
  // across an as-of change instead of wiping them (request 6). Consumed once, by
  // the frame swap below.
  const carryDraftRef = useRef(null);
  // A frame flagged to auto-enter edit mode once its saved marks load (request 2:
  // the Trigger is editable on a loaded setup without a Re-Mark). Holds a frameKey.
  const pendingAutoEditRef = useRef(null);

  // Drafts are structurally keyed to the frame they were drawn on: loading
  // another session swaps to THAT frame's draft (or a fresh one), never bleeding
  // rails across frames (frameSwap decides what the new frame starts with; a
  // carry is consumed by this one swap either way).
  useEffect(() => {
    const key = frameKeyOf(chartData);
    if (key !== markingRef.current.frameKey) {
      const swap = frameSwap(chartData, carryDraftRef.current, draftsRef.current.get(key));
      carryDraftRef.current = null;
      dispatchMarking(swap.load);
      setLabel(swap.label);
      setNote(swap.note);
      clearConflict();   // a parked overwrite must not follow the eye to a new frame
      pendingAutoEditRef.current = swap.autoEditKey;
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chartData]);

  // Stash the draft AND its edit binding under the frame key (they travel
  // together in state, so a swap can never stash them under the wrong frame).
  // Persisting editingId means returning to a frame mid-edit resumes the PUT,
  // not a create that collides (adversarial review 2026-07-22).
  useEffect(() => {
    if (marking.frameKey) {
      draftsRef.current.set(marking.frameKey,
        { draft: marking.draft, editingId: marking.editingId, pristine: marking.pristine });
    }
  }, [marking.frameKey, marking.draft, marking.editingId, marking.pristine]);

  // A parked "Update existing" holds the geometry AS IT WAS when it collided;
  // the moment the operator redraws, that snapshot is stale — drop the
  // conflict so a later click can't write yesterday's rails. Re-Save re-parks
  // with the current draft.
  useEffect(() => {
    if (conflict) clearConflict();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [marking.draft]);

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
  // line (only what was observed by then is markable), a Trigger clicked at/before
  // the last LPS bar (its only rule now — no as_of floor), or a snapshot lock that
  // would strand a mark. Shown as a transient chip, cleared when the tool or frame
  // changes.
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

  // Saved boxes drawn on THIS frame's chart (minus the one being edited — it IS
  // the draft); every mark on the frame (what Re Mark deletes); and the box that
  // loading the frame auto-enters for edit.
  const savedForFrame = useMemo(() => savedBoxesForFrame(marks, chartData, marking.editingId),
    [marks, chartData, marking.editingId]);
  const frameMarks = useMemo(() => marksOnFrame(marks, chartData), [marks, chartData]);
  const representativeBox = useMemo(() => representativeBoxFor(marks, chartData),
    [marks, chartData]);

  // Auto-enter edit mode on a pre-marked frame (request 2): once the frame's saved
  // marks have loaded, drop the representative box into the draft — no Re-Mark
  // needed. Fires ONLY for a frame the swap flagged fresh (so never right after a
  // save on the same frame, and never over a carried or in-progress draft). "New
  // mark"/"Add instance" escape it. Reads the LIVE reducer state, not markingRef
  // (autoEditStep says why).
  useEffect(() => {
    const step = autoEditStep(pendingAutoEditRef.current, chartData, marking, representativeBox);
    if (step === 'wait') return;
    pendingAutoEditRef.current = null;
    if (step === 'cancel') return;
    setLabel(representativeBox.label ?? '');
    setNote(representativeBox.note ?? '');
    clearConflict();
    dispatchMarking({ type: 'edit-mark', mark: representativeBox });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chartData, representativeBox, marking.frameKey, marking.editingId, marking.draft]);

  const spec = useCalibrationCanvas({
    chartData, marking, savedForFrame, engineOn, engineRead,
    dispatchMarking, setPlaceNotice,
  });

  const canSave = !!chartData && draftComplete(marking.draft);

  // Assisted Trigger: arming the tool — or re-drawing the LPS while an ASSISTED
  // trigger stands — re-derives the snapped buy from the LAST LPS end-bar's High
  // and the first forward bar that clears it. assistedTriggerAction owns the
  // rule, including the guard against a dispatch loop.
  const lastLpsEnd = useMemo(() => lastLpsEndDate(marking.draft.events),
    [marking.draft.events]);
  useEffect(() => {
    const action = assistedTriggerAction(markingRef.current, chartData?.candles);
    if (action) dispatchMarking(action);
  }, [marking.tool, lastLpsEnd, chartData]);

  // In-progress geometry lives only in memory (draftsRef), so ANY exit from this
  // page drops it. Guard all three exits with one armed flag: a reload/close via
  // beforeunload, and an in-app route change via the shared leave guard the top
  // nav consults (council review 2026-09-07, finding 8 — the top nav used to be
  // an unguarded, silent delete of hand-drawn ground truth).
  //
  // Armed on draftHasUnsavedWork, not draftComplete: a placed rail with the LPS
  // still pending is drawn work too, and the old guard let it go without a word.
  // It still never nags on a pristine page — including the very common case of a
  // saved mark auto-loaded for correction and not yet touched.
  const hasUnsavedDraft = !!chartData && draftHasUnsavedWork(marking);
  useEffect(() => {
    if (!hasUnsavedDraft) return undefined;
    const warn = (e) => { e.preventDefault(); e.returnValue = ''; };
    window.addEventListener('beforeunload', warn);
    armLeaveGuard('This setup has marks you have not saved. Leaving the page discards them.');
    return () => {
      window.removeEventListener('beforeunload', warn);
      disarmLeaveGuard();
    };
  }, [hasUnsavedDraft]);

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
  // events c/l/t/o/m/u, Enter saves, Escape disarms, e toggles the engine peek.
  const keyDeps = useRef({});
  keyDeps.current = { save };
  useEffect(() => {
    const onKey = (e) => {
      if (!isMarkingKeystroke(e)) return;
      const k = e.key.toLowerCase();
      const tool = HOTKEY_TOOLS[k];
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

  // Run a lookup that may have armed a carry, and NEVER leave the carry stranded:
  // if the load fails, or resolves to the SAME frame, the frame-swap effect won't
  // consume it, so clear it here (adversarial review 2026-07-22 — a stranded carry
  // could otherwise bleed onto whatever frame loads next).
  const loadCarrying = async (t, date) => {
    const preKey = chartData ? frameKeyOf(chartData) : null;
    const result = await lookup(t, date);
    if (carryDraftRef.current && (!result || frameKeyOf(result) === preKey)) {
      carryDraftRef.current = null;
    }
    return result;
  };

  const submit = async (event) => {
    event?.preventDefault();
    if (!ticker.trim() || !asOf) return;
    const d = marking.draft;
    const sameTicker = chartData && ticker.trim().toUpperCase() === chartData.ticker;
    const dateChanged = chartData && asOf !== chartData.as_of_session;
    // Request 6: a same-ticker as-of change CARRIES the current marks to the new
    // snapshot instead of wiping them. Dialing the date BEFORE the drawn marks
    // would push the box/LPS into the forward window (invalid), so that is
    // confirmed — and on cancel the date input is reset so it isn't left poisoned.
    if (sameTicker && dateChanged && draftStarted(d)) {
      const latest = latestObservedDate(d);
      if (latest && asOf < latest) {
        const ok = window.confirm(
          `${asOf} is before your marks (last observed ${latest}).\n\n`
          + 'On that earlier frame the box/LPS would fall after the as-of line and '
          + `can't be kept. Load a fresh chart at ${asOf} and drop the current marks?`);
        if (!ok) { setAsOf(chartData.as_of_session); return; }
        // proceed: a blank load at the earlier date (the marks don't fit it)
      } else {
        carryDraftRef.current = { ticker: chartData.ticker, draft: trimDraftForAsOf(d, asOf), label, note };
      }
    }
    await loadCarrying(ticker, asOf);
  };

  // The eve-of-buy snapshot (the session before the placed buy). Usually >= every
  // observed mark (the box/LPS precede the buy), but not guaranteed — a rail/event
  // placed after the buy is refused below rather than stranded past the earlier
  // snapshot.
  const eveOfBuyAsOf = useMemo(() => eveOfBuyDate(marking.draft.triggerDate, chartData),
    [marking.draft.triggerDate, chartData]);

  // Lock the engine's snapshot to the buy's eve, carrying every mark across.
  const lockSnapshotToBuyEve = async () => {
    if (!eveOfBuyAsOf || !chartData || loading) return;
    if (eveOfBuyAsOf === chartData.as_of_session) return;
    // A mark placed AFTER the buy would be stranded past this earlier snapshot
    // (trimDraftForAsOf only re-derives box_end, not rail anchors / event ends);
    // refuse with a reason instead of a cryptic save rejection (review 2026-07-22).
    const latest = latestObservedDate(marking.draft);
    if (latest && eveOfBuyAsOf < latest) {
      setPlaceNotice(`Can’t snapshot to ${eveOfBuyAsOf} — a mark (${latest}) sits after it; move it or the buy first.`);
      return;
    }
    carryDraftRef.current = { ticker: chartData.ticker,
      draft: trimDraftForAsOf(marking.draft, eveOfBuyAsOf), label, note };
    setAsOf(eveOfBuyAsOf);
    await loadCarrying(chartData.ticker, eveOfBuyAsOf);
  };

  // Add another instance of a setup on this ticker (request 7): a brand-new setup
  // at a NEW as-of. Clear the draft/label/note and the date, keep the ticker, focus
  // the date input. Deletes nothing and carries nothing (the explicit opposite of
  // the date-change carry) — the existing saved setup is untouched.
  const addInstance = () => {
    pendingAutoEditRef.current = null; // an explicit CREATE cancels a pending auto-edit
    dispatchMarking({ type: 'clear' });
    setLabel('');
    setNote('');
    setAsOf('');
    dateInputRef.current?.focus();
  };

  // "New mark" — leave edit mode for a fresh CREATE draft on the SAME frame. Cancels
  // any pending auto-edit so a mid-fetch New click isn't overridden back into an edit.
  const newMark = () => {
    pendingAutoEditRef.current = null;
    dispatchMarking({ type: 'clear' });
  };


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
      <CalibrationLookupForm
        ticker={ticker}
        onTicker={setTicker}
        asOf={asOf}
        onAsOf={setAsOf}
        dateInputRef={dateInputRef}
        loading={loading}
        chartData={chartData}
        engineOn={engineOn}
        onToggleEngine={() => setEngineOn((v) => !v)}
        eveOfBuyAsOf={eveOfBuyAsOf}
        onLockSnapshot={lockSnapshotToBuyEve}
        onAddInstance={addInstance}
        onSubmit={submit}
      />

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
        onNewMark={newMark}
        conflict={conflict}
        onResolveConflict={resolveSaveConflict}
        saveError={saveError}
        tally={tally}
        needs={draftStarted(marking.draft) ? saveNeeds(marking.draft) : []}
      />
      </div>

      <CalibrationChartPane
        chartData={chartData}
        spec={spec}
        loading={loading}
        failure={failure}
        engineOn={engineOn}
        engineRead={engineRead}
        engineStatus={engineStatus}
        placeNotice={placeNotice}
        warningsOpen={warningsOpen}
        onDismissWarnings={() => setWarningsOpen(false)}
      />

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

export default CalibrationTab;
