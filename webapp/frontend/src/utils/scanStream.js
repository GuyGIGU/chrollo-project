// Which stream URL each manual job uses, and whether a fresh mount should
// re-attach to one already running.
//
// Council review 2026-09-07, finding 4: the scan stream was owned by the
// screener route, so one click on the top nav unmounted it — and the backend
// read that disconnect as a cancellation and killed the 12-17 minute scan
// (archive row 271). The job now survives server-side; this is the client half,
// the decision to pick the run back up on the next mount.
//
// The SERVER names the running job (EC-28 — the wire carries the verdict); the
// client only maps that name to a URL, and refuses a name it cannot map rather
// than building a URL out of it.

// Only the jobs a surface can START live here. The full-scan route the backend
// labels 'scan' is deliberately absent: nothing in the app starts it, so a
// re-attach has no readout to offer it and refuses the name rather than
// inventing a URL (council review 2026-09-07, A6).
export const SCAN_STREAM_PATH = {
  evaluation: 'run-evaluation-stream',
  download: 'download-data-stream',
};

export const ATTACH_STREAM_PATH = 'scan-stream/attach';
export const ACTIVE_STREAM_PATH = 'scan-stream/active';
export const CANCEL_STREAM_PATH = 'scan-stream/cancel';

export const startStreamUrl = (base, job) => `${base}/${SCAN_STREAM_PATH[job]}/`;
export const attachStreamUrl = (base) => `${base}/${ATTACH_STREAM_PATH}/`;
export const activeStreamUrl = (base) => `${base}/${ACTIVE_STREAM_PATH}`;
export const cancelStreamUrl = (base) => `${base}/${CANCEL_STREAM_PATH}`;

// The job this mount should re-attach to, or null. `alreadyStreaming` keeps a
// late /scan-stream/active answer from stomping a stream the operator just
// started by hand.
export function reattachTarget(state, alreadyStreaming = false) {
  if (alreadyStreaming) return null;
  if (!state || !state.active || !state.job) return null;
  if (!SCAN_STREAM_PATH[state.job]) return null;
  return state.job;
}
