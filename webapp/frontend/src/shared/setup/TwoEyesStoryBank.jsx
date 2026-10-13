import { useState } from 'react';
import { twoEyesStory } from './twoEyesStory.js';
import { formatScore } from '../formatting/scoreFormat.js';
import { EMPTY } from '../formatting/format.js';

// The grade panel's bank for a row the two-eyes reader wrote (Tue 13/10/2026): the grade, then the read left to right
// in chart order — the box, each word of the story, the mini, the LPS. The same chrome as the old chapters (one
// continuous hued rule across the top, a narrow rail for a word, the number line below it), so the panel reads the
// same whichever reader wrote the row; only what fills it is the new reader's own. twoEyesStory owns the words.

// Hover/focus: the column engages locally and lights its own band on the chart (each band has its own id).
const engageBind = (column, onEngage, onRegionChange) => ({
  onBlur: () => { onEngage(null); onRegionChange?.(null); },
  onFocus: () => { onEngage(column.key); onRegionChange?.(column.region); },
  onMouseEnter: () => { onEngage(column.key); onRegionChange?.(column.region); },
  onMouseLeave: () => { onEngage(null); onRegionChange?.(null); },
  type: 'button',
});

function WordRail({ column, engaged, onEngage, onRegionChange }) {
  const Element = column.region ? 'button' : 'div';
  const bind = column.region ? engageBind(column, onEngage, onRegionChange) : {};
  return (
    <div className={['story-col', 'story-col-mark', column.phase ? `phase-bin-${column.phase}` : '',
      engaged === column.key ? 'is-engaged' : ''].filter(Boolean).join(' ')}
    >
      <Element
        {...bind}
        className={['story-face', 'story-face-mark', column.region ? '' : 'is-static',
          engaged === column.key ? 'is-engaged' : ''].filter(Boolean).join(' ')}
        title={column.title}
      >
        <span className="story-gauge is-mark" />
        <span className="story-value is-mark">
          <span className="phase-bin-token">{column.token}</span>
        </span>
        <span className="story-name">
          <span className="story-name-text">{column.name}</span>
        </span>
        <span className="story-detail is-mark">{column.detail}</span>
      </Element>
    </div>
  );
}

function FactColumn({ column, engaged, onEngage, onRegionChange }) {
  const Element = column.region ? 'button' : 'div';
  const bind = column.region ? engageBind(column, onEngage, onRegionChange) : {};
  const [whole, decimal] = column.figure != null ? column.figure.split('.') : [];
  return (
    <div className={['story-col', column.phase ? `phase-bin-${column.phase}` : '',
      engaged === column.key ? 'is-engaged' : ''].filter(Boolean).join(' ')}
    >
      <Element
        {...bind}
        className={['story-face', column.region ? '' : 'is-static',
          engaged === column.key ? 'is-engaged' : ''].filter(Boolean).join(' ')}
        title={column.title}
      >
        {/* A fill only where there is a measured share (the box: its days with a bar in it); a hairline otherwise,
            never an empty track that would read as a measured zero. */}
        {column.fraction != null ? (
          <span className="story-gauge">
            <span className="story-gauge-fill" style={{ width: `${(column.fraction * 100).toFixed(1)}%` }} />
          </span>
        ) : <span className="story-gauge is-mark" />}
        <span className={`story-value${column.figure != null ? '' : ' is-absent'}`}>
          {column.figure != null
            ? <>{whole}{decimal != null ? <span className="story-dec">.{decimal}</span> : null}{column.unit ? <span className="story-unit">{column.unit}</span> : null}</>
            : 'not read'}
        </span>
        <span className="story-name">
          <span className="phase-bin-token">{column.token}</span>
          {column.name === column.token ? null : <span className="story-name-text">{column.name}</span>}
        </span>
        <span className="story-detail">{column.detail}</span>
      </Element>
    </div>
  );
}

export default function TwoEyesStoryBank({ data, grade, onRegionChange, regions = [] }) {
  const { columns, footnote } = twoEyesStory(data, regions);
  const [engaged, setEngaged] = useState(null);
  // Words take the narrow rail; the box, the mini and the LPS share what is left, capped like the old chapters.
  const track = columns
    .map((column) => (column.kind === 'mark' ? 'var(--story-mark-w)' : 'minmax(0, var(--story-col-max))'))
    .join(' ');
  return (
    <>
      <div className="story-bank" style={{ '--story-track': track }}>
        <div className="story-total">
          <span className="story-total-fig" title={grade.title}>
            <span className="story-total-value">{grade.value != null ? formatScore(grade.value) : EMPTY}</span>
            {grade.scale ? <span className="story-total-scale">{grade.scale}</span> : null}
          </span>
          <span className="story-total-label">{grade.label}</span>
          <small className="story-total-note">{grade.note}</small>
        </div>
        {columns.map((column) => (column.kind === 'mark' ? (
          <WordRail column={column} engaged={engaged} key={column.key} onEngage={setEngaged} onRegionChange={onRegionChange} />
        ) : (
          <FactColumn column={column} engaged={engaged} key={column.key} onEngage={setEngaged} onRegionChange={onRegionChange} />
        )))}
      </div>
      {footnote ? <p className="story-footnote">{footnote}</p> : null}
    </>
  );
}
