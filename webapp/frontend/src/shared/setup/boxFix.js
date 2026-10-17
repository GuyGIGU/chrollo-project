// "Fix the box" on the lens (his ask of Tue 13/10/2026, "if we can get the engine to draw like me",
// and Fri 17/10/2026, on MTLS: "build something to close the gap"): he corrects the reader's two
// lines on the daily chart, each click snapping to a bar's end point, and the fix is saved BESIDE
// the pair the reader showed. Pure: no DOM, no chart; node --test pins it. The hook
// (useBoxFix.js) does the clicks and the save, the lens draws the lines.

// The reader's parent box as the wire carries it (two_eyes.boxes), or null when it shows none.
export function readerPair(data) {
  const parent = (data?.two_eyes?.boxes || []).find((box) => box.role === 'parent');
  if (!parent) return null;
  return { r: parent.r, rDay: parent.r_day, s: parent.s, sDay: parent.s_day, opened: parent.opened };
}

// The empty draft: nothing drawn yet.
export const EMPTY_FIX = { r: null, rDay: null, s: null, sDay: null };

// One click while fixing. The FIRST line is the resistance, on the clicked bar's HIGH (a rail sits
// only on the end point of a swing: the climax's high); the SECOND is the support, on the clicked
// bar's LOW (the reaction's low). A third click starts over with a new resistance.
export function applyFixClick(draft, { date, bar }) {
  if (!date || !bar || !Number.isFinite(bar.high) || !Number.isFinite(bar.low)) return draft;
  if (draft.r == null || draft.s != null) {
    return { r: bar.high, rDay: date, s: null, sDay: null };
  }
  return { ...draft, s: bar.low, sDay: date };
}

// A draft is a box once both lines stand and the resistance sits over the support.
export function fixComplete(draft) {
  return draft?.r != null && draft?.s != null && draft.r > draft.s;
}

// The step the strip under the chart tells him.
export function fixPrompt(draft) {
  if (draft?.r == null) return 'click the bar whose HIGH is the resistance';
  if (draft?.s == null) return `resistance ${draft.r.toFixed(2)} on ${draft.rDay}: now click the bar whose LOW is the support`;
  if (!fixComplete(draft)) return 'the support must sit under the resistance: click the resistance bar again';
  return `R ${draft.r.toFixed(2)} (${draft.rDay}) · S ${draft.s.toFixed(2)} (${draft.sDay})`;
}

// Whether his box differs from the reader's to the cent (a fix that agrees is still worth saving:
// a chart he looked at and left as it was says "the box is right").
export function fixDiffers(draft, reader) {
  if (!fixComplete(draft)) return false;
  if (!reader) return true;
  return Math.abs(draft.r - reader.r) >= 0.005 || Math.abs(draft.s - reader.s) >= 0.005;
}

// The request body: his two lines, the reader's pair beside them, the chart's last day and the
// reader's stamp that night (the scan identity's engine_config_version, which hashes the ruleset).
export function fixPayload(ticker, data, draft, scanIdentity = null) {
  const candles = data?.candles || [];
  const reader = readerPair(data);
  return {
    ticker,
    scan_day: candles.length ? candles[candles.length - 1].time : null,
    resistance: draft.r,
    r_day: draft.rDay,
    support: draft.s,
    s_day: draft.sDay,
    reader_resistance: reader?.r ?? null,
    reader_r_day: reader?.rDay ?? null,
    reader_support: reader?.s ?? null,
    reader_s_day: reader?.sDay ?? null,
    reader_opened_day: reader?.opened ?? null,
    ruleset: scanIdentity?.engine_config_version || '',
    note: null,
  };
}
