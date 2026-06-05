import React from 'react';

const STALE_CHUNK_RELOAD_PREFIX = 'chrollo:stale-chunk-reload:';

const isDynamicImportError = (error) => {
  const message = String(error?.message || error || '');
  return (
    error?.name === 'ChunkLoadError' ||
    message.includes('Failed to fetch dynamically imported module') ||
    message.includes('Importing a module script failed') ||
    message.includes('error loading dynamically imported module')
  );
};

const alreadyReloadedFor = (key) => {
  try {
    if (window.sessionStorage.getItem(key) === '1') return true;
    window.sessionStorage.setItem(key, '1');
    return false;
  } catch {
    return false;
  }
};

/**
 * Error Boundary that catches runtime errors in child components
 * and displays a fallback UI instead of crashing the entire app.
 */
class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error('[ErrorBoundary] Caught error:', error, errorInfo);
    if (!isDynamicImportError(error)) return;

    const reloadKey = `${STALE_CHUNK_RELOAD_PREFIX}${String(error?.message || '').slice(0, 180)}`;
    if (alreadyReloadedFor(reloadKey)) return;
    window.location.reload();
  }

  render() {
    if (this.state.hasError) {
      const staleChunk = isDynamicImportError(this.state.error);
      return (
        <div style={{
          padding: '2rem',
          textAlign: 'center',
          color: '#eb4956',
          background: 'rgba(235, 73, 86, 0.08)',
          border: '1px solid rgba(235, 73, 86, 0.25)',
          borderRadius: '8px',
          margin: '1rem'
        }}>
          <div style={{ fontSize: '16px', fontWeight: '600', marginBottom: '0.5rem' }}>
            {staleChunk ? 'App Update Needed' : 'Component Error'}
          </div>
          <div style={{ fontSize: '12px', color: '#9595a6' }}>
            {staleChunk
              ? 'The dashboard files changed while this tab was open. Reload to fetch the latest build.'
              : this.state.error?.message || 'An unexpected error occurred.'}
          </div>
          <button
            onClick={() => {
              if (staleChunk) window.location.reload();
              else this.setState({ hasError: false, error: null });
            }}
            style={{
              marginTop: '1rem', padding: '6px 16px', borderRadius: '6px',
              border: '1px solid #3f3f52', background: '#2b2b36',
              color: '#f0f0f0', cursor: 'pointer', fontSize: '12px'
            }}
          >
            {staleChunk ? 'Reload' : 'Retry'}
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

export default ErrorBoundary;
