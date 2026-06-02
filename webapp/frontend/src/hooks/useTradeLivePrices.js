import { useCallback, useEffect, useMemo, useState } from 'react';
import { API_BASE } from '../api';
import useIBKRStatus from './useIBKRStatus';
import useSSE from './useSSE';

export default function useTradeLivePrices(trades) {
  const [yfPrices, setYfPrices] = useState({});
  const ibkrStatus = useIBKRStatus(10000);
  const ibkrConnected = Boolean(ibkrStatus?.connected);
  const { data: portfolioSnap } = useSSE(
    ibkrStatus?.available ? `${API_BASE}/stream/portfolio` : null,
    { enabled: Boolean(ibkrStatus?.available) },
  );

  const ibkrPriceMap = useMemo(() => {
    const map = {};
    for (const position of portfolioSnap?.positions || []) {
      if (!position?.symbol) continue;
      const price = position.market_price;
      if (price != null && Number.isFinite(Number(price))) {
        map[position.symbol.toUpperCase()] = Number(price);
      }
    }
    return map;
  }, [portfolioSnap]);

  const openTickers = useMemo(() => {
    const symbols = new Set();
    for (const trade of trades) {
      if (!trade.closing_date && trade.pnl == null && trade.ticker) {
        symbols.add(String(trade.ticker).toUpperCase());
      }
    }
    return [...symbols];
  }, [trades]);

  const openTickersKey = useMemo(() => openTickers.join(','), [openTickers]);

  useEffect(() => {
    if (openTickers.length === 0) return undefined;
    const missing = openTickers.filter(ticker => ibkrPriceMap[ticker] == null);
    if (missing.length === 0) return undefined;

    let cancelled = false;
    const fetchPrices = () => {
      fetch(`${API_BASE}/live-prices/?tickers=${missing.join(',')}`)
        .then(response => (response.ok ? response.json() : {}))
        .then(data => {
          if (!cancelled) setYfPrices(previous => ({ ...previous, ...data }));
        })
        .catch(() => {});
    };

    fetchPrices();
    const intervalId = setInterval(fetchPrices, ibkrConnected ? 60000 : 20000);
    return () => {
      cancelled = true;
      clearInterval(intervalId);
    };
    // Deliberately omit the openTickers array — its identity changes on every parent
    // render even when the ticker set is unchanged, which would reset the interval.
    // openTickersKey (a joined string) is the stable proxy for "tickers changed".
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [openTickersKey, ibkrConnected, ibkrPriceMap]);

  return useCallback((ticker) => {
    const symbol = String(ticker || '').toUpperCase();
    if (ibkrPriceMap[symbol] != null) return { price: ibkrPriceMap[symbol], source: 'ibkr' };
    if (yfPrices[symbol] != null) return { price: yfPrices[symbol], source: 'yf' };
    return { price: null, source: null };
  }, [ibkrPriceMap, yfPrices]);
}
