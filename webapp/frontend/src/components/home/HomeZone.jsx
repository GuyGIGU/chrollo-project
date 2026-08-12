import ErrorBoundary from '../ErrorBoundary';

// Skeleton + message helpers so every zone speaks the same loading/empty/error
// language and the layout doesn't reflow as data lands.
export function ZoneSkeleton({ rows = 3 }) {
  return (
    <div className="home-skeleton">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="home-skeleton-row" />
      ))}
    </div>
  );
}

export function ZoneMessage({ tone = 'muted', children }) {
  return (
    <div className="home-zone-msg" style={{ color: tone === 'error' ? 'var(--danger)' : 'var(--text-muted)' }}>
      {children}
    </div>
  );
}

/**
 * Shared chrome for a Home zone: a confident title, an always-visible handoff
 * link (shown even in the error state so the trader can route around a dead
 * zone), and a status-driven body. Wrapped in its OWN ErrorBoundary so a render
 * throw in one zone never blanks the page.
 */
export default function HomeZone({ title, icon, link, status = 'ready', error, empty, skeletonRows, children }) {
  return (
    <ErrorBoundary>
      <section className="home-zone instrument-tile">
        <div className="home-zone-head">
          <div className="home-zone-headl">
            {icon ? <span className="home-zone-icon">{icon}</span> : null}
            <h2 className="home-zone-title">{title}</h2>
          </div>
          {link}
        </div>
        <div className="home-zone-body">
          {status === 'loading' && <ZoneSkeleton rows={skeletonRows} />}
          {status === 'error' && <ZoneMessage tone="error">{error || 'Could not load.'}</ZoneMessage>}
          {status === 'empty' && <ZoneMessage>{empty || 'Nothing to show.'}</ZoneMessage>}
          {status === 'ready' && children}
        </div>
      </section>
    </ErrorBoundary>
  );
}
