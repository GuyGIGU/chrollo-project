import { useEffect } from 'react';

// Modal — the shared overlay behavior the app's dialogs repeated by hand:
// a fixed backdrop, click-outside-to-close, Escape-to-close, and
// stopPropagation on the inner shell. Composition over flags: the caller passes
// its own shell as children (no showHeader/variant props). The shell's look
// stays the caller's via contentStyle/contentClassName so migrating a dialog is
// behavior-preserving; the default backdrop is the standard dimmed scrim.
const defaultOverlayStyle = {
  position: 'fixed',
  inset: 0,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  background: 'rgba(8, 10, 15, 0.78)',
  zIndex: 2000,
  padding: 18,
};

function Modal({
  onClose,
  children,
  closeOnEscape = true,
  closeOnBackdrop = true,
  overlayStyle,
  overlayClassName,
  contentStyle,
  contentClassName,
  contentProps,
}) {
  useEffect(() => {
    if (!closeOnEscape) return undefined;
    const handleKeyDown = (event) => {
      if (event.key === 'Escape') onClose?.();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [closeOnEscape, onClose]);

  // A caller that supplies its own overlay class/style opts out of the default
  // inline scrim (e.g. the class-based .modal-overlay dialog); only fall back to
  // the default scrim when neither is given.
  const resolvedOverlayStyle =
    overlayStyle !== undefined
      ? overlayStyle
      : overlayClassName
        ? undefined
        : defaultOverlayStyle;

  return (
    <div
      className={overlayClassName}
      style={resolvedOverlayStyle}
      onClick={closeOnBackdrop ? onClose : undefined}
    >
      <div
        className={contentClassName}
        style={contentStyle}
        onClick={(event) => event.stopPropagation()}
        {...contentProps}
      >
        {children}
      </div>
    </div>
  );
}

export default Modal;
