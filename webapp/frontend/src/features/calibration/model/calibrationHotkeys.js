// The Calibration page's keyboard loop: which key arms which marking tool, and
// which keystrokes the loop must leave alone. The rest of the loop (Enter
// saves, Escape disarms, e toggles the engine peek) lives with the page's
// state. Pure, so node --test pins the vocabulary.

// Tools b/r/s/x, events c/l/t/o/m/u (the marking bar's key legend).
export const HOTKEY_TOOLS = { r: 'rail-r', s: 'rail-s', x: 'span',
                              c: 'event:phase_c', l: 'event:lps', t: 'event:spring_test',
                              o: 'event:sos', m: 'event:mini_consolidation',
                              u: 'event:last_supper',
                              b: 'trigger' };

// Skipped while typing in any field, and for any modified key (a browser or
// OS shortcut, never a marking command).
export function isMarkingKeystroke(event) {
  const tag = event.target?.tagName;
  if (tag === 'INPUT' || tag === 'SELECT' || tag === 'TEXTAREA') return false;
  return !(event.metaKey || event.ctrlKey || event.altKey);
}
