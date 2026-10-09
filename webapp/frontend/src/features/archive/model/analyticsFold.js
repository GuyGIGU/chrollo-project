// The Archive's analytics fold: collapsed unless this viewer opened it last time.
export const ANALYTICS_OPEN_KEY = 'chrollo:archive-analytics-open';

// The localStorage accessor is read INSIDE the try on purpose, never as a default
// parameter: when site data is blocked, Chrome throws on the getter itself. The
// storage argument exists only so the tests can inject a stub; React calls this
// with no argument as the lazy useState initializer.
export function readAnalyticsOpen(storage) {
  try {
    return (storage ?? globalThis.localStorage).getItem(ANALYTICS_OPEN_KEY) === '1';
  } catch {
    return false;
  }
}

export function writeAnalyticsOpen(open, storage) {
  try {
    (storage ?? globalThis.localStorage).setItem(ANALYTICS_OPEN_KEY, open ? '1' : '0');
  } catch {
    /* storage blocked or full: the fold still works for this visit */
  }
}

// Numbers one analytics fetch on the shared `generation` ref ({ current }) and returns
// whether it is still the newest. An opening fetch that read the archive before Update
// Forward Returns committed can land after the refresh that followed it; a superseded
// fetch must write nothing, or the older numbers come back on screen as 'done'.
export function beginLatestCall(generation) {
  generation.current += 1;
  const mine = generation.current;
  return () => mine === generation.current;
}
