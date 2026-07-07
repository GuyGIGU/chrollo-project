import { QUALITY_LABELS } from '../../utils/archiveTabUtils';
import Modal from '../ui/Modal';

const fieldStyle = {
  background: 'var(--bg-panel)',
  border: '1px solid var(--border-color)',
  borderRadius: '6px',
  boxSizing: 'border-box',
  color: 'var(--text-main)',
  display: 'block',
  fontFamily: 'inherit',
  fontSize: '13px',
  marginTop: '4px',
  padding: '8px 10px',
  width: '100%',
};

export default function AddSetupModal({ form }) {
  if (!form.open) return null;
  const close = () => !form.adding && form.setOpen(false);
  return (
    <Modal
      onClose={close}
      overlayStyle={{
        alignItems: 'center',
        backdropFilter: 'blur(4px)',
        background: 'rgba(10,10,15,0.85)',
        display: 'flex',
        inset: 0,
        justifyContent: 'center',
        position: 'fixed',
        zIndex: 6000,
      }}
      contentStyle={{
        background: 'var(--bg-main)',
        border: '1px solid var(--border-color)',
        borderRadius: '12px',
        boxShadow: '0 20px 50px rgba(0,0,0,0.5)',
        maxWidth: '420px',
        padding: '24px',
        width: '100%',
      }}
    >
        <div style={{ fontSize: '16px', fontWeight: '700', marginBottom: '4px' }}>Add Setup to Archive</div>
        <div style={{ color: 'var(--text-muted)', fontSize: '11px', marginBottom: '16px' }}>
          Runs the screener at this date. Rejected if no LPS fires there.
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <Field label="Ticker">
            <input autoFocus placeholder="e.g. AAPL" style={{ ...fieldStyle, textTransform: 'uppercase' }} type="text" value={form.ticker} onChange={event => form.setTicker(event.target.value)} />
          </Field>
          <Field label="Scan date">
            <input style={fieldStyle} type="date" value={form.date} onChange={event => form.setDate(event.target.value)} />
          </Field>
          <Field label="Quality label (optional)">
            <select style={fieldStyle} value={form.label} onChange={event => form.setLabel(event.target.value)}>
              <option value="">-</option>
              {QUALITY_LABELS.map(label => <option key={label} value={label}>{label}</option>)}
            </select>
          </Field>
          <Field label="Notes (optional)">
            <textarea rows={3} style={{ ...fieldStyle, fontSize: '12px', resize: 'vertical' }} value={form.notes} onChange={event => form.setNotes(event.target.value)} />
          </Field>
        </div>
        {form.error && <ErrorMessage text={form.error} />}
        <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end', marginTop: '16px' }}>
          <ModalButton disabled={form.adding} onClick={() => form.setOpen(false)}>Cancel</ModalButton>
          <ModalButton primary disabled={form.adding || !form.ticker.trim()} onClick={form.addSetup}>
            {form.adding ? 'Adding...' : 'Add Setup'}
          </ModalButton>
        </div>
    </Modal>
  );
}

function Field({ children, label }) {
  return <label style={{ color: 'var(--text-muted)', fontSize: '11px' }}>{label}{children}</label>;
}

function ErrorMessage({ text }) {
  return (
    <div style={{
      background: 'rgba(199,107,115,0.12)',
      border: '1px solid rgba(199,107,115,0.4)',
      borderRadius: '6px',
      color: '#c76b73',
      fontSize: '11px',
      marginTop: '12px',
      padding: '8px 12px',
    }}>
      {text}
    </div>
  );
}

function ModalButton({ children, disabled, onClick, primary }) {
  return (
    <button
      disabled={disabled}
      onClick={onClick}
      style={{
        background: primary && !disabled ? 'var(--accent-active)' : primary ? 'var(--bg-hover)' : 'transparent',
        border: primary ? 'none' : '1px solid var(--border-color)',
        borderRadius: '6px',
        color: primary && !disabled ? 'var(--myth-ink)' : primary ? 'var(--text-muted)' : 'var(--text-main)',
        cursor: disabled ? 'not-allowed' : 'pointer',
        fontFamily: 'inherit',
        fontSize: '12px',
        fontWeight: primary ? '600' : '400',
        padding: '8px 14px',
      }}
    >
      {children}
    </button>
  );
}
