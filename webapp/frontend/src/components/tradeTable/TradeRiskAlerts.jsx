import { useEffect, useMemo, useState } from 'react';
import { pruneDismissed, selectActiveAlerts, SNOOZE_MS } from '../../utils/alertMuting';

export default function TradeRiskAlerts({ alerts = [], onDetailClick, trades = [] }) {
  // { alertId: dismissedAtMs } — a STAMP, not a set membership: alert ids recur,
  // so a permanent id-keyed dismissal muted the next genuine breach too.
  const [dismissed, setDismissed] = useState(() => ({}));
  const [snoozedUntil, setSnoozedUntil] = useState({});
  const tradesById = useMemo(() => {
    const map = new Map();
    for (const trade of trades) map.set(trade.id, trade);
    return map;
  }, [trades]);

  // Bind each dismissal to the firing episode: once its alert stops firing (or
  // the backstop expires) the dismissal is dropped, so a re-breach shows again.
  // pruneDismissed returns the same object when nothing changed, so this cannot loop.
  useEffect(() => {
    setDismissed(previous => pruneDismissed(previous, alerts, Date.now()));
  }, [alerts]);

  const now = Date.now();
  const activeAlerts = selectActiveAlerts(alerts, dismissed, snoozedUntil, now);

  if (activeAlerts.length === 0) return null;

  const visibleAlerts = activeAlerts.slice(0, 4);
  const hiddenCount = activeAlerts.length - visibleAlerts.length;

  const dismiss = (alert) => {
    setDismissed(previous => ({ ...previous, [alert.id]: Date.now() }));
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
