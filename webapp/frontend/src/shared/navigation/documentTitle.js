// The browser tab's title (operator suggestion 6, 2026-10-03): with Chrollo open
// in several tabs across two screens, each tab must say which page it is, and
// what it is looking at. No "Chrollo" suffix: the approved example has none, and
// the favicon already names the app. The one hook that writes it is
// shared/hooks/useDocumentTitle.js.
export const APP_TITLE = 'Chrollo';            // must equal index.html <title>
export const UNSAVED_DOT = '●';

export function documentTitle(page, detail = null, { unsaved = false } = {}) {
  const base = detail ? `${page} · ${detail}` : page;   // 'Calibration · SKYT 2026-04-13'
  return unsaved ? `${UNSAVED_DOT} ${base}` : base;     // the dot LEADS so a truncated tab still shows it
}
