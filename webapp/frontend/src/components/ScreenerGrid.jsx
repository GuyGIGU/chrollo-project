import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import ScreenerCard from './ScreenerCard';
import ScreenerModal from './ScreenerModal';
import { TagLegend, TAG_CATALOG, deriveTags } from './SetupTags';
import { deriveScoreBreakdown } from './setupScoreMath';
import { API_BASE } from '../api';

const ScreenerGrid = () => {
  const [screenerData, setScreenerData] = useState(null);
  const [isScanning, setIsScanning] = useState(false);
  const [scanLogs, setScanLogs] = useState([]);

  const [searchTerm, setSearchTerm] = useState('');
  const [tierFilter, setTierFilter] = useState('ALL');
  const [setupFilter, setSetupFilter] = useState('ALL');     // setup-type dropdown
  const [tagFilter, setTagFilter] = useState(() => new Set()); // active "why-ranked" tag ids
  const [sortBy, setSortBy] = useState('score');             // score | visual | market | base | trigger | rs
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 24;

  // Earnings cache: ticker -> {date, days_until}. Backend caches 24h, but we
  // also keep results per-session to avoid re-requesting on every page flip.
  const [earningsByTicker, setEarningsByTicker] = useState({});

  // User-curated watchlist (persisted to backend). Stored as a Set for O(1) lookups.
  const [watchlist, setWatchlist] = useState(() => new Set());

  const [activeModalTicker, setActiveModalTicker] = useState(null);

  const fetchScreener = async () => {
    try {
      const res = await fetch(`${API_BASE}/screener-data/`);
      if (res.ok) {
        const data = await res.json();
        setScreenerData(data);
      } else {
        // Surface backend failures (e.g. a 500 serving screener_data.json)
        // instead of silently sitting on the "Loading…" placeholder forever.
        const body = await res.text().catch(() => '');
        console.error(`screener-data ${res.status}: ${body.slice(0, 200)}`);
      }
    } catch (err) {
      console.error("Failed to load screener data", err);
    }
  };

  useEffect(() => {
    fetchScreener();
  }, []);

  useEffect(() => {
    fetch(`${API_BASE}/watchlist/`)
      .then(r => r.ok ? r.json() : [])
      .then(items => setWatchlist(new Set(items.map(it => it.ticker))))
      .catch(() => {});
  }, []);

  const toggleWatchlist = useCallback((ticker) => {
    setWatchlist(prev => {
      const next = new Set(prev);
      const isOn = next.has(ticker);
      if (isOn) next.delete(ticker); else next.add(ticker);
      // Optimistic; revert on failure
      const url = `${API_BASE}/watchlist/${encodeURIComponent(ticker)}`;
      fetch(url, { method: isOn ? 'DELETE' : 'POST' })
        .then(r => {
          if (!r.ok) throw new Error('watchlist write failed');
        })
        .catch(err => {
          console.error('Watchlist toggle failed, reverting', err);
          setWatchlist(curr => {
            const rolled = new Set(curr);
            if (isOn) rolled.add(ticker); else rolled.delete(ticker);
            return rolled;
          });
        });
      return next;
    });
  }, []);

  // Which "why-ranked" tags fire for each ticker — computed once per data load
  // (the same derivation the card chips use) so tag-filtering is O(1) per card.
  const tagIdsByTicker = useMemo(() => {
    const map = {};
    if (!screenerData || !screenerData.chart_data) return map;
    for (const [ticker, d] of Object.entries(screenerData.chart_data)) {
      const tags = deriveTags(d.sub_scores, {
        phaseDInner: d.phase_d_inner,
        rTouchVolZ: d.r_touch_vol_z,
        sTouchVolZ: d.s_touch_vol_z,
      });
      map[ticker] = new Set(tags.map(t => t.id));
    }
    return map;
  }, [screenerData]);

  // Distinct setup types present in the current scan (for the setup dropdown).
  const availableSetups = useMemo(() => {
    if (!screenerData || !screenerData.chart_data) return [];
    const seen = new Set();
    for (const d of Object.values(screenerData.chart_data)) {
      if (d.setup) seen.add(d.setup);
    }
    return Array.from(seen).sort();
  }, [screenerData]);

  // Tags actually present in this scan — only show filter chips that can match.
  const availableTagIds = useMemo(() => {
    const seen = new Set();
    for (const ids of Object.values(tagIdsByTicker)) {
      ids.forEach(id => seen.add(id));
    }
    return seen;
  }, [tagIdsByTicker]);

  const distToTrigger = (d) =>
    (d && d.trigger && d.price) ? (d.trigger - d.price) / d.price : Infinity;

  const filteredTickers = useMemo(() => {
    if (!screenerData || !screenerData.ordered_tickers) return [];
    const matched = screenerData.ordered_tickers.filter(ticker => {
      const d = screenerData.chart_data[ticker];
      if (!d) return false;
      const matchesSearch = ticker.toLowerCase().includes(searchTerm.toLowerCase());
      const matchesTier =
        tierFilter === 'ALL' ? true
        : tierFilter === 'WATCHLIST' ? watchlist.has(ticker)
        : d.tier === tierFilter;
      const matchesSetup = setupFilter === 'ALL' ? true : d.setup === setupFilter;
      // Tag filter is AND across selected tags (a card must carry all of them).
      const tIds = tagIdsByTicker[ticker] || new Set();
      const matchesTags = tagFilter.size === 0
        || Array.from(tagFilter).every(id => tIds.has(id));
      return matchesSearch && matchesTier && matchesSetup && matchesTags;
    });

    // ordered_tickers arrives score-desc; only re-sort when a non-default key
    // is chosen so the default path stays a no-op.
    if (sortBy === 'score') return matched;
    const cd = screenerData.chart_data;
    const sorted = [...matched];
    if (sortBy === 'visual') {
      const visual = (t) => deriveScoreBreakdown(cd[t].sub_scores).visual.score || 0;
      sorted.sort((a, b) => visual(b) - visual(a));
    } else if (sortBy === 'market') {
      const market = (t) => deriveScoreBreakdown(cd[t].sub_scores).market.score || 0;
      sorted.sort((a, b) => market(b) - market(a));
    } else if (sortBy === 'base') {
      sorted.sort((a, b) => (cd[b].base_len || 0) - (cd[a].base_len || 0));
    } else if (sortBy === 'trigger') {
      sorted.sort((a, b) => distToTrigger(cd[a]) - distToTrigger(cd[b])); // nearest first
    } else if (sortBy === 'rs') {
      const rs = (t) => (cd[t].sub_scores && cd[t].sub_scores.rs_bonus) || 0;
      sorted.sort((a, b) => rs(b) - rs(a));
    }
    return sorted;
  }, [screenerData, searchTerm, tierFilter, setupFilter, tagFilter, sortBy, watchlist, tagIdsByTicker]);

  const toggleTagFilter = useCallback((id) => {
    setTagFilter(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
    setCurrentPage(1);
  }, []);

  const totalPages = Math.max(1, Math.ceil(filteredTickers.length / itemsPerPage));
  const paginatedTickers = filteredTickers.slice((currentPage - 1) * itemsPerPage, currentPage * itemsPerPage);

  useEffect(() => {
    if (currentPage > totalPages) {
      setCurrentPage(1);
    }
  }, [totalPages, currentPage]);

  // Lazy-fetch earnings for the visible page. Skip tickers we already have
  // (cache lives on `earningsByTicker`); backend also caches 24h.
  useEffect(() => {
    const missing = paginatedTickers.filter(t => !(t in earningsByTicker));
    if (missing.length === 0) return;
    let cancelled = false;
    fetch(`${API_BASE}/screener-data/earnings`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tickers: missing }),
    })
      .then(r => r.ok ? r.json() : {})
      .then(data => {
        if (cancelled) return;
        setEarningsByTicker(prev => ({ ...prev, ...data }));
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [paginatedTickers, earningsByTicker]);

  const handleNextModal = useCallback(() => {
    if (!activeModalTicker || filteredTickers.length === 0) return;
    const currentIndex = filteredTickers.indexOf(activeModalTicker);
    const nextIndex = (currentIndex + 1) % filteredTickers.length;
    setActiveModalTicker(filteredTickers[nextIndex]);
  }, [activeModalTicker, filteredTickers]);

  const handlePrevModal = useCallback(() => {
    if (!activeModalTicker || filteredTickers.length === 0) return;
    const currentIndex = filteredTickers.indexOf(activeModalTicker);
    const prevIndex = (currentIndex - 1 + filteredTickers.length) % filteredTickers.length;
    setActiveModalTicker(filteredTickers[prevIndex]);
  }, [activeModalTicker, filteredTickers]);

  const handleCardClick = useCallback((ticker) => setActiveModalTicker(ticker), []);

  useEffect(() => {
    const handleKeyDown = (e) => {
      if (activeModalTicker) {
        if (e.key === 'ArrowRight' || e.key === 'ArrowDown') { e.preventDefault(); handleNextModal(); }
        if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') { e.preventDefault(); handlePrevModal(); }
        if (e.key === 'Escape') { e.preventDefault(); setActiveModalTicker(null); }
      }
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [activeModalTicker, handleNextModal, handlePrevModal]);

  const [scanProgress, setScanProgress] = useState(0);
  const [scanPhase, setScanPhase] = useState('');
  // Hold the live scan EventSource so we can close it on unmount — otherwise
  // navigating away mid-scan leaks the stream and fires setState on a dead
  // component.
  const scanSourceRef = useRef(null);

  useEffect(() => () => {
    if (scanSourceRef.current) {
      scanSourceRef.current.close();
      scanSourceRef.current = null;
    }
  }, []);

  const parseScanProgress = (line) => {
    const trimmed = line.trim();
    // "Evaluating: |####---| 45.2% Complete"
    const evalMatch = trimmed.match(/(\d+\.?\d*)%\s*Complete/i);
    if (evalMatch) {
      // Evaluation phase is 40-95% of overall progress
      const evalPct = parseFloat(evalMatch[1]);
      setScanProgress(40 + evalPct * 0.55);
      setScanPhase('Evaluating tickers…');
      return;
    }
    // "  Download batch 2/12 (500 tickers)..." / "  Incremental batch 1/3..."
    // (data.py prints the label "Download"/"Incremental", not "Downloading")
    const batchMatch = trimmed.match(/(?:Download|Incremental) batch (\d+)\/(\d+)/i);
    if (batchMatch) {
      const cur = parseInt(batchMatch[1]);
      const tot = parseInt(batchMatch[2]);
      setScanProgress(10 + (cur / tot) * 28);
      setScanPhase(`Downloading market data (batch ${cur}/${tot})…`);
      return;
    }
    // "Validating X tickers with missing..."
    if (/Validating.*tickers/i.test(trimmed)) {
      setScanProgress(38);
      setScanPhase('Validating data integrity…');
      return;
    }
    // "Loaded XXXX tickers" or "Downloading master universe"
    if (/Loaded \d+ tickers/i.test(trimmed) || /Downloading master universe/i.test(trimmed)) {
      setScanProgress(5);
      setScanPhase('Loading ticker universe…');
      return;
    }
    // "Loading market data from local cache"
    if (/Loading market data from local cache/i.test(trimmed)) {
      setScanProgress(35);
      setScanPhase('Loading cached market data…');
      return;
    }
    // "Starting quantitative scans"
    if (/Starting quantitative scans/i.test(trimmed)) {
      setScanProgress(40);
      setScanPhase('Starting evaluation engine…');
      return;
    }
    // Dashboard generation / final phase
    if (/Generating|Dashboard|chart data/i.test(trimmed)) {
      setScanProgress(96);
      setScanPhase('Generating dashboard charts…');
      return;
    }
  };

  const handleRunScan = () => {
    // Guard against double-start: close any stream still open from a prior click.
    if (scanSourceRef.current) {
      scanSourceRef.current.close();
      scanSourceRef.current = null;
    }
    setIsScanning(true);
    setScanLogs([]);
    setScanProgress(0);
    setScanPhase('Initializing pipeline…');

    const eventSource = new EventSource(`${API_BASE}/run-scan-stream/`);
    scanSourceRef.current = eventSource;

    // Reveal results as soon as the dashboard JSON is written — which happens
    // BEFORE the (slow, network-bound) archive/market-context step. Otherwise a
    // slow SPY/VIX/sector fetch during archiving gatekeeps the grid behind the
    // final [DONE], making a finished scan look frozen. We still keep the stream
    // open until [DONE] so archiving completes cleanly in the background.
    let resultsRevealed = false;
    const revealResults = async () => {
      if (resultsRevealed) return;
      resultsRevealed = true;
      setIsScanning(false);
      setScanProgress(0);
      setScanPhase('');
      await fetchScreener();
    };

    eventSource.onmessage = async (e) => {
      if (e.data === '[DONE]') {
        eventSource.close();
        scanSourceRef.current = null;
        await revealResults();   // no-op if the export line already revealed
        return;
      }
      parseScanProgress(e.data);
      if (/Data exported to|UI update available/i.test(e.data)) {
        await revealResults();
        return;
      }
      if (!resultsRevealed) {
        setScanLogs(prev => {
          const newLogs = [...prev, e.data];
          return newLogs.slice(-4);
        });
      }
    };
    
    eventSource.onerror = (err) => {
      console.error("EventSource failed.", err);
      eventSource.close();
      scanSourceRef.current = null;
      setIsScanning(false);
      setScanProgress(0);
      setScanPhase('');
    };
  };

  const getTierBtnStyle = (tier) => {
    const isActive = tierFilter === tier;
    return {
      padding: '5px 14px', borderRadius: '16px', border: '1px solid',
      borderColor: isActive ? 'var(--accent-blue)' : 'var(--border-color)',
      background: isActive ? 'var(--accent-blue)' : 'transparent',
      color: isActive ? '#fff' : 'var(--text-main)',
      cursor: 'pointer', transition: 'all 0.2s ease',
      fontWeight: isActive ? '600' : '500', fontSize: '12px',
      fontFamily: 'inherit'
    };
  };

  const selectStyle = {
    padding: '5px 10px', borderRadius: '8px', border: '1px solid var(--border-color)',
    background: 'var(--bg-main)', color: 'var(--text-main)', fontSize: '12px',
    outline: 'none', cursor: 'pointer', fontFamily: 'inherit',
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ color: 'var(--text-muted)' }}>
          {filteredTickers.length} setups matched your constraints.
        </div>
        <button 
          onClick={handleRunScan} 
          disabled={isScanning}
          style={{
            background: isScanning ? 'var(--bg-hover)' : 'var(--accent-blue)',
            color: isScanning ? 'var(--text-muted)' : '#fff',
            border: 'none',
            padding: '8px 16px',
            borderRadius: '6px',
            cursor: isScanning ? 'not-allowed' : 'pointer',
            fontWeight: '600',
            transition: 'all 0.2s',
            fontFamily: 'inherit'
          }}
        >
          {isScanning ? '⏳ Running Scan...' : '▶ Run Market Scan Now'}
        </button>
      </div>

      {screenerData && !isScanning && (
        <div style={{
          padding: '10px 16px', background: 'var(--bg-panel)', border: '1px solid var(--border-color)', borderRadius: '8px',
          display: 'flex', flexDirection: 'column', gap: '12px'
        }}>
          {/* Row 1 — tier filter + search */}
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
            <span style={{fontSize: '12px', color: 'var(--text-muted)', fontWeight: '500', marginRight: '6px'}}>Filter:</span>
            {['ALL', 'S', 'A', 'B', 'C', 'WATCHLIST'].map(tier => (
              <button key={tier} onClick={() => {setTierFilter(tier); setCurrentPage(1);}} style={getTierBtnStyle(tier)}>
                {tier === 'ALL'
                  ? 'All Tiers'
                  : tier === 'WATCHLIST'
                    ? `★ Watchlist (${watchlist.size})`
                    : `${tier} Tier`}
              </button>
            ))}
            <input
              type="text"
              placeholder="Search ticker..."
              value={searchTerm}
              onChange={(e) => {setSearchTerm(e.target.value); setCurrentPage(1);}}
              style={{
                marginLeft: 'auto', padding: '5px 14px', borderRadius: '8px', border: '1px solid var(--border-color)',
                background: 'var(--bg-main)', color: 'var(--text-main)', fontSize: '12px', width: '180px', outline: 'none',
                fontFamily: 'inherit'
              }}
            />
          </div>

          {/* Row 2 — setup-type + sort dropdowns */}
          <div style={{ display: 'flex', gap: '16px', alignItems: 'center', flexWrap: 'wrap' }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', color: 'var(--text-muted)' }}>
              Setup:
              <select
                value={setupFilter}
                onChange={(e) => { setSetupFilter(e.target.value); setCurrentPage(1); }}
                style={selectStyle}
              >
                <option value="ALL">All setups</option>
                {availableSetups.map(s => <option key={s} value={s}>{s}</option>)}
              </select>
            </label>
            <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', color: 'var(--text-muted)' }}>
              Sort by:
              <select
                value={sortBy}
                onChange={(e) => { setSortBy(e.target.value); setCurrentPage(1); }}
                style={selectStyle}
              >
                <option value="score">Score (high → low)</option>
                <option value="visual">Visual score (high → low)</option>
                <option value="market">Market score (high → low)</option>
                <option value="base">Base age (old → new)</option>
                <option value="trigger">Nearest to trigger</option>
                <option value="rs">Relative strength</option>
              </select>
            </label>
            {(setupFilter !== 'ALL' || tagFilter.size > 0 || sortBy !== 'score') && (
              <button
                onClick={() => { setSetupFilter('ALL'); setTagFilter(new Set()); setSortBy('score'); setCurrentPage(1); }}
                style={{
                  fontSize: '11px', color: 'var(--text-muted)', background: 'transparent',
                  border: '1px solid var(--border-color)', borderRadius: '12px',
                  padding: '4px 12px', cursor: 'pointer', fontFamily: 'inherit',
                }}
              >Reset</button>
            )}
          </div>

          {/* Row 3 — tag filter chips (only tags present in this scan) */}
          {availableTagIds.size > 0 && (
            <div style={{ display: 'flex', gap: '6px', alignItems: 'center', flexWrap: 'wrap' }}>
              <span style={{ fontSize: '12px', color: 'var(--text-muted)', fontWeight: 500, marginRight: '2px' }}>Tags:</span>
              {TAG_CATALOG.filter(t => availableTagIds.has(t.id)).map(t => {
                const active = tagFilter.has(t.id);
                return (
                  <button
                    key={t.id}
                    onClick={() => toggleTagFilter(t.id)}
                    title={active ? 'Click to remove this tag filter' : 'Show only setups carrying this tag'}
                    style={{
                      fontSize: '10px', fontWeight: 700, fontFamily: "'JetBrains Mono', monospace",
                      padding: '3px 9px', borderRadius: '12px', cursor: 'pointer',
                      border: `1px solid ${active ? 'var(--accent-blue)' : 'var(--border-color)'}`,
                      background: active ? 'var(--accent-blue)' : 'transparent',
                      color: active ? '#fff' : 'var(--text-main)',
                    }}
                  >{t.label}</button>
                );
              })}
            </div>
          )}

          {/* Row 4 — color legend */}
          <TagLegend style={{ borderTop: '1px solid var(--border-color)', paddingTop: '10px' }} />
        </div>
      )}

      {tierFilter === 'WATCHLIST' && watchlist.size > 0 && !isScanning && (
        <div style={{
          padding: '10px 16px', background: 'var(--bg-panel)', border: '1px solid var(--border-color)', borderRadius: '8px',
          display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap'
        }}>
          <span style={{fontSize: '12px', color: 'var(--text-muted)', fontWeight: '500', marginRight: '6px'}}>
            Manage ({watchlist.size}):
          </span>
          {Array.from(watchlist).sort().map(ticker => {
            const hasSetup = !!(screenerData && screenerData.chart_data && screenerData.chart_data[ticker]);
            return (
              <span
                key={ticker}
                title={hasSetup ? '' : 'No matching setup in the latest scan'}
                style={{
                  display: 'inline-flex', alignItems: 'center', gap: '6px',
                  padding: '4px 4px 4px 10px', borderRadius: '14px',
                  border: '1px solid var(--border-color)',
                  background: hasSetup ? 'transparent' : 'rgba(255,255,255,0.04)',
                  color: hasSetup ? 'var(--text-main)' : 'var(--text-muted)',
                  fontSize: '12px',
                  fontStyle: hasSetup ? 'normal' : 'italic',
                }}
              >
                {ticker}
                {!hasSetup && <span style={{fontSize: '10px', opacity: 0.7}}>(no setup)</span>}
                <button
                  onClick={() => toggleWatchlist(ticker)}
                  title="Remove from watchlist"
                  style={{
                    border: 'none', background: 'transparent', color: 'var(--text-muted)',
                    cursor: 'pointer', fontSize: '14px', lineHeight: 1,
                    padding: '0 6px', borderRadius: '10px',
                  }}
                >×</button>
              </span>
            );
          })}
        </div>
      )}

      {isScanning && (
        <div style={{
          background: 'var(--bg-panel)',
          border: '1px solid var(--border-color)',
          borderRadius: '12px',
          padding: '24px',
          display: 'flex',
          flexDirection: 'column',
          gap: '16px',
        }}>
          {/* Phase label + percentage */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{
              fontSize: '13px',
              fontWeight: '600',
              color: scanProgress >= 100 ? '#3fb950' : 'var(--text-main)',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
            }}>
              {scanProgress < 100 && (
                <span style={{
                  display: 'inline-block',
                  width: '8px',
                  height: '8px',
                  borderRadius: '50%',
                  background: 'var(--accent-blue)',
                  animation: 'pulse-subtle 1.5s ease-in-out infinite',
                }} />
              )}
              {scanProgress >= 100 && '✓ '}
              {scanPhase || 'Initializing pipeline…'}
            </span>
            <span style={{
              fontSize: '13px',
              fontWeight: '700',
              fontFamily: "'JetBrains Mono', monospace",
              color: scanProgress >= 100 ? '#3fb950' : 'var(--accent-blue)',
            }}>
              {Math.min(100, Math.round(scanProgress))}%
            </span>
          </div>

          {/* Progress bar track */}
          <div style={{
            width: '100%',
            height: '8px',
            borderRadius: '4px',
            background: 'rgba(255,255,255,0.06)',
            overflow: 'hidden',
            position: 'relative',
          }}>
            <div style={{
              height: '100%',
              width: `${Math.min(100, scanProgress)}%`,
              borderRadius: '4px',
              background: scanProgress >= 100
                ? '#3fb950'
                : 'linear-gradient(90deg, var(--accent-blue), var(--accent-pink, #bb86fc))',
              transition: 'width 0.4s ease-out',
              position: 'relative',
              overflow: 'hidden',
            }}>
              {/* Shimmer animation overlay */}
              {scanProgress < 100 && (
                <div style={{
                  position: 'absolute',
                  top: 0,
                  left: 0,
                  right: 0,
                  bottom: 0,
                  background: 'linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.3) 50%, transparent 100%)',
                  animation: 'shimmer 1.8s ease-in-out infinite',
                }} />
              )}
            </div>
          </div>

          {/* Live log lines */}
          <div style={{
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: '10px',
            color: 'var(--text-muted)',
            maxHeight: '52px',
            overflow: 'hidden',
            display: 'flex',
            flexDirection: 'column',
            gap: '2px',
          }}>
            {scanLogs.map((log, i) => (
              <div key={i} style={{
                opacity: i === scanLogs.length - 1 ? 0.7 : 0.35,
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
              }}>
                {log}
              </div>
            ))}
          </div>
        </div>
      )}

      {(!screenerData || !screenerData.ordered_tickers) && !isScanning ? (
        <div style={{padding: '2rem', textAlign: 'center', color: 'var(--text-muted)'}}>
          Loading Screener Data... (If this takes more than a moment, run a new market scan!)
        </div>
      ) : (!isScanning && paginatedTickers.length === 0) ? (
        <div style={{padding: '2rem', textAlign: 'center', color: 'var(--text-muted)'}}>
          No setups found matching current filters.
        </div>
      ) : !isScanning && screenerData ? (
        <>
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(min(100%, 390px), 1fr))',
            gap: '22px',
          }}>
            {paginatedTickers.map((ticker) => (
              <ScreenerCard
                key={ticker}
                ticker={ticker}
                data={screenerData.chart_data[ticker]}
                earnings={earningsByTicker[ticker]}
                watchlisted={watchlist.has(ticker)}
                onToggleWatchlist={toggleWatchlist}
                onClick={handleCardClick}
              />
            ))}
          </div>

          {totalPages > 1 && (
            <div style={{display: 'flex', justifyContent: 'center', gap: '8px', marginTop: '20px', marginBottom: '20px'}}>
              <button 
                disabled={currentPage === 1} 
                onClick={() => setCurrentPage(p => p - 1)}
                style={{padding: '6px 14px', background: 'var(--bg-main)', border: '1px solid var(--border-color)', color: 'var(--text-main)', borderRadius: '6px', cursor: currentPage === 1 ? 'not-allowed' : 'pointer', opacity: currentPage === 1 ? 0.5 : 1, fontFamily: 'inherit'}}
              >◀ Prev</button>
              
              {Array.from({length: totalPages}, (_, i) => i + 1).map(page => (
                <button 
                  key={page} 
                  onClick={() => setCurrentPage(page)}
                  style={{
                    padding: '6px 14px', borderRadius: '6px', border: '1px solid',
                    borderColor: currentPage === page ? 'var(--accent-blue)' : 'var(--border-color)',
                    background: currentPage === page ? 'var(--accent-blue)' : 'var(--bg-main)',
                    color: currentPage === page ? '#fff' : 'var(--text-main)',
                    cursor: 'pointer', fontWeight: currentPage === page ? '600' : '400',
                    fontFamily: 'inherit'
                  }}
                >{page}</button>
              ))}

              <button 
                disabled={currentPage === totalPages} 
                onClick={() => setCurrentPage(p => p + 1)}
                style={{padding: '6px 14px', background: 'var(--bg-main)', border: '1px solid var(--border-color)', color: 'var(--text-main)', borderRadius: '6px', cursor: currentPage === totalPages ? 'not-allowed' : 'pointer', opacity: currentPage === totalPages ? 0.5 : 1, fontFamily: 'inherit'}}
              >Next ▶</button>
            </div>
          )}
        </>
      ) : null}

      {activeModalTicker && screenerData && screenerData.chart_data[activeModalTicker] && (
        <ScreenerModal 
          ticker={activeModalTicker}
          data={screenerData.chart_data[activeModalTicker]}
          onClose={() => setActiveModalTicker(null)}
          onNext={handleNextModal}
          onPrev={handlePrevModal}
        />
      )}
    </div>
  );
};

export default ScreenerGrid;
