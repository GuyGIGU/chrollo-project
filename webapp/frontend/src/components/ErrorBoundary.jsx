import React from 'react';

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
  }

  render() {
    if (this.state.hasError) {
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
            Component Error
          </div>
          <div style={{ fontSize: '12px', color: '#9595a6' }}>
            {this.state.error?.message || 'An unexpected error occurred.'}
          </div>
          <button
            onClick={() => this.setState({ hasError: false, error: null })}
            style={{
              marginTop: '1rem', padding: '6px 16px', borderRadius: '6px',
              border: '1px solid #3f3f52', background: '#2b2b36',
              color: '#f0f0f0', cursor: 'pointer', fontSize: '12px'
            }}
          >
            Retry
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

export default ErrorBoundary;
