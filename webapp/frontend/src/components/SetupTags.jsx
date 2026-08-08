import { useLayoutEffect, useRef, useState } from 'react';
import { GROUP_LABELS, GROUP_ORDER, GROUP_TONES } from './setupTagsData';
import { resolveTags } from './tagResolver';

const chipBase = {
  padding: '3px 7px',
  borderRadius: 'var(--radius-xs)',
  fontSize: '11px',
  fontWeight: 700,
  fontFamily: "'JetBrains Mono', monospace",
  lineHeight: 1.1,
  whiteSpace: 'nowrap',
};

const OVERFLOW_CHIP_WIDTH = 30;
const TAG_GAP = 4;

function compactLabel(label) {
  const firstSpace = label.indexOf(' ');
  return firstSpace === -1 ? label : label.slice(firstSpace + 1);
}

function TagChip({ compact, tagDef, style }) {
  const tone = GROUP_TONES[tagDef.group];
  return (
    <span
      title={tagDef.title}
      style={{ ...style, background: tone.bg, color: tone.fg }}
    >
      {compact ? compactLabel(tagDef.label) : tagDef.label}
    </span>
  );
}

function fitTags(containerWidth, tagWidths, rows = 1) {
  if (!containerWidth || tagWidths.length === 0) return tagWidths.length;

  // Budget = `rows` rows worth of width. A width-sum heuristic (not a true
  // greedy wrap), good enough to decide how many chips show before the +N.
  const budget = containerWidth * Math.max(1, rows);

  for (let count = tagWidths.length; count >= 0; count -= 1) {
    const hiddenCount = tagWidths.length - count;
    const tagWidth = tagWidths
      .slice(0, count)
      .reduce((total, width) => total + width, 0);
    const gapCount = count + (hiddenCount > 0 ? 1 : 0) - 1;
    const overflowWidth = hiddenCount > 0 ? OVERFLOW_CHIP_WIDTH : 0;
    const totalWidth = tagWidth + overflowWidth + Math.max(0, gapCount) * TAG_GAP;
    if (totalWidth <= budget) return count;
  }

  return 0;
}

export function TagLegend({ style }) {
  const groups = Object.keys(GROUP_LABELS).sort((a, b) => GROUP_ORDER[a] - GROUP_ORDER[b]);
  return (
    <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', alignItems: 'center', ...style }}>
      <span style={{ fontSize: '11px', color: 'var(--text-muted)', fontWeight: 500 }}>
        Tag colors:
      </span>
      {groups.map(group => {
        const tone = GROUP_TONES[group];
        return (
          <span key={group} style={{ display: 'inline-flex', alignItems: 'center', gap: '5px' }}>
            <span style={{
              width: '10px',
              height: '10px',
              borderRadius: '3px',
              background: tone.bg,
              border: `1px solid ${tone.fg}`,
            }} />
            <span style={{ fontSize: '11px', color: tone.fg, fontWeight: 600 }}>
              {GROUP_LABELS[group]}
            </span>
          </span>
        );
      })}
    </div>
  );
}

// Contract change (task 11): TagRow takes the WIRE PAYLOAD, not
// subScores-plus-flags — the ONE resolver decides the epoch (backend
// verdicts vs the legacy derive fallback), so the card, the lens, and the
// filter bar can never disagree about which chips a row carries.
export function TagRow({ data, maxTags, compact = false, rows = 1, style }) {
  const tags = resolveTags(data);
  const containerRef = useRef(null);
  const measureRef = useRef(null);
  const [fitCount, setFitCount] = useState(maxTags === 'auto' ? tags.length : maxTags);
  const chipStyle = compact
    ? { ...chipBase, fontSize: '10px', padding: '2px 5px' }
    : chipBase;
  const visibleLimit = maxTags === 'auto' ? fitCount : maxTags;
  const visibleTags = visibleLimit == null ? tags : tags.slice(0, visibleLimit);
  const hiddenTags = visibleLimit == null ? [] : tags.slice(visibleLimit);
  const tagKey = tags.map(tag => tag.id).join('|');

  useLayoutEffect(() => {
    if (maxTags !== 'auto') return undefined;

    const updateFitCount = () => {
      const container = containerRef.current;
      const measure = measureRef.current;
      if (!container || !measure) return;

      const widths = Array.from(measure.children).map(child => child.getBoundingClientRect().width);
      setFitCount(fitTags(container.clientWidth, widths, rows));
    };

    updateFitCount();

    if (!window.ResizeObserver || !containerRef.current) {
      window.addEventListener('resize', updateFitCount);
      return () => window.removeEventListener('resize', updateFitCount);
    }

    const observer = new ResizeObserver(updateFitCount);
    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, [maxTags, tagKey, rows]);

  if (tags.length === 0) return null;

  return (
    <div
      ref={containerRef}
      style={{ alignItems: 'center', display: 'flex', gap: `${TAG_GAP}px`, flexWrap: 'wrap', position: 'relative', ...style }}
    >
      {visibleTags.map(tagDef => (
        <TagChip compact={compact} key={tagDef.id} tagDef={tagDef} style={chipStyle} />
      ))}
      {hiddenTags.length > 0 && (
        <span
          title={hiddenTags.map(tag => tag.label).join(', ')}
          style={{
            ...chipStyle,
            background: 'rgba(255,255,255,0.05)',
            color: 'var(--text-muted)',
          }}
        >
          +{hiddenTags.length}
        </span>
      )}
      {maxTags === 'auto' && (
        <div
          ref={measureRef}
          style={{
            display: 'flex',
            gap: `${TAG_GAP}px`,
            height: 0,
            left: 0,
            overflow: 'hidden',
            pointerEvents: 'none',
            position: 'absolute',
            top: 0,
            visibility: 'hidden',
          }}
        >
          {tags.map(tagDef => (
            <TagChip compact={compact} key={tagDef.id} tagDef={tagDef} style={chipStyle} />
          ))}
        </div>
      )}
    </div>
  );
}
