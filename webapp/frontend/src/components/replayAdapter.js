// Pure adapter between the watchlist replay envelope and the modal's props —
// the renderability seam the checked-in v1 fixture pins (Finviz plan Task 7:
// future shape changes must keep old saves rendering). EC-28: presentational
// lookups only — the verdicts and the entry arrive resolved from storage;
// nothing here re-derives a judgment. No React, node-testable.

export const SNAPSHOT_VERSION = 1;

// Frontend twin of the backend's closed archive-verdict registry
// (services/watchlist_ledger.ARCHIVE_STATUSES) — copy strings only.
export const ARCHIVE_STATUS_COPY = {
  matched: 'archive row intact',
  rewritten: 'archive re-scanned under a different engine config — no longer what you saw',
  purged: 'archive row purged — this snapshot is the only record',
  never_archived: 'this scan never reached the archive',
  no_pin: 'saved without a setup — nothing to compare',
};

// The stored envelope -> { entry, scanIdentity } the modal renders, or null
// when the snapshot is absent or from a version this build cannot draw.
export function adaptReplaySnapshot(snapshot) {
  if (!snapshot || snapshot.snapshot_version !== SNAPSHOT_VERSION) return null;
  const entry = snapshot.entry;
  if (!entry || !Array.isArray(entry.candles) || entry.candles.length === 0) {
    return null;
  }
  return { entry, scanIdentity: snapshot.scan_identity || null };
}

// The provenance frame's resolved strings for one ReplayResponse envelope.
export function replayProvenance(replay) {
  const watch = replay?.watch || {};
  return {
    asScanned: watch.pin_scan_date || null,
    savedOn: watch.save_date || null,
    unstarred: watch.unstarred_at != null,
    archiveNote: ARCHIVE_STATUS_COPY[replay?.archive_status]
      || replay?.archive_status
      || '',
    renderable: adaptReplaySnapshot(replay?.snapshot) != null,
  };
}
