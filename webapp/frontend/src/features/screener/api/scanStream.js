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
// This module also decides whether the results on screen are about to be replaced by a running job.

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

// Whether the results on screen are about to be replaced, so the grid shows them dimmed
// and inert instead of blanking them (operator 2026-10-03). Only a cached evaluation
// rewrites the screener artifact; a download refreshes the market-data cache and leaves
// the scan alone. The dim holds through the re-fetch after the job ends (awaitingResults),
// so the old cards never return to full strength just before the new ones land.
export function resultsStale(activeJob, awaitingResults) {
  return activeJob === 'evaluation' || awaitingResults === true;
}

// The end of a job, in the order that dim depends on. Both ends of a run use it: the
// export line, and [DONE] (a stopped evaluation, or one that never printed the export
// line). When the job rewrote the scan (`refetch`), the dim goes up in the same tick
// that clears the job and comes down only once the re-fetch has settled.
export async function endJob(refetch, { holdDim, clearJob, reloadStatus, reloadResults }) {
  if (refetch) holdDim(true);
  clearJob();
  try {
    await reloadStatus();
    if (refetch) await reloadResults();
  } finally {
    if (refetch) holdDim(false);
  }
}
