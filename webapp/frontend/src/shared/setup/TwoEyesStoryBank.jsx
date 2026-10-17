import { useState } from 'react';
import { formatScore } from '../formatting/scoreFormat.js';
import { EMPTY } from '../formatting/format.js';
import { dayMonth, phaseBoard } from './phaseBoard.js';

// THE PHASE BOARD (Thu 16/10/2026, his design): "we Set the Phases at the top. then the events that occurred within
// these phases below them." Phase A is the root swing the reader chose for the box (the climax and its reaction);
// Phase B is gone ("the only event that it has is upthrust and we can represent it on its own anyways"), so the
// upthrust stands in a column of its own; Phase C holds the spring and its test; Phase D "can start from a bunch of
// different events" (the recovery test, an SOS, an LPS, a mini, or straight after the middle) and holds the SOS, the
// last supper, the mini and the LPS. The grade's letter is NOT repeated here: the top bar carries it. The score and
// its two facts are one line over the phases. Every fact arrives resolved on the wire (EC-28); this file only
// arranges them. Hover or focus an event and its band lights on the chart (the same region ids as before).

const engageBind = (line, onEngage, onRegionChange) => ({
  onBlur: () => { onEngage(null); onRegionChange?.(null); },
  onFocus: () => { onEngage(line.key); onRegionChange?.(line.region); },
  onMouseEnter: () => { onEngage(line.key); onRegionChange?.(line.region); },
  onMouseLeave: () => { onEngage(null); onRegionChange?.(null); },
  type: 'button',
});

function EventLine({ line, engaged, onEngage, onRegionChange }) {
  const Element = line.region ? 'button' : 'div';
  const bind = line.region ? engageBind(line, onEngage, onRegionChange) : {};
  return (
    <Element {...bind} className={['phase-event', line.region ? '' : 'is-static', engaged === line.key ? 'is-engaged' : ''].filter(Boolean).join(' ')} title={line.title}>
      <span className="phase-event-dot" />
      <span className="phase-event-body">
        <span className="phase-event-head">
          <span className="phase-event-name">{line.name}</span>
          {line.day ? <span className="phase-event-day">{dayMonth(line.day)}</span> : null}
          {line.hero ? <span className="phase-event-hero">{line.hero}</span> : null}
        </span>
        <span className="phase-event-text">{line.sentence}</span>
      </span>
    </Element>
  );
}

export default function TwoEyesStoryBank({ data, grade, onRegionChange, regions = [] }) {
  const board = phaseBoard(data, regions);
  const [engaged, setEngaged] = useState(null);
  if (!board) return null;
  return (
    <div className="phase-board">
      <div className="phase-board-score" title={grade?.title}>
        <span className="phase-board-score-value">{board.score != null ? formatScore(board.score) : EMPTY}</span>
        <span className="phase-board-score-scale">/100</span>
        <span className="phase-board-score-note">{board.note ?? grade?.note ?? ''}</span>
      </div>
      <div className="phase-columns">
        {board.phases.map((phase) => (
          <section className={['phase-col', `phase-bin-${phase.key}`, phase.aside ? 'is-aside' : ''].filter(Boolean).join(' ')} key={phase.key}>
            <header className="phase-head">
              <span className="phase-head-rule" />
              <span className="phase-head-row">
                <span className="phase-bin-token">{phase.token}</span>
                <span className="phase-head-name">{phase.name}</span>
              </span>
              <span className="phase-head-meaning">{phase.meaning}</span>
            </header>
            <div className="phase-events">
              {phase.lines.map((line) => (
                <EventLine engaged={engaged} key={line.key} line={line} onEngage={setEngaged} onRegionChange={onRegionChange} />
              ))}
            </div>
          </section>
        ))}
      </div>
      {!board.told ? <p className="story-footnote">No story came with this row: the archive keeps the boxes and the grade, and the story (spring, SOS, last supper) rides the night's scan.</p> : null}
    </div>
  );
}
