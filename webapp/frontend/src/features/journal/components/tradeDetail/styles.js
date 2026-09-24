export const labelStyle = {
  fontSize: 10,
  color: 'var(--text-muted)',
  textTransform: 'uppercase',
  letterSpacing: '1px',
  fontWeight: 600,
  marginBottom: 4,
  display: 'block',
};

export const textareaStyle = {
  width: '100%',
  minHeight: 80,
  padding: 10,
  background: 'var(--bg-main)',
  border: '1px solid var(--border-color)',
  borderRadius: 'var(--radius-md, 6px)',
  color: 'var(--text-main, #e0e0e6)',
  fontSize: 13,
  fontFamily: 'inherit',
  resize: 'vertical',
  boxSizing: 'border-box',
};

export const inputStyle = {
  ...textareaStyle,
  minHeight: 'unset',
  padding: '8px 10px',
};

export const btnPrimary = {
  padding: '8px 16px',
  fontSize: 11,
  fontWeight: 600,
  color: 'var(--myth-ink)',
  background: 'var(--accent-active)',
  border: 'none',
  borderRadius: 'var(--radius-pill, 999px)',
  cursor: 'pointer',
  textTransform: 'uppercase',
  letterSpacing: '1px',
};
