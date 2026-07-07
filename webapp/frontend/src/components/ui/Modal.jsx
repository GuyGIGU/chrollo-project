import { useEffect, useRef } from 'react';

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

// Elements the Tab key may land on; used to keep focus inside the open dialog.
const FOCUSABLE =
  'a[href], button:not([disabled]), textarea, input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

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
  const contentRef = useRef(null);

  useEffect(() => {
    if (!closeOnEscape) return undefined;
    const handleKeyDown = (event) => {
      if (event.key === 'Escape') onClose?.();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [closeOnEscape, onClose]);

  // Move focus into the dialog on open, keep Tab cycling inside it (the scrim
  // implies the background is inert — honor that for the keyboard too), and
  // restore focus to the invoking control on close.
  useEffect(() => {
    const previouslyFocused = document.activeElement;
    const node = contentRef.current;
    if (node) (node.querySelector(FOCUSABLE) || node).focus?.();
    const handleTab = (event) => {
      if (event.key !== 'Tab' || !contentRef.current) return;
      const items = contentRef.current.querySelectorAll(FOCUSABLE);
      if (items.length === 0) return;
      const first = items[0];
      const last = items[items.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    window.addEventListener('keydown', handleTab);
    return () => {
      window.removeEventListener('keydown', handleTab);
      previouslyFocused?.focus?.();
    };
  }, []);

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
        ref={contentRef}
        tabIndex={-1}
        role="dialog"
        aria-modal="true"
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
