export const overlayStyle = {
  background: 'rgba(0,0,0,0.54)',
  display: 'flex',
  inset: 0,
  justifyContent: 'flex-end',
  position: 'fixed',
  zIndex: 1000,
};

export const drawerStyle = {
  background: 'var(--bg-panel)',
  borderLeft: '1px solid var(--border-color)',
  boxShadow: '-8px 0 24px rgba(0,0,0,0.3)',
  display: 'flex',
  flexDirection: 'column',
  height: '100%',
  width: 'min(760px, 100%)',
};

export const headerStyle = {
  alignItems: 'center',
  borderBottom: '1px solid var(--border-color)',
  display: 'flex',
  gap: 12,
  justifyContent: 'space-between',
  padding: '16px 20px',
};

export const bodyStyle = {
  display: 'flex',
  flex: 1,
  flexDirection: 'column',
  gap: 14,
  overflowY: 'auto',
  padding: 20,
};

export const eyebrowStyle = {
  color: 'var(--text-muted)',
  fontSize: 10,
  fontWeight: 800,
  letterSpacing: '0.08em',
  textTransform: 'uppercase',
};

export const titleStyle = {
  color: 'var(--accent-blue)',
  fontSize: 22,
  fontWeight: 850,
  marginTop: 2,
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
};

export const titleMetaStyle = {
  color: 'var(--text-muted)',
  fontSize: 12,
  fontWeight: 700,
  marginLeft: 8,
};

export const closeButtonStyle = {
  background: 'transparent',
  border: '1px solid var(--border-color)',
  borderRadius: 6,
  color: 'var(--text-muted)',
  cursor: 'pointer',
  fontSize: 16,
  fontWeight: 900,
  height: 30,
  lineHeight: 1,
  width: 30,
};

export const cockpitGridStyle = {
  display: 'grid',
  gap: 8,
  gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))',
};

export const metricStyle = {
  background: 'rgba(255,255,255,0.025)',
  border: '1px solid var(--border-color)',
  borderRadius: 8,
  minHeight: 76,
  minWidth: 0,
  padding: '10px 11px',
};

export const metricLabelStyle = {
  color: 'var(--text-faint)',
  display: 'block',
  fontSize: 10,
  fontWeight: 800,
  letterSpacing: '0.04em',
  textTransform: 'uppercase',
};

export const metricValueStyle = {
  display: 'block',
  fontSize: 16,
  fontWeight: 850,
  marginTop: 7,
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
};

export const metricSubStyle = {
  color: 'var(--text-muted)',
  display: 'block',
  fontSize: 10,
  marginTop: 4,
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
};

export const panelStyle = {
  background: 'rgba(255,255,255,0.025)',
  border: '1px solid var(--border-color)',
  borderRadius: 8,
  display: 'flex',
  flexDirection: 'column',
  gap: 12,
  padding: 14,
};

export const sectionHeaderStyle = {
  alignItems: 'center',
  display: 'flex',
  gap: 12,
  justifyContent: 'space-between',
};

export const sectionTitleStyle = {
  color: 'var(--text-main)',
  display: 'block',
  fontSize: 15,
  marginTop: 3,
};

export const saveGroupStyle = {
  alignItems: 'center',
  display: 'flex',
  gap: 8,
};

export const saveMessageStyle = (message) => ({
  color: message === 'Saved' ? 'var(--success)' : 'var(--danger)',
  fontSize: 11,
  fontWeight: 700,
});

export const saveButtonStyle = (disabled) => ({
  background: disabled ? 'rgba(91, 138, 255, 0.35)' : 'var(--accent-blue)',
  border: 'none',
  borderRadius: 6,
  color: '#fff',
  cursor: disabled ? 'default' : 'pointer',
  fontSize: 12,
  fontWeight: 800,
  minWidth: 76,
  padding: '8px 13px',
});

export const labelStyle = {
  color: 'var(--text-muted)',
  display: 'block',
  fontSize: 10,
  fontWeight: 800,
  letterSpacing: '0.06em',
  marginBottom: 5,
  textTransform: 'uppercase',
};

export const inputStyle = {
  background: 'var(--bg-main)',
  border: '1px solid var(--border-color)',
  borderRadius: 6,
  boxSizing: 'border-box',
  color: 'var(--text-main)',
  fontFamily: 'inherit',
  fontSize: 13,
  minHeight: 36,
  padding: '8px 10px',
  width: '100%',
};

export const textareaStyle = {
  ...inputStyle,
  minHeight: 82,
  resize: 'vertical',
};

export const inputGridStyle = {
  display: 'grid',
  gap: 10,
  gridTemplateColumns: 'repeat(3, minmax(0, 1fr))',
};

export const sideConvictionStyle = {
  display: 'grid',
  gap: 12,
  gridTemplateColumns: 'minmax(160px, 0.75fr) minmax(220px, 1.25fr)',
};

export const segmentedStyle = {
  display: 'grid',
  gap: 6,
  gridTemplateColumns: '1fr 1fr',
};

export const segmentButtonStyle = (active) => ({
  background: active ? 'var(--accent-blue)' : 'var(--bg-main)',
  border: `1px solid ${active ? 'var(--accent-blue)' : 'var(--border-color)'}`,
  borderRadius: 6,
  color: active ? '#fff' : 'var(--text-muted)',
  cursor: 'pointer',
  fontSize: 12,
  fontWeight: 850,
  padding: '9px 0',
});

export const convictionStyle = {
  display: 'grid',
  gap: 5,
  gridTemplateColumns: 'repeat(10, minmax(0, 1fr))',
};

export const convictionButtonStyle = (active) => ({
  background: active ? 'var(--accent-blue)' : 'var(--bg-main)',
  border: `1px solid ${active ? 'var(--accent-blue)' : 'var(--border-color)'}`,
  borderRadius: 5,
  color: active ? '#fff' : 'var(--text-muted)',
  cursor: 'pointer',
  fontSize: 11,
  fontWeight: 800,
  height: 30,
  padding: 0,
});

export const targetEditorStyle = {
  display: 'grid',
  gap: 8,
};

export const targetEditRowStyle = {
  alignItems: 'center',
  display: 'grid',
  gap: 8,
  gridTemplateColumns: '38px minmax(90px, 1fr) minmax(58px, 0.5fr) 52px minmax(88px, 0.75fr)',
};

export const targetLabelStyle = {
  color: 'var(--accent-blue)',
  fontSize: 12,
  fontWeight: 850,
};

export const targetInputStyle = {
  ...inputStyle,
  minHeight: 32,
  padding: '6px 9px',
};

export const targetQtyStyle = {
  ...targetInputStyle,
};

export const rButtonStyle = {
  background: 'var(--bg-main)',
  border: '1px solid var(--border-color)',
  borderRadius: 6,
  color: 'var(--text-muted)',
  cursor: 'pointer',
  fontSize: 11,
  fontWeight: 800,
  height: 32,
};

export const targetStateStyle = {
  color: 'var(--text-muted)',
  fontSize: 11,
  fontWeight: 700,
  overflow: 'hidden',
  textAlign: 'right',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
};

export const secondaryGridStyle = {
  display: 'grid',
  gap: 10,
};

export const detailsStyle = {
  background: 'rgba(255,255,255,0.018)',
  border: '1px solid var(--border-color)',
  borderRadius: 8,
};

export const summaryStyle = {
  color: 'var(--text-main)',
  cursor: 'pointer',
  fontSize: 12,
  fontWeight: 800,
  padding: '11px 13px',
};

export const detailsBodyStyle = {
  borderTop: '1px solid var(--border-color)',
  padding: 13,
};

export const alertStyle = {
  alignItems: 'center',
  border: '1px solid',
  borderRadius: 8,
  color: 'var(--text-main)',
  display: 'flex',
  fontSize: 12,
  gap: 10,
  justifyContent: 'space-between',
  padding: '10px 12px',
};

export const alertToneStyle = (level) => {
  if (level === 'critical' || level === 'danger') {
    return { background: 'rgba(242, 103, 112, 0.11)', borderColor: 'rgba(242, 103, 112, 0.34)' };
  }
  if (level === 'warning') {
    return { background: 'rgba(240, 190, 60, 0.10)', borderColor: 'rgba(240, 190, 60, 0.30)' };
  }
  return { background: 'rgba(91, 138, 255, 0.10)', borderColor: 'rgba(91, 138, 255, 0.30)' };
};

export const mutedStyle = {
  color: 'var(--text-muted)',
  fontSize: 11,
  fontWeight: 700,
};
