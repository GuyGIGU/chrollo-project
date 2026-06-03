import { deriveTags, GROUP_LABELS, GROUP_ORDER, GROUP_TONES } from './setupTagsData';

const chipBase = {
  padding: '3px 7px',
  borderRadius: '5px',
  fontSize: '11px',
  fontWeight: 700,
  fontFamily: "'JetBrains Mono', monospace",
  lineHeight: 1.1,
  whiteSpace: 'nowrap',
};

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

export function TagRow({ subScores, flags, style }) {
  const tags = deriveTags(subScores, flags);
  if (tags.length === 0) return null;
  return (
    <div style={{ alignItems: 'center', display: 'flex', gap: '4px', flexWrap: 'wrap', ...style }}>
      {tags.map(tagDef => {
        const tone = GROUP_TONES[tagDef.group];
        return (
          <span
            key={tagDef.id}
            title={tagDef.title}
            style={{ ...chipBase, background: tone.bg, color: tone.fg }}
          >
            {tagDef.label}
          </span>
        );
      })}
    </div>
  );
}
