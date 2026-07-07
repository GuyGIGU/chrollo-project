import { useCallback, useEffect, useRef, useState } from 'react';

// Elements the Tab key may land on; used to seat focus inside an open popover.
const FOCUSABLE =
  'a[href], button:not([disabled]), textarea, input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

// Popover — a small anchored, NON-modal disclosure shared by the screener
// command bar's Filters and Data panels. It gives the app's hand-rolled
// dropdowns the a11y they skipped: opening moves focus into the panel, Escape
// closes and restores focus to the trigger, and a pointer-down outside the
// anchor closes it (focus left where it landed). Unlike ui/Modal it does NOT
// trap focus or dim the page — Tab is free to leave, which is the correct
// contract for a lightweight popover. The trigger is supplied via renderTrigger
// so the caller keeps its own button styling; the panel anchors under it.
export default function Popover({
  renderTrigger,        // ({ open, toggle, triggerRef }) => node
  children,             // panel content
  align = 'left',       // which edge of the trigger the panel aligns to
  panelWidth = 300,
  panelLabel,           // aria-label for the panel
}) {
  const [open, setOpen] = useState(false);
  const anchorRef = useRef(null);
  const panelRef = useRef(null);
  const triggerRef = useRef(null);

  const close = useCallback((restoreFocus) => {
    setOpen(false);
    if (restoreFocus) triggerRef.current?.focus?.();
  }, []);

  useEffect(() => {
    if (!open) return undefined;
    // Seat focus on the first control in the panel so the keyboard lands inside.
    const node = panelRef.current;
    if (node) (node.querySelector(FOCUSABLE) || node).focus?.();

    const onKeyDown = (event) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        close(true);
      }
    };
    // Capture so a click anywhere outside closes before it does anything else;
    // native <select> option picks fire in the OS layer (no page pointerdown),
    // so choosing a filter value does not trip this.
    const onPointerDown = (event) => {
      if (anchorRef.current && !anchorRef.current.contains(event.target)) close(false);
    };
    document.addEventListener('keydown', onKeyDown);
    document.addEventListener('pointerdown', onPointerDown, true);
    return () => {
      document.removeEventListener('keydown', onKeyDown);
      document.removeEventListener('pointerdown', onPointerDown, true);
    };
  }, [open, close]);

  return (
    <div ref={anchorRef} style={{ position: 'relative', display: 'inline-flex' }}>
      {renderTrigger({ open, toggle: () => setOpen((value) => !value), triggerRef })}
      {open && (
        <div
          ref={panelRef}
          role="dialog"
          aria-label={panelLabel}
          tabIndex={-1}
          style={{
            position: 'absolute',
            top: 'calc(100% + 6px)',
            [align]: 0,
            zIndex: 50,
            width: panelWidth,
            maxWidth: '90vw',
            background: 'var(--bg-panel)',
            border: '1px solid var(--border-color)',
            borderRadius: 'var(--radius-sm)',
            boxShadow: 'inset 0 1px 0 rgba(255, 255, 255, 0.035), 0 12px 30px -12px rgba(0, 0, 0, 0.6)',
            padding: '12px 14px',
          }}
        >
          {children}
        </div>
      )}
    </div>
  );
}
