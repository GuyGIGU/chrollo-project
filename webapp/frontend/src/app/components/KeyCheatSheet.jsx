import { useEffect, useState } from 'react';
import { useLocation } from 'react-router-dom';
import Modal from '../../shared/components/Modal';
import { hasCommandModifier, isPageKeystroke, isTypingTarget } from '../../shared/navigation/keyboardGuard';
import { keyLabel, keySectionsFor } from '../keyboard/keyMap';

// The '?' sheet: every key the app answers to, 'Everywhere' plus the current
// page's sections (app/keyboard/keyMap.js is the one list). Mounted once in the
// shell, so it works on every page and over the big chart too. It also owns the
// app-wide '/' (jump to the page's [data-page-search] box).
//
// While open it takes every keystroke at the window in the CAPTURE phase and
// stops it there, so nothing behind it reacts (an armed calibration tool, the
// big chart's arrows or Escape). Only propagation is stopped: Enter/Space on
// the close button and browser shortcuts still do their default thing.
function KeyCheatSheet() {
  const [open, setOpen] = useState(false);
  const { pathname } = useLocation();

  useEffect(() => {
    if (open) return undefined;
    const onKey = (event) => {
      if (event.key === '?' && !hasCommandModifier(event) && !isTypingTarget(event.target)) {
        event.preventDefault();
        setOpen(true);
        return;
      }
      if (event.key === '/' && isPageKeystroke(event)) {
        const box = document.querySelector('[data-page-search]');
        if (!box) return;
        event.preventDefault();   // focus the box without typing the '/' into it
        box.focus();
        box.select?.();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open]);

  useEffect(() => {
    if (!open) return undefined;
    const onKey = (event) => {
      event.stopPropagation();
      if (event.key === 'Escape' || event.key === '?') {
        event.preventDefault();
        setOpen(false);
      } else if (event.key === 'Tab') {
        // The Modal's own Tab trap never sees the key (stopped above); the
        // close button is the sheet's only control, so Tab stays put.
        event.preventDefault();
      }
    };
    window.addEventListener('keydown', onKey, true);
    return () => window.removeEventListener('keydown', onKey, true);
  }, [open]);

  if (!open) return null;

  const close = () => setOpen(false);
  return (
    <Modal
      onClose={close}
      closeOnEscape={false}
      overlayClassName="key-sheet-overlay"
      contentClassName="glass-panel key-sheet"
      contentProps={{ 'aria-label': 'Keyboard keys' }}
    >
      <header className="key-sheet-head">
        <span>Keyboard keys</span>
        <button type="button" className="btn btn-icon" aria-label="Close" onClick={close}>✕</button>
      </header>
      {keySectionsFor(pathname).map((section) => (
        <section key={section.id} className="key-sheet-section">
          <h3 className="key-sheet-title">{section.title}</h3>
          {section.rows.map((row) => (
            <div key={row.keys.join(' ')} className="key-sheet-row">
              <span className="key-sheet-keys">
                {row.keys.map((key) => <kbd key={key} className="key-cap">{keyLabel(key)}</kbd>)}
              </span>
              <span>{row.does}</span>
            </div>
          ))}
        </section>
      ))}
      <p className="key-sheet-foot">Keys never act while you are typing in a box. Esc or ? closes this list.</p>
    </Modal>
  );
}

export default KeyCheatSheet;
