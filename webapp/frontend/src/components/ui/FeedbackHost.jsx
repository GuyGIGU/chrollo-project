import { useEffect, useSyncExternalStore } from 'react';
import Modal from './Modal';
import { dismissToast, getFeedbackState, settleConfirm, subscribeFeedback } from './feedback';

// Renders the feedback store: a bottom-right toast stack + the (single)
// confirm dialog on the shared Modal primitive. Mounted once in AppShell.

const TONE_COLOR = {
  info: 'var(--accent-blue)',
  success: 'var(--success)',
  danger: 'var(--danger)',
  warning: 'var(--warning)',
};

function Toast({ item }) {
  // Each toast owns its auto-dismiss timer; clicking dismisses early.
  useEffect(() => {
    const timer = window.setTimeout(() => dismissToast(item.id), item.duration);
    return () => window.clearTimeout(timer);
  }, [item.id, item.duration]);

  return (
    <div
      role="status"
      onClick={() => dismissToast(item.id)}
      style={{
        background: 'var(--bg-panel)',
        border: '1px solid var(--border-color)',
        borderRadius: 'var(--radius-sm)',
        boxShadow: '0 12px 32px rgba(0,0,0,0.4)',
        color: 'var(--text-main)',
        cursor: 'pointer',
        display: 'flex',
        gap: 9,
        alignItems: 'flex-start',
        fontSize: 12.5,
        lineHeight: 1.5,
        maxWidth: 380,
        padding: '10px 14px',
        whiteSpace: 'pre-line',
        wordBreak: 'break-word',
      }}
    >
      <span style={{ width: 7, height: 7, borderRadius: '50%', flexShrink: 0, marginTop: 5, background: TONE_COLOR[item.tone] || TONE_COLOR.info }} />
      <span>{item.message}</span>
    </div>
  );
}

function ConfirmDialog({ confirm }) {
  return (
    <Modal onClose={() => settleConfirm(false)} contentStyle={confirmShellStyle}>
      <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-main)', marginBottom: 10 }}>
        {confirm.title}
      </div>
      <div style={{ fontSize: 12.5, lineHeight: 1.55, color: 'var(--text-muted)', whiteSpace: 'pre-line' }}>
        {confirm.message}
      </div>
      <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end', marginTop: 18 }}>
        <button type="button" style={cancelButtonStyle} onClick={() => settleConfirm(false)}>
          {confirm.cancelLabel}
        </button>
        <button
          type="button"
          style={{
            ...confirmButtonStyle,
            background: confirm.danger ? 'var(--danger)' : 'var(--accent-blue)',
          }}
          onClick={() => settleConfirm(true)}
        >
          {confirm.confirmLabel}
        </button>
      </div>
    </Modal>
  );
}

export default function FeedbackHost() {
  const { toasts, confirm } = useSyncExternalStore(subscribeFeedback, getFeedbackState);

  return (
    <>
      {toasts.length > 0 && (
        <div
          style={{
            position: 'fixed',
            right: 18,
            bottom: 18,
            display: 'flex',
            flexDirection: 'column',
            gap: 8,
            zIndex: 3000,
          }}
        >
          {toasts.map((item) => <Toast key={item.id} item={item} />)}
        </div>
      )}
      {confirm && <ConfirmDialog confirm={confirm} />}
    </>
  );
}

const confirmShellStyle = {
  background: 'var(--bg-panel)',
  border: '1px solid var(--border-color)',
  borderRadius: 8,
  boxShadow: '0 24px 70px rgba(0,0,0,0.42)',
  maxWidth: 460,
  padding: '18px 20px',
  width: 'min(460px, 92vw)',
};

const buttonBase = {
  border: 'none',
  borderRadius: 'var(--radius-sm)',
  cursor: 'pointer',
  fontFamily: 'inherit',
  fontSize: 12,
  fontWeight: 600,
  padding: '7px 16px',
};

const cancelButtonStyle = {
  ...buttonBase,
  background: 'transparent',
  border: '1px solid var(--border-color)',
  color: 'var(--text-main)',
};

const confirmButtonStyle = {
  ...buttonBase,
  color: '#fff',
};
