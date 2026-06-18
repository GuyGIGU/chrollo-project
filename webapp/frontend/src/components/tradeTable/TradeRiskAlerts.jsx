import { useMemo, useState } from 'react';

const SNOOZE_MS = 30 * 60 * 1000;

export default function TradeRiskAlerts({ alerts = [], onDetailClick, trades = [] }) {
  const [dismissed, setDismissed] = useState(() => new Set());
  const [snoozedUntil, setSnoozedUntil] = useState({});
  const tradesById = useMemo(() => {
    const map = new Map();
    for (const trade of trades) map.set(trade.id, trade);
    return map;
  }, [trades]);
  const now = Date.now();
  const activeAlerts = alerts.filter(alert => (
    !dismissed.has(alert.id) && (!snoozedUntil[alert.id] || snoozedUntil[alert.id] <= now)
  ));

  if (activeAlerts.length === 0) return null;

  const visibleAlerts = activeAlerts.slice(0, 4);
  const hiddenCount = activeAlerts.length - visibleAlerts.length;

  const dismiss = (alert) => {
    setDismissed(previous => new Set([...previous, alert.id]));
  };

  const snooze = (alert) => {
    setSnoozedUntil(previous => ({
      ...previous,
      [alert.id]: Date.now() + SNOOZE_MS,
    }));
  };

  const openTrade = (alert) => {
    const trade = tradesById.get(alert.tradeId);
    if (trade) onDetailClick?.(trade);
  };

  return (
    <section className="trade-alert-strip" role="alert" aria-label="Open trade alerts">
      <div className="trade-alert-head">
        <span className="trade-alert-kicker">Live Alerts</span>
        <strong>{activeAlerts.length}</strong>
      </div>
      <div className="trade-alert-list">
        {visibleAlerts.map(alert => (
          <div key={alert.id} className={`trade-alert-item ${alert.level}`}>
            <button
              type="button"
              className="trade-alert-main"
              onClick={() => openTrade(alert)}
              title="Open trade details"
            >
              <span className="trade-alert-title">{alert.title}</span>
              <span className="trade-alert-detail">{alert.detail}</span>
            </button>
            <button type="button" className="trade-alert-action" onClick={() => snooze(alert)}>
              Snooze
            </button>
            <button type="button" className="trade-alert-action" onClick={() => dismiss(alert)}>
              Dismiss
            </button>
          </div>
        ))}
        {hiddenCount > 0 && <span className="trade-alert-more">+{hiddenCount} more</span>}
      </div>
    </section>
  );
}
