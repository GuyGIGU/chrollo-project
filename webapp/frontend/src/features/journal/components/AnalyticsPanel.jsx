import React from 'react';
import RMultipleHistogram from './RMultipleHistogram';

const card = {
  background: 'var(--bg-panel)',
  border: '1px solid var(--border-color)',
  borderRadius: 'var(--radius-md, 8px)',
  padding: '16px',
};

const sectionTitle = {
  fontSize: 11,
  color: 'var(--text-muted)',
  textTransform: 'uppercase',
  letterSpacing: '1px',
  margin: '0 0 12px 0',
  fontWeight: 600,
};

export default function AnalyticsPanel() {
  return (
    <div style={{ marginTop: '2rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      <div style={card}>
        <h3 style={sectionTitle}>R-Multiple Distribution</h3>
        <RMultipleHistogram />
      </div>
    </div>
  );
}
