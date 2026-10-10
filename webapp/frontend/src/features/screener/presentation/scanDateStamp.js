// The screener's scan-date stamp — a PURE builder, kept out of the JSX so it
// stays Node-testable (extension-explicit imports: Node's ESM resolver does not
// guess one). The shown date is the close the scan READ (scan_identity.scan_date);
// the colour comes from the payload's stale_after (the backend's verdict of when a
// newer scan was due) through the one shared freshness rule, the same one the Home
// Action Center uses. ' · stale' is Home's own word. Presentation only: no engine
// threshold is judged here.
import { scanIsStale } from '../../../shared/formatting/appFormat.js';
import { dateTimeShort, fmtDay } from '../../../shared/formatting/format.js';

export function buildScanDateStamp(payload, now = new Date()) {
  const written = payload?.scanned_at;
  if (!written) return null;
  const session = payload?.scan_identity?.scan_date ?? null;
  const when = dateTimeShort(written);
  if (!session && !when) return null;
  const stale = scanIsStale(payload?.stale_after, now);
  const title = [
    session ? `Setups from the close of ${fmtDay(session)}.` : null,
    `Scan written ${when ?? 'at an unknown time'}.`,
    stale
      ? `A newer scan was due by ${dateTimeShort(payload.stale_after) ?? 'now'}: either it has not run (the top bar shows the last run) or this page has not loaded it yet (reload).`
      : null,
  ].filter(Boolean).join(' ');
  return { stale, text: `Scan ${session ? fmtDay(session) : when}${stale ? ' · stale' : ''}`, title };
}
