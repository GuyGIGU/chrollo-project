import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import { createChart, BarSeries, LineSeries, HistogramSeries } from 'lightweight-charts';
import ScreenerModal from './ScreenerModal';
import { TagRow } from './SetupTags';
import { API_BASE } from '../api';

// Earnings within ~10 days = high blow-up risk on a breakout play. We surface
// a small chip in the card header so the trader sees it before clicking.
// NOT a ranking signal — purely an earnings-calendar warning.
const EarningsChip = ({ info }) => {
  if (!info || info.days_until == null) return null;
  const d = info.days_until;
  if (d < 0 || d > 14) return null;        // only render when imminent
  const tone = d <= 3
    ? { bg: 'rgba(199,107,115,0.18)', fg: '#ff8c8c' }
    : d <= 7
      ? { bg: 'rgba(231,179,65,0.18)', fg: '#e3b341' }
      : { bg: 'rgba(88,166,255,0.15)', fg: '#58a6ff' };
  return (
    <span
      title={`Earnings in ${d} day${d === 1 ? '' : 's'} (${info.date}) — high blow-up risk on a breakout play`}
      style={{
        padding: '1px 6px', borderRadius: '8px', fontSize: '9px', fontWeight: 700,
        background: tone.bg, color: tone.fg, fontFamily: "'JetBrains Mono', monospace",
      }}
    >
      📅 ER {d}d
    </span>
  );
};


const ScreenerCard = React.memo(({ ticker, data, earnings, onClick }) => {
  const chartContainerRef = useRef(null);
  const chartRef = useRef(null);
  const [chartError, setChartError] = useState(false);

  useEffect(() => {
    const container = chartContainerRef.current;
    if (!container) return;

    // Always clear container before creating a new chart
    container.innerHTML = '';

    let disposed = false;
    let chart = null;

    try {
      // Fallback to sane defaults if container hasn't been laid out yet
      const w = container.clientWidth || 340;
      const h = container.clientHeight || 220;

      chart = createChart(container, {
        width: w,
        height: h,
        layout: { background: { type: 'solid', color: '#1c1c24' }, textColor: '#7b7b8f', fontFamily: "'JetBrains Mono', monospace", fontSize: 11 },
        grid: { vertLines: { color: 'rgba(42, 42, 54, 0.3)' }, horzLines: { color: 'rgba(42, 42, 54, 0.3)' } },
        crosshair: { mode: 0 },
        rightPriceScale: { borderColor: '#2a2a36', scaleMargins: { top: 0.1, bottom: 0.25 } },
        timeScale: { borderColor: '#2a2a36', timeVisible: false, fixLeftEdge: true, fixRightEdge: true },
        handleScroll: false,
        handleScale: false,
      });

      chartRef.current = chart;

      const candleSeries = chart.addSeries(BarSeries, { upColor: '#d1d4dc', downColor: '#d1d4dc', thinBars: false });
      
      let plotCandles = JSON.parse(JSON.stringify(data.candles));
      if (data.base_len > 0) {
        const rawBaseStart = plotCandles.length - data.base_len;
        const rBar = rawBaseStart + data.r_anchor;
        const sBar = rawBaseStart + data.s_anchor;
        const limbStart = Math.min(rBar, sBar);
        const limbEnd = Math.max(rBar, sBar);
        for (let k = limbStart; k <= limbEnd; k++) {
          if (k >= 0 && k < plotCandles.length) plotCandles[k].color = '#555555';
        }
        
        if (data.lps_len > 0 && data.lps_offset !== undefined) {
          const lpsEnd = plotCandles.length - 1 - data.lps_offset;
          const lpsStart = Math.max(0, lpsEnd - data.lps_len + 1);
          for (let k = lpsStart; k <= lpsEnd; k++) {
            if (k >= 0 && k < plotCandles.length) plotCandles[k].color = '#e3b341'; // Yellow highlight
          }
        }
      }
      candleSeries.setData(plotCandles);

      const volumeSeries = chart.addSeries(HistogramSeries, { priceFormat: { type: 'volume' }, priceScaleId: 'volume' });
      volumeSeries.priceScale().applyOptions({ scaleMargins: { top: 0.8, bottom: 0 } });
      volumeSeries.setData(data.volumes);

      const rSeries = chart.addSeries(LineSeries, { color: '#4488ff', lineWidth: 2, crosshairMarkerVisible: false, lastValueVisible: false, priceLineVisible: false });
      const sSeries = chart.addSeries(LineSeries, { color: '#4488ff', lineWidth: 2, crosshairMarkerVisible: false, lastValueVisible: false, priceLineVisible: false });
      const midSeries = chart.addSeries(LineSeries, { color: 'rgba(139, 148, 158, 0.4)', lineWidth: 1, lineStyle: 2, crosshairMarkerVisible: false, lastValueVisible: false, priceLineVisible: false });

      const rData = []; const sData = []; const midData = [];
      const startIdx = Math.max(0, data.candles.length - data.base_len);
      const midValue = (data.R + data.S) / 2;
      for (let i = startIdx; i < data.candles.length; i++) {
          const t = data.candles[i].time;
          rData.push({ time: t, value: data.R }); 
          sData.push({ time: t, value: data.S });
          midData.push({ time: t, value: midValue });
      }
      rSeries.setData(rData); sSeries.setData(sData); midSeries.setData(midData);

      if (data.base_len > 0 && data.candles.length > 0) {
        const displayStart = Math.max(0, data.candles.length - data.base_len - 15);
        chart.timeScale().setVisibleRange({
          from: data.candles[displayStart].time,
          to: data.candles[data.candles.length - 1].time,
        });
      } else {
        chart.timeScale().fitContent();
      }
    } catch (err) {
      console.error(`[ScreenerCard] Chart init failed for ${ticker}:`, err);
      setChartError(true);
      return; // Skip resize listener setup
    }

    const handleResize = () => {
      if (!disposed && container && container.isConnected && chart) {
        try {
          chart.applyOptions({ width: container.clientWidth });
        } catch { /* container detached */ }
      }
    };

    window.addEventListener('resize', handleResize);
    const resizeTimeout = setTimeout(handleResize, 80);

    return () => {
      disposed = true;
      clearTimeout(resizeTimeout);
      window.removeEventListener('resize', handleResize);
      chartRef.current = null;
      if (chart) {
        try { chart.remove(); } catch { /* safe to ignore */ }
      }
      if (container) container.innerHTML = '';
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ticker]);

  const getTierColor = (tier) => {
    switch(tier) {
      case 'S': return '#ff8c00';
      case 'A': return '#bb86fc';
      case 'B': return '#58a6ff';
      case 'C': return '#3fb950';
      default: return '#8b949e';
    }
  };

  return (
    <div onClick={() => onClick(ticker)} style={{
      background: 'var(--bg-panel)',
      border: '1px solid var(--border-color)',
      borderRadius: '8px',
      overflow: 'hidden',
      display: 'flex',
      flexDirection: 'column',
      height: '320px',
      cursor: 'pointer',
      transition: 'border-color 0.2s',
    }}
    onMouseEnter={(e) => e.currentTarget.style.borderColor = 'var(--accent-blue)'}
    onMouseLeave={(e) => e.currentTarget.style.borderColor = 'var(--border-color)'}
    >
      <div style={{
        padding: '12px 14px',
        borderBottom: '1px solid var(--border-color)',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center'
      }}>
        <span style={{fontWeight: '700', fontSize: '16px', color: getTierColor(data.tier)}}>{ticker}</span>
        <div style={{fontSize: '11px', color: 'var(--text-main)', display: 'flex', gap: '8px', alignItems: 'center'}}>
          <EarningsChip info={earnings} />
          <span style={{padding: '2px 8px', borderRadius: '10px', background: 'rgba(255,255,255,0.05)'}}>{data.tier} TIER</span>
          <span>Score: {data.score}</span>
        </div>
      </div>
      {chartError ? (
        <div style={{flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)', fontSize: '11px'}}>
          Chart failed to load
        </div>
      ) : (
        <div ref={chartContainerRef} style={{flex: 1, position: 'relative', pointerEvents: 'none'}}></div>
      )}
      <div style={{
        display: 'flex', justifyContent: 'space-between', padding: '8px 14px',
        background: 'var(--bg-main)', borderTop: '1px solid var(--border-color)', fontSize: '11px', color: 'var(--text-muted)'
      }}>
        <span>{data.setup}</span>
        <span>Base: {data.base_len}d</span>
      </div>
      <TagRow
        subScores={data.sub_scores}
        flags={{ phaseDInner: data.phase_d_inner }}
        style={{
          padding: '6px 10px',
          background: 'var(--bg-main)',
          borderTop: '1px solid var(--border-color)',
        }}
      />
    </div>
  );
});

const ScreenerGrid = () => {
  const [screenerData, setScreenerData] = useState(null);
  const [isScanning, setIsScanning] = useState(false);
  const [scanLogs, setScanLogs] = useState([]);

  const [searchTerm, setSearchTerm] = useState('');
  const [tierFilter, setTierFilter] = useState('ALL');
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 24;

  // Earnings cache: ticker -> {date, days_until}. Backend caches 24h, but we
  // also keep results per-session to avoid re-requesting on every page flip.
  const [earningsByTicker, setEarningsByTicker] = useState({});

  const [activeModalTicker, setActiveModalTicker] = useState(null);

  const fetchScreener = async () => {
    try {
      const res = await fetch(`${API_BASE}/screener-data/`);
      if (res.ok) {
        const data = await res.json();
        setScreenerData(data);
      }
    } catch (err) {
      console.error("Failed to load screener data", err);
    }
  };

  useEffect(() => {
    fetchScreener();
  }, []);

  const filteredTickers = useMemo(() => {
    if (!screenerData || !screenerData.ordered_tickers) return [];
    return screenerData.ordered_tickers.filter(ticker => {
      const d = screenerData.chart_data[ticker];
      if (!d) return false;
      const matchesSearch = ticker.toLowerCase().includes(searchTerm.toLowerCase());
      const matchesTier = tierFilter === 'ALL' || d.tier === tierFilter;
      return matchesSearch && matchesTier;
    });
  }, [screenerData, searchTerm, tierFilter]);

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
    // "Downloading batch 2/12 (500 tickers)..."
    const batchMatch = trimmed.match(/Downloading batch (\d+)\/(\d+)/i);
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
    setIsScanning(true);
    setScanLogs([]);
    setScanProgress(0);
    setScanPhase('Initializing pipeline…');

    const eventSource = new EventSource(`${API_BASE}/run-scan-stream/`);
    
    eventSource.onmessage = async (e) => {
      if (e.data === '[DONE]') {
        setScanProgress(100);
        setScanPhase('Complete!');
        eventSource.close();
        // Brief pause so user sees 100%
        setTimeout(async () => {
          setIsScanning(false);
          setScanProgress(0);
          setScanPhase('');
          await fetchScreener();
        }, 600);
      } else {
        parseScanProgress(e.data);
        setScanLogs(prev => {
          const newLogs = [...prev, e.data];
          return newLogs.slice(-4);
        });
      }
    };
    
    eventSource.onerror = (err) => {
      console.error("EventSource failed.", err);
      eventSource.close();
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
          display: 'flex', gap: '8px', alignItems: 'center'
        }}>
          <span style={{fontSize: '12px', color: 'var(--text-muted)', fontWeight: '500', marginRight: '6px'}}>Filter:</span>
          {['ALL', 'S', 'A', 'B', 'C'].map(tier => (
            <button key={tier} onClick={() => {setTierFilter(tier); setCurrentPage(1);}} style={getTierBtnStyle(tier)}>
              {tier === 'ALL' ? 'All Tiers' : `${tier} Tier`}
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
            gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))',
            gap: '20px',
          }}>
            {paginatedTickers.map((ticker) => (
              <ScreenerCard
                key={ticker}
                ticker={ticker}
                data={screenerData.chart_data[ticker]}
                earnings={earningsByTicker[ticker]}
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
