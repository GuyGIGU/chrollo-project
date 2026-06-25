import React, { useEffect, useMemo, useRef, useState } from 'react';
import { API_BASE } from '../api';

const CAT_COLOR = {
  setup: 'var(--accent-blue)',
  mistake: 'var(--danger)',
  custom: 'var(--text-muted)',
};

const pillStyle = (cat, selected) => ({
  display: 'inline-flex',
  alignItems: 'center',
  gap: '4px',
  padding: '2px 8px',
  borderRadius: 'var(--radius-pill, 12px)',
  fontSize: '11px',
  fontWeight: 500,
  border: `1px solid ${CAT_COLOR[cat] || 'var(--border-color)'}`,
  background: selected ? (CAT_COLOR[cat] || 'var(--text-muted)') : 'transparent',
  color: selected ? '#fff' : (CAT_COLOR[cat] || 'var(--text-muted)'),
  cursor: 'pointer',
  userSelect: 'none',
  transition: 'all 0.15s',
});

export default function TagPicker({ value = [], onChange, category = 'custom', disabled = false }) {
  const [all, setAll] = useState([]);
  const [query, setQuery] = useState('');
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const wrapRef = useRef(null);

  const refresh = async () => {
    try {
      const r = await fetch(`${API_BASE}/tags/`);
      if (r.ok) setAll(await r.json());
    } catch { /* ignore */ }
  };

  useEffect(() => { refresh(); }, []);

  useEffect(() => {
    const onDocClick = (e) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener('mousedown', onDocClick);
    return () => document.removeEventListener('mousedown', onDocClick);
  }, []);

  const selectedIds = useMemo(() => new Set((value || []).map(t => t.id)), [value]);
  const q = query.trim().toLowerCase();
  const suggestions = useMemo(() => {
    return all
      .filter(t => !selectedIds.has(t.id))
      .filter(t => !q || t.name.toLowerCase().includes(q))
      .slice(0, 10);
  }, [all, selectedIds, q]);

  const exactMatch = all.find(t => t.name.toLowerCase() === q);
  const canCreate = q.length > 0 && !exactMatch;

  const addTag = (tag) => {
    if (!tag || selectedIds.has(tag.id)) return;
    onChange?.([...(value || []), tag]);
    setQuery('');
  };

  const removeTag = (tagId) => {
    onChange?.((value || []).filter(t => t.id !== tagId));
  };

  const createAndAdd = async () => {
    if (!q) return;
    setLoading(true);
    try {
      const r = await fetch(`${API_BASE}/tags/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: q, category }),
      });
      if (r.ok) {
        const tag = await r.json();
        setAll(prev => prev.some(t => t.id === tag.id) ? prev : [...prev, tag]);
        addTag(tag);
      }
    } catch (error) {
      console.error('Failed to create tag:', error);
    } finally {
      setLoading(false);
    }
  };

  const onKeyDown = (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      if (suggestions[0]) addTag(suggestions[0]);
      else if (canCreate) createAndAdd();
    } else if (e.key === 'Backspace' && !query && value.length > 0) {
      removeTag(value[value.length - 1].id);
    }
  };

  return (
    <div ref={wrapRef} style={{ position: 'relative' }}>
      <div
        style={{
          display: 'flex', flexWrap: 'wrap', gap: '6px',
          padding: '6px 8px',
          background: '#2b2b36',
          border: '1px solid var(--border-color, #3f3f52)',
          borderRadius: '6px',
          minHeight: '34px',
          cursor: disabled ? 'not-allowed' : 'text',
          opacity: disabled ? 0.6 : 1,
        }}
        onClick={() => !disabled && setOpen(true)}
      >
        {(value || []).map(t => (
          <span key={t.id} style={pillStyle(t.category, true)}>
            {t.name}
            {!disabled && (
              <span onClick={e => { e.stopPropagation(); removeTag(t.id); }} style={{ marginLeft: 2, cursor: 'pointer' }}>×</span>
            )}
          </span>
        ))}
        {!disabled && (
          <input
            value={query}
            onChange={e => { setQuery(e.target.value); setOpen(true); }}
            onKeyDown={onKeyDown}
            onFocus={() => setOpen(true)}
            placeholder={value.length === 0 ? 'Add tags…' : ''}
            style={{
              flex: 1, minWidth: '80px',
              background: 'transparent', border: 'none', outline: 'none',
              color: '#e0e0e6', fontSize: '12px',
            }}
          />
        )}
      </div>

      {open && !disabled && (suggestions.length > 0 || canCreate) && (
        <div style={{
          position: 'absolute', top: '100%', left: 0, right: 0, zIndex: 50,
          marginTop: '4px',
          background: '#242430',
          border: '1px solid var(--border-color, #3f3f52)',
          borderRadius: '6px',
          boxShadow: '0 4px 12px rgba(0,0,0,0.4)',
          maxHeight: '200px', overflowY: 'auto',
        }}>
          {suggestions.map(t => (
            <div
              key={t.id}
              onMouseDown={e => e.preventDefault()}
              onClick={() => addTag(t)}
              style={{ padding: '6px 10px', cursor: 'pointer', fontSize: '12px', display: 'flex', alignItems: 'center', gap: '8px' }}
              onMouseEnter={e => e.currentTarget.style.background = 'var(--bg-hover, #2b2b36)'}
              onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
            >
              <span style={{ width: 8, height: 8, borderRadius: '50%', background: CAT_COLOR[t.category] || 'var(--text-muted)' }} />
              <span style={{ color: '#e0e0e6' }}>{t.name}</span>
              <span style={{ marginLeft: 'auto', color: 'var(--text-muted)', fontSize: '10px' }}>{t.category}</span>
            </div>
          ))}
          {canCreate && (
            <div
              onMouseDown={e => e.preventDefault()}
              onClick={createAndAdd}
              style={{ padding: '6px 10px', cursor: 'pointer', fontSize: '12px', color: 'var(--accent-blue)', borderTop: suggestions.length ? '1px solid var(--border-color, #3f3f52)' : 'none' }}
            >
              {loading ? 'Creating…' : `+ Create "${q}" (${category})`}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
