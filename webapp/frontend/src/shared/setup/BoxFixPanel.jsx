import { fixPrompt } from './boxFix';
import { EVENT_NAMES, EVENT_TAG, eventPrompt, eventWords } from './boxFixEvents';

// The "fix the box" window (Sat 18/10/2026, his correction of the first cut: "give me an interface,
// clicking the button makes a pop up window appear with all of the relevant options, does it look
// like I am going to remember every single keybind?"). The toolbar's button (or B) opens it over the
// daily chart; everything is a button here: the two lines, each event with what to click, the placed
// events with a × each, Save, Clear and close. The letters are shown on the buttons as hints only.
// `fix` is useBoxFix's handle; `reader` the pair the reader showed (boxFix.readerPair).
const EVENT_HOW = {
  spring: 'click its tip',
  upthrust: 'click its top',
  sos: 'click the launch low, then the top',
  lps: 'click its first and last day',
  former_lps: 'click its first and last day',
  span: 'click its first and last day, then name it',
  mini: 'click two corners',
};

export default function BoxFixPanel({ fix, reader }) {
  const linesActive = fix.tool == null;
  return (
    <div className="lens-fix-panel" role="dialog" aria-label="Fix the box">
      <div className="lens-fix-panel-head">
        <span className="lens-fix-word">FIX THE BOX</span>
        <button type="button" className="btn btn-icon" onClick={fix.toggle} title="Close (B)" aria-label="Close the fix window">✕</button>
      </div>
      <div className="lens-fix-prompt">{eventPrompt(fix.marks) ?? fixPrompt(fix.draft)}</div>
      <div className="lens-fix-reader">
        {reader ? `reader: R ${reader.r.toFixed(2)} (${reader.rDay}) · S ${reader.s.toFixed(2)} (${reader.sDay})` : 'reader: no box shown'}
      </div>

      <div className="lens-fix-group-name">What the next click places</div>
      <button
        type="button"
        className="btn lens-fix-option"
        aria-pressed={linesActive}
        onClick={() => fix.arm(null)}
      >
        <span className="lens-fix-option-name">The two lines</span>
        <span className="lens-fix-option-how">click the climax bar, then the reaction bar, in either order</span>
      </button>
      {Object.entries(EVENT_TAG).map(([kind, tag]) => (
        <button
          key={kind}
          type="button"
          className="btn lens-fix-option"
          aria-pressed={fix.tool === kind}
          onClick={() => fix.arm(kind)}
        >
          <span className="lens-fix-option-name">{EVENT_NAMES[kind]} <kbd>{tag}</kbd></span>
          <span className="lens-fix-option-how">{EVENT_HOW[kind]}</span>
        </button>
      ))}

      {(fix.draft.r != null || fix.draft.s != null || fix.events.length > 0) && (
        <>
          <div className="lens-fix-group-name">Placed</div>
          <div className="lens-fix-events">
            {fix.draft.r != null && <span className="lens-fix-chip">resistance {fix.draft.r.toFixed(2)} ({fix.draft.rDay})</span>}
            {fix.draft.s != null && <span className="lens-fix-chip">support {fix.draft.s.toFixed(2)} ({fix.draft.sDay})</span>}
            {fix.events.map((event, index) => (
              <span key={`${event.kind}-${event.first_day}-${index}`} className="lens-fix-chip">
                {eventWords(event)}
                {event.kind === 'span' && (
                  <input
                    type="text"
                    className="lens-fix-label"
                    placeholder="name it"
                    aria-label="Name this span"
                    value={event.label ?? ''}
                    onChange={(e) => fix.label(index, e.target.value)}
                  />
                )}
                <button type="button" className="lens-fix-chip-x" aria-label={`Remove ${EVENT_NAMES[event.kind]}`} onClick={() => fix.remove(index)}>×</button>
              </span>
            ))}
          </div>
        </>
      )}

      <div className="lens-fix-acts">
        <button type="button" className="btn btn-primary" disabled={!fix.complete || fix.saving} onClick={fix.save}>{fix.saving ? 'Saving…' : 'Save fix'}</button>
        <button type="button" className="btn" disabled={fix.draft.r == null && fix.draft.s == null && fix.events.length === 0} onClick={fix.clear}>Clear</button>
        {fix.saved != null && <span className="lens-fix-saved">{fix.saved > 1 ? `saved (revision ${fix.saved})` : 'saved'} ✓</span>}
        {fix.error && <span className="lens-fix-error">{fix.error}</span>}
      </div>
    </div>
  );
}
