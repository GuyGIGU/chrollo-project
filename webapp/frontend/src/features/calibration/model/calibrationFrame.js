// The loaded frame's side of the Calibration page — which saved marks belong
// to it, and what a draft does when the frame changes. Pure (node --test'able):
// the page owns the refs, state and effects; this module owns the judgments.
import { draftStarted, frameKeyOf } from './calibrationMarking.js';

const onFrame = (m, chartData) => m.as_of_date === chartData.as_of_session
  && m.frame_digest === chartData.frame_digest;

// Saved marks drawn on THIS frame's chart, always (operator bug report
// 2026-07-11: with only the draft rendered, saving and starting the next mark
// visually erased everything). The mark being edited is excluded — it IS the
// draft, already drawn in the operator hue. Bound on the FULL frame identity
// (digest too): after a vendor restatement a session's digest changes, and a
// mark bound to the OLD digest must not draw on the new frame as if it were
// this frame's ground truth.
export function savedBoxesForFrame(marks, chartData, editingId) {
  if (!chartData) return [];
  return marks.filter((m) => onFrame(m, chartData)
    && m.verdict === 'box' && m.id !== editingId);
}

// Every mark on the loaded frame (ANY verdict, including one being edited) —
// the set Re Mark deletes to let the operator start this setup over.
export function marksOnFrame(marks, chartData) {
  if (!chartData) return [];
  return marks.filter((m) => m.ticker === chartData.ticker && onFrame(m, chartData));
}

// The representative BOX mark for the loaded frame (highest revision, then the
// primary/empty label) — the setup that loading auto-enters for edit. Null if
// the frame carries no saved box.
export function representativeBoxFor(marks, chartData) {
  if (!chartData) return null;
  const boxes = marksOnFrame(marks, chartData).filter((m) => m.verdict === 'box');
  if (!boxes.length) return null;
  return boxes.sort((a, b) => ((b.revision ?? 0) - (a.revision ?? 0))
    || (a.label || '').localeCompare(b.label || ''))[0];
}

// The eve-of-buy snapshot the operator picked (request 6, "auto → eve of buy"):
// the session immediately BEFORE the placed buy — Chrollo scans after the close,
// so this asks "would last night's scan have surfaced it?". Null until a buy is
// placed (or if it is the very first bar).
export function eveOfBuyDate(triggerDate, chartData) {
  if (!triggerDate || !chartData) return null;
  const list = chartData.candles || [];
  const idx = list.findIndex((b) => b.time === triggerDate);
  return idx > 0 ? list[idx - 1].time : null;
}

// What a newly loaded frame starts with. Drafts are structurally keyed to the
// frame they were drawn on: loading another session swaps to THAT frame's
// cached draft (or a fresh one), never bleeding rails across frames. A carried
// draft (the date-change / snapshot-lock) wins for the one swap that consumes
// it and keeps the setup's label/note with it; otherwise the label and note
// clear — they are per-setup and never follow the eye to a new frame.
//
// A carry only applies to the frame it was armed for — its own TICKER. A
// stranded carry (a date-change that failed or was abandoned, then a hop to
// another setup) is discarded so a setup's marks can never bleed onto an
// unrelated frame (adversarial review 2026-07-22).
//
// `autoEditKey` flags a genuinely fresh frame (no carry, nothing drawn) so it
// auto-enters edit mode when its saved marks arrive — never a carried or
// in-progress one.
export function frameSwap(chartData, carry, cached) {
  const key = frameKeyOf(chartData);
  const carried = carry && chartData && carry.ticker !== chartData.ticker ? null : carry;
  return {
    load: { type: 'load', frameKey: key,
            draft: carried?.draft ?? cached?.draft ?? null,
            editingId: carried ? null : (cached?.editingId ?? null),
            // A carried draft is work in hand; a cached one resumes whatever it
            // was, so the unsaved-work guard survives a frame hop and back.
            pristine: carried ? false : (cached?.pristine ?? true) },
    label: carried ? (carried.label ?? '') : '',
    note: carried ? (carried.note ?? '') : '',
    autoEditKey: (!carried && !(cached?.draft && draftStarted(cached.draft))) ? key : null,
  };
}

// One step of the auto-edit on a pre-marked frame (request 2): once the frame's
// saved marks have loaded, the representative box drops into the draft so its
// LPS is "in hand" and the Trigger tool un-grays — no Re-Mark needed.
//   'wait'   — keep the flag: the frame, its load, or its marks have not landed
//   'cancel' — drop the flag: the draft is already being edited or drawn on
//   'enter'  — drop the flag and edit the representative box
// It must read the LIVE reducer state: the frame-swap and this step run in the
// same pass on a chartData change, before the swap's 'load' has applied — so it
// waits until marking.frameKey === the flagged key, and a same-ticker hop between
// pre-marked setups still auto-enters edit (adversarial review 2026-07-22).
export function autoEditStep(pendingKey, chartData, marking, box) {
  if (!pendingKey || !chartData || frameKeyOf(chartData) !== pendingKey) return 'wait';
  if (marking.frameKey !== pendingKey) return 'wait';
  if (marking.editingId != null || draftStarted(marking.draft)) return 'cancel';
  return box ? 'enter' : 'wait';
}
