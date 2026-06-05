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
  color: '#fff',
  background: 'var(--accent-blue)',
  border: 'none',
  borderRadius: 'var(--radius-pill, 999px)',
  cursor: 'pointer',
  textTransform: 'uppercase',
  letterSpacing: '1px',
};

export const convBtnBase = {
  flex: 1,
  padding: '8px 0',
  fontSize: 13,
  fontWeight: 700,
  borderRadius: 'var(--radius-md, 6px)',
  border: '1px solid var(--border-color)',
  background: 'var(--bg-main)',
  color: 'var(--text-muted)',
  cursor: 'pointer',
  fontFamily: 'inherit',
};

export const convBtnActive = {
  background: 'var(--accent-blue)',
  borderColor: 'var(--accent-blue)',
  color: '#fff',
};
