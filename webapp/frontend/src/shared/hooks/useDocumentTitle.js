import { useEffect } from 'react';
import { APP_TITLE, documentTitle } from '../navigation/documentTitle';

/**
 * Write the browser tab's title for the page on screen (the words come from
 * shared/navigation/documentTitle.js). Two rules:
 *
 * - ONE owner per route. The component that knows the page's detail calls it,
 *   and nothing else on that route does: never also a child, and never the Route
 *   wrapper of an owner (documentTitle.test.js pins the list of owners).
 * - On unmount it restores the constant APP_TITLE, never a captured previous
 *   title. The old route's cleanup runs before the new route's effects in the
 *   same commit, so the next page's title always wins.
 */
export default function useDocumentTitle(page, detail = null, { unsaved = false } = {}) {
  const title = documentTitle(page, detail, { unsaved });

  useEffect(() => {
    document.title = title;
    return () => { document.title = APP_TITLE; };
  }, [title]);
}
