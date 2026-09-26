import React, { useCallback, useEffect, useRef, useState } from 'react';
import { API_BASE } from '../../../api/base';

const ALLOWED_MIMES = ['image/png', 'image/jpeg', 'image/webp'];
const MAX_BYTES = 10 * 1024 * 1024;

export default function AttachmentUploader({ tradeId }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState(null);
  const [dragOver, setDragOver] = useState(false);
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef(null);
  const wrapRef = useRef(null);
  // dragenter/leave fire for every child — a simple boolean gets stuck.
  const dragDepth = useRef(0);

  const refresh = useCallback(() => {
    if (!tradeId) return;
    setLoading(true);
    fetch(`${API_BASE}/trades/${tradeId}/attachments`)
      .then(r => r.ok ? r.json() : [])
      .then(d => { setItems(Array.isArray(d) ? d : []); setLoading(false); })
      .catch(() => { setItems([]); setLoading(false); });
  }, [tradeId]);

  useEffect(() => { refresh(); }, [refresh]);

  const uploadOne = useCallback(async (file) => {
    if (!file) return;
    if (!ALLOWED_MIMES.includes(file.type)) {
      setErr(`Only PNG/JPEG/WebP allowed (got ${file.type || 'unknown'})`);
      return;
    }
    if (file.size > MAX_BYTES) {
      setErr('File too large (10 MB max)');
      return;
    }
    setErr(null);
    setUploading(true);
    try {
      const fd = new FormData();
      fd.append('file', file, file.name || 'pasted.png');
      const res = await fetch(`${API_BASE}/trades/${tradeId}/attachments`, {
        method: 'POST',
        body: fd,
      });
      if (!res.ok) {
        const body = await res.text();
        throw new Error(body || `HTTP ${res.status}`);
      }
      await res.json();
      refresh();
    } catch (e) {
      setErr(`Upload failed: ${e.message || e}`);
    } finally {
      setUploading(false);
    }
  }, [tradeId, refresh]);

  const handleFiles = useCallback(async (fileList) => {
    const files = Array.from(fileList || []).filter(f => f && ALLOWED_MIMES.includes(f.type));
    for (const f of files) {
       
      await uploadOne(f);
    }
  }, [uploadOne]);

  const onDrop = (e) => {
    e.preventDefault();
    dragDepth.current = 0;
    setDragOver(false);
    handleFiles(e.dataTransfer?.files);
  };

  const onDragEnter = (e) => {
    e.preventDefault();
    dragDepth.current += 1;
    setDragOver(true);
  };

  const onDragLeave = (e) => {
    e.preventDefault();
    dragDepth.current = Math.max(0, dragDepth.current - 1);
    if (dragDepth.current === 0) setDragOver(false);
  };

  const onPaste = useCallback((e) => {
    const items = e.clipboardData?.items;
    if (!items) return;
    const files = [];
    for (const item of items) {
      if (item.kind === 'file') {
        const f = item.getAsFile();
        if (f && ALLOWED_MIMES.includes(f.type)) files.push(f);
      }
    }
    if (files.length) {
      e.preventDefault();
      handleFiles(files);
    }
  }, [handleFiles]);

  useEffect(() => {
    const node = wrapRef.current;
    if (!node) return;
    node.addEventListener('paste', onPaste);
    return () => node.removeEventListener('paste', onPaste);
  }, [onPaste]);

  const removeAttachment = async (id) => {
    try {
      const res = await fetch(`${API_BASE}/attachments/${id}`, { method: 'DELETE' });
      if (res.ok) refresh();
    } catch { /* no-op */ }
  };

  return (
    <div
      ref={wrapRef}
      tabIndex={0}
      style={{ outline: 'none' }}
    >
      <div
        onDragEnter={onDragEnter}
        onDragOver={(e) => { e.preventDefault(); }}
        onDragLeave={onDragLeave}
        onDrop={onDrop}
        onClick={() => fileInputRef.current?.click()}
        style={{
          border: `2px dashed ${dragOver ? 'var(--accent-active)' : 'var(--border-color)'}`,
          borderRadius: 'var(--radius-md, 8px)',
          padding: '20px',
          textAlign: 'center',
          cursor: 'pointer',
          background: dragOver ? 'var(--myth-wash)' : 'transparent',
          transition: 'all 0.2s',
          color: 'var(--text-muted)',
          fontSize: 12,
        }}
      >
        <div style={{ fontSize: 20, marginBottom: 4 }}>⇪</div>
        <div><strong style={{ color: 'var(--text-main, #e0e0e6)' }}>Drop a chart</strong>, click to browse, or paste from clipboard</div>
        <div style={{ marginTop: 4, fontSize: 10 }}>PNG / JPEG / WebP · up to 10 MB</div>
        <input
          ref={fileInputRef}
          type="file"
          accept={ALLOWED_MIMES.join(',')}
          multiple
          style={{ display: 'none' }}
          onChange={(e) => handleFiles(e.target.files)}
        />
      </div>

      {err && (
        <div style={{ color: 'var(--danger)', fontSize: 11, marginTop: 6 }}>{err}</div>
      )}
      {uploading && (
        <div style={{ color: 'var(--text-muted)', fontSize: 11, marginTop: 6 }}>Uploading…</div>
      )}

      <div style={{ marginTop: 12, display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(140px, 1fr))', gap: 10 }}>
        {loading ? (
          <div style={{ color: 'var(--text-muted)', fontSize: 12 }}>Loading…</div>
        ) : items.length === 0 ? (
          <div style={{ color: 'var(--text-muted)', fontSize: 12, gridColumn: '1 / -1' }}>No attachments yet.</div>
        ) : items.map((a) => (
          <div
            key={a.id}
            style={{
              position: 'relative',
              border: '1px solid var(--border-color)',
              borderRadius: 'var(--radius-md, 8px)',
              overflow: 'hidden',
              background: 'var(--bg-main)',
            }}
          >
            <a href={a.url} target="_blank" rel="noreferrer" style={{ display: 'block' }}>
              <img
                src={a.url}
                alt={a.filename}
                style={{ width: '100%', height: 100, objectFit: 'cover', display: 'block' }}
              />
            </a>
            <div style={{ padding: '4px 6px', fontSize: 10, color: 'var(--text-muted)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 4 }}>
              <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{a.filename}</span>
              <button
                type="button"
                onClick={() => removeAttachment(a.id)}
                style={{
                  background: 'transparent', border: 'none', color: 'var(--danger)',
                  cursor: 'pointer', padding: '0 2px', fontSize: 12, lineHeight: 1,
                }}
                title="Delete"
              >×</button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
