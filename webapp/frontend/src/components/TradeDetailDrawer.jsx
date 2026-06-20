import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { API_BASE } from '../api';
import useIBKRStatus from '../hooks/useIBKRStatus';
import usePortfolioSnapshot from '../hooks/usePortfolioSnapshot';
import useTradeLivePrices from '../hooks/useTradeLivePrices';
import { buildPortfolioPlanMap, positionPlanKey } from '../utils/portfolioPlanUtils';
import { inferDirection } from '../utils/tradeUtils';
import {
  buildTradeAlerts,
  deriveTradeRow,
  fmtInt,
  fmtMoney,
} from '../utils/tradeTableUtils';
import { fmtMoney as fmtPortfolioMoney, summaryValue } from './portfolioFormat';
import AttachmentUploader from './AttachmentUploader';
import ExecutionsTab from './tradeDetail/ExecutionsTab';
import NotesTab from './tradeDetail/NotesTab';
import TradeSetupChart from './tradeDetail/TradeSetupChart';
import {
  alertStyle,
  alertToneStyle,
  bodyStyle,
  closeButtonStyle,
  cockpitGridStyle,
  convictionButtonStyle,
  convictionStyle,
  detailsBodyStyle,
  detailsStyle,
  drawerStyle,
  eyebrowStyle,
  headerStyle,
  inputGridStyle,
  inputStyle,
  labelStyle,
  metricLabelStyle,
  metricStyle,
  metricSubStyle,
  metricValueStyle,
  mutedStyle,
  overlayStyle,
  panelStyle,
  rButtonStyle,
  saveButtonStyle,
  saveGroupStyle,
  saveMessageStyle,
  secondaryGridStyle,
  sectionHeaderStyle,
  sectionTitleStyle,
  segmentedStyle,
  segmentButtonStyle,
  sideConvictionStyle,
  summaryStyle,
  targetEditRowStyle,
  targetEditorStyle,
  targetInputStyle,
  targetLabelStyle,
  targetQtyStyle,
  targetStateStyle,
  textareaStyle,
  titleMetaStyle,
  titleStyle,
} from './tradeDetail/tradePlanDrawerStyles';

const EMPTY_POSITIONS = [];

const emptyPlan = () => ({
  thesis: '',
  entry_plan: '',
  exit_plan: '',
  risk_plan: '',
});

export default function TradeDetailDrawer({ trade, onClose, onTradeUpdate }) {
  const [savedTrade, setSavedTrade] = useState(trade);
  const [draft, setDraft] = useState(() => buildDraft(trade));
  const [planDraft, setPlanDraft] = useState(emptyPlan);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');
  const overlayRef = useRef(null);
  const ibkrStatus = useIBKRStatus(10000);
  const { snapshot } = usePortfolioSnapshot(Boolean(ibkrStatus?.available));

  useEffect(() => {
    setSavedTrade(trade);
    setDraft(buildDraft(trade));
    setMessage('');
  }, [trade]);

  useEffect(() => {
    if (!trade?.id) return undefined;
    let cancelled = false;
    fetch(`${API_BASE}/trades/${trade.id}/plan`)
      .then(response => response.ok ? response.json() : emptyPlan())
      .then((data) => {
        if (!cancelled) setPlanDraft(normalizePlan(data));
      })
      .catch(() => {
        if (!cancelled) setPlanDraft(emptyPlan());
      });
    return () => { cancelled = true; };
  }, [trade?.id]);

  const workingTrade = useMemo(
    () => mergeDraftIntoTrade(savedTrade, draft),
    [draft, savedTrade],
  );
  const priceFor = useTradeLivePrices(workingTrade ? [workingTrade] : []);
  const derived = useMemo(
    () => (workingTrade ? deriveTradeRow(workingTrade, priceFor) : null),
    [priceFor, workingTrade],
  );
  const alerts = useMemo(
    () => buildTradeAlerts(workingTrade, derived),
    [derived, workingTrade],
  );
  const positions = snapshot?.positions || EMPTY_POSITIONS;
  const netLiquidation = finiteNumber(summaryValue(snapshot?.account_summary, 'NetLiquidation'));
  const brokerMatch = useMemo(
    () => findBrokerMatch(positions, workingTrade),
    [positions, workingTrade],
  );
  const riskDollars = derived?.riskDistance != null && derived?.riskQty
    ? derived.riskDistance * derived.riskQty * derived.multiplier
    : null;
  const riskPct = riskDollars != null && netLiquidation
    ? riskDollars / netLiquidation * 100
    : null;

  const handleKey = useCallback((event) => {
    if (event.key === 'Escape') onClose?.();
  }, [onClose]);

  useEffect(() => {
    document.addEventListener('keydown', handleKey);
    return () => document.removeEventListener('keydown', handleKey);
  }, [handleKey]);

  const updateField = (field) => (event) => {
    setDraft(current => ({ ...current, [field]: event.target.value }));
    setMessage('');
  };

  const updateTarget = (targetIndex, field, value) => {
    setDraft((current) => {
      const targets = current.targets.map((target, index) => (
        index === targetIndex ? { ...target, [field]: value } : target
      ));
      return { ...current, targets };
    });
    setMessage('');
  };

  const applyRTarget = (targetIndex) => {
    const entry = finiteNumber(draft.entry_price);
    const stop = finiteNumber(draft.stop_loss);
    if (entry == null || stop == null || entry === stop) return;
    const risk = Math.abs(entry - stop);
    const direction = draft.direction === 'SHORT' ? 'SHORT' : 'LONG';
    const r = targetIndex + 1;
    const price = direction === 'SHORT' ? entry - risk * r : entry + risk * r;
    updateTarget(targetIndex, 'price', formatInputPrice(price));
  };

  const savePlan = async () => {
    if (!workingTrade?.id || saving) return;
    setSaving(true);
    setMessage('');
    try {
      const tradePayload = buildTradePayload(draft, savedTrade);
      let updatedTrade = savedTrade;
      if (Object.keys(tradePayload).length > 0) {
        const tradeResponse = await fetch(`${API_BASE}/trades/${workingTrade.id}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(tradePayload),
        });
        updatedTrade = await tradeResponse.json().catch(() => null);
        if (!tradeResponse.ok || !updatedTrade) throw new Error('Trade save failed');
      }

      const planResponse = await fetch(`${API_BASE}/trades/${workingTrade.id}/plan`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ thesis: planDraft.thesis }),
      });
      if (!planResponse.ok) throw new Error('Plan save failed');

      setSavedTrade(updatedTrade);
      setDraft(buildDraft(updatedTrade));
      setMessage('Saved');
      onTradeUpdate?.(updatedTrade);
    } catch (error) {
      console.error('Trade plan save failed:', error);
      setMessage('Save failed');
    } finally {
      setSaving(false);
    }
  };

  if (!trade || !workingTrade || !derived) return null;

  const topAlert = alerts[0] || null;

  return (
    <div
      ref={overlayRef}
      onClick={(event) => { if (event.target === overlayRef.current) onClose?.(); }}
      style={overlayStyle}
    >
      <aside style={drawerStyle}>
        <header style={headerStyle}>
          <div style={{ minWidth: 0 }}>
            <div style={eyebrowStyle}>Trade #{workingTrade.id} / {workingTrade.opening_date || '-'}</div>
            <div style={titleStyle}>
              {workingTrade.ticker || '-'}
              <span style={titleMetaStyle}>{derived.direction} / {derived.status}</span>
            </div>
          </div>
          <button type="button" onClick={onClose} title="Close" style={closeButtonStyle}>x</button>
        </header>

        <div style={bodyStyle}>
          {topAlert && <AlertStrip alert={topAlert} />}

          <section style={cockpitGridStyle}>
            <Metric label="Live" value={moneyValue(derived.currentExit)} sub={sourceLabel(derived.currentExitSource)} />
            <Metric label="P&L" value={signedMoney(derived.pnl)} sub={formatR(derived.rValue, true)} tone={signedTone(derived.pnl)} />
            <Metric label="Risk" value={riskDollars == null ? '-' : fmtPortfolioMoney(riskDollars)} sub={riskPct == null ? 'Portfolio -' : `${formatPct(riskPct)} portfolio`} />
            <Metric label="To Stop" value={formatPct(derived.distToStopPct)} sub={formatR(derived.rToStop)} tone={derived.stopRiskTone} />
            <Metric label="Next Target" value={targetValue(derived.nextTarget)} sub={targetSub(derived.nextTarget, derived.targetLadder)} tone={derived.nextTarget ? 'target' : null} />
            <BrokerMetric match={brokerMatch} />
          </section>

          <section style={panelStyle}>
            <div style={sectionHeaderStyle}>
              <div>
                <div style={eyebrowStyle}>Plan</div>
                <strong style={sectionTitleStyle}>Thesis and Risk</strong>
              </div>
              <div style={saveGroupStyle}>
                {message && <span style={saveMessageStyle(message)}>{message}</span>}
                <button type="button" onClick={savePlan} disabled={saving} style={saveButtonStyle(saving)}>
                  {saving ? 'Saving' : 'Save'}
                </button>
              </div>
            </div>

            <label style={labelStyle} htmlFor="trade-thesis">Thesis</label>
            <textarea
              id="trade-thesis"
              value={planDraft.thesis}
              onChange={(event) => {
                setPlanDraft(current => ({ ...current, thesis: event.target.value }));
                setMessage('');
              }}
              rows={3}
              style={textareaStyle}
            />

            <div style={inputGridStyle}>
              <Field label="Entry" value={draft.entry_price} onChange={updateField('entry_price')} />
              <Field label="Stop" value={draft.stop_loss} onChange={updateField('stop_loss')} tone="danger" />
              <Field label="Qty" value={draft.quantity} onChange={updateField('quantity')} />
            </div>

            <div style={sideConvictionStyle}>
              <div>
                <label style={labelStyle}>Side</label>
                <div style={segmentedStyle}>
                  {['LONG', 'SHORT'].map(side => (
                    <button
                      key={side}
                      type="button"
                      onClick={() => setDraft(current => ({ ...current, direction: side }))}
                      style={segmentButtonStyle(draft.direction === side)}
                    >
                      {side}
                    </button>
                  ))}
                </div>
              </div>
              <div>
                <label style={labelStyle}>Conviction</label>
                <div style={convictionStyle}>
                  {Array.from({ length: 10 }, (_, index) => index + 1).map(value => (
                    <button
                      key={value}
                      type="button"
                      onClick={() => {
                        setDraft(current => ({ ...current, conviction: String(value) }));
                        setMessage('');
                      }}
                      style={convictionButtonStyle(Number(draft.conviction) === value)}
                    >
                      {value}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </section>

          <section style={panelStyle}>
            <div style={sectionHeaderStyle}>
              <div>
                <div style={eyebrowStyle}>Targets</div>
                <strong style={sectionTitleStyle}>Ladder</strong>
              </div>
              <span style={mutedStyle}>{derived.targetLadder.length ? `${derived.targetLadder.length}/5 set` : '0/5 set'}</span>
            </div>
            <div style={targetEditorStyle}>
              {draft.targets.map((target, index) => (
                <div key={target.label} style={targetEditRowStyle}>
                  <strong style={targetLabelStyle}>{target.label}</strong>
                  <input
                    aria-label={`${target.label} price`}
                    value={target.price}
                    onChange={(event) => updateTarget(index, 'price', event.target.value)}
                    inputMode="decimal"
                    style={targetInputStyle}
                  />
                  <input
                    aria-label={`${target.label} quantity`}
                    value={target.qty}
                    onChange={(event) => updateTarget(index, 'qty', event.target.value)}
                    inputMode="numeric"
                    style={targetQtyStyle}
                  />
                  <button type="button" onClick={() => applyRTarget(index)} style={rButtonStyle}>
                    +{index + 1}R
                  </button>
                  <TargetState target={derived.targetLadder.find(item => item.index === index + 1)} />
                </div>
              ))}
            </div>
          </section>

          <TradeSetupChart trade={workingTrade} derived={derived} />

          <section style={secondaryGridStyle}>
            <Details title="Fills">
              <ExecutionsTab tradeId={workingTrade.id} />
            </Details>
            <Details title="Notes">
              <NotesTab tradeId={workingTrade.id} />
            </Details>
            <Details title="Images">
              <AttachmentUploader tradeId={workingTrade.id} />
            </Details>
          </section>
        </div>
      </aside>
    </div>
  );
}

function Metric({ label, sub, tone, value }) {
  return (
    <div style={metricStyle}>
      <span style={metricLabelStyle}>{label}</span>
      <strong style={{ ...metricValueStyle, color: toneColor(tone) }}>{value}</strong>
      <small style={metricSubStyle}>{sub || '-'}</small>
    </div>
  );
}

function BrokerMetric({ match }) {
  if (!match?.plan) return <Metric label="Broker" value="No holding" sub="-" tone="muted" />;
  const { plan, position } = match;
  const qty = finiteNumber(position?.quantity ?? position?.position);
  const price = finiteNumber(position?.market_price);
  if (plan.state === 'multiple') {
    return <Metric label="Broker" value="Multiple plans" sub={qty == null ? '-' : `${fmtInt(qty)} shares`} tone="warning" />;
  }
  if (plan.directionMismatch) {
    return <Metric label="Broker" value="Mismatch" sub={qty == null ? '-' : `${fmtInt(qty)} shares`} tone="danger" />;
  }
  return (
    <Metric
      label="Broker"
      value="Linked"
      sub={`${qty == null ? '-' : fmtInt(qty)} @ ${price == null ? '-' : fmtMoney(price)}`}
      tone="success"
    />
  );
}

function Field({ label, onChange, tone, value }) {
  return (
    <div>
      <label style={labelStyle}>{label}</label>
      <input
        value={value}
        onChange={onChange}
        inputMode="decimal"
        style={{ ...inputStyle, borderColor: tone === 'danger' ? 'rgba(242, 103, 112, 0.38)' : 'var(--border-color)' }}
      />
    </div>
  );
}

function AlertStrip({ alert }) {
  return (
    <div style={{ ...alertStyle, ...alertToneStyle(alert.level) }}>
      <strong>{alert.title}</strong>
      <span>{alert.detail}</span>
    </div>
  );
}

function TargetState({ target }) {
  if (!target) return <span style={targetStateStyle}>-</span>;
  if (target.hit) return <span style={{ ...targetStateStyle, color: 'var(--success)' }}>Hit</span>;
  if (target.isNext) return <span style={{ ...targetStateStyle, color: 'var(--accent-blue)' }}>{targetDistance(target)}</span>;
  return <span style={targetStateStyle}>Pending</span>;
}

function Details({ children, title }) {
  return (
    <details style={detailsStyle}>
      <summary style={summaryStyle}>{title}</summary>
      <div style={detailsBodyStyle}>{children}</div>
    </details>
  );
}

const buildDraft = (trade) => ({
  direction: inferDirection(trade),
  entry_price: toInput(trade?.entry_price),
  stop_loss: toInput(trade?.stop_loss),
  quantity: toInput(trade?.quantity),
  conviction: toInput(trade?.conviction),
  targets: [1, 2, 3, 4, 5].map(index => ({
    label: `T${index}`,
    price: toInput(trade?.[`t${index}_price`]),
    qty: toInput(trade?.[`t${index}_qty`]),
  })),
});

const normalizePlan = (plan) => ({
  ...emptyPlan(),
  ...plan,
  thesis: plan?.thesis || '',
  entry_plan: plan?.entry_plan || '',
  exit_plan: plan?.exit_plan || '',
  risk_plan: plan?.risk_plan || '',
});

const mergeDraftIntoTrade = (trade, draft) => {
  if (!trade || !draft) return trade;
  const next = {
    ...trade,
    direction: draft.direction,
    conviction: finiteNumber(draft.conviction),
  };
  const entry = finiteNumber(draft.entry_price);
  const stop = finiteNumber(draft.stop_loss);
  const quantity = finiteNumber(draft.quantity);
  next.entry_price = entry;
  next.stop_loss = stop;
  next.quantity = quantity;
  draft.targets.forEach((target, index) => {
    const targetNumber = index + 1;
    next[`t${targetNumber}_price`] = finiteNumber(target.price);
    next[`t${targetNumber}_qty`] = finiteNumber(target.qty);
  });
  return next;
};

const buildTradePayload = (draft, savedTrade) => {
  const payload = {};
  const direction = draft.direction;
  if (direction && direction !== inferDirection(savedTrade)) {
    payload.direction = direction;
  }

  const conviction = clampConviction(draft.conviction);
  if (conviction !== finiteNumber(savedTrade?.conviction)) {
    payload.conviction = conviction;
  }

  const entry = finiteNumber(draft.entry_price);
  const stop = finiteNumber(draft.stop_loss);
  const quantity = finiteNumber(draft.quantity);
  const savedEntry = finiteNumber(savedTrade?.entry_price);
  const savedStop = finiteNumber(savedTrade?.stop_loss);
  const savedQuantity = finiteNumber(savedTrade?.quantity);

  if (entry != null && !sameNumber(entry, savedEntry)) payload.entry_price = entry;
  if (stop != null && !sameNumber(stop, savedStop)) payload.stop_loss = stop;
  if (stop == null && savedStop != null) payload.stop_loss = 0;
  if (quantity != null && !sameNumber(Math.round(quantity), savedQuantity)) payload.quantity = Math.round(quantity);
  if ((payload.entry_price != null || payload.quantity != null) && entry != null && quantity != null) {
    payload.position_size = entry * quantity;
  }

  draft.targets.forEach((target, index) => {
    const targetNumber = index + 1;
    const savedPrice = finiteNumber(savedTrade?.[`t${targetNumber}_price`]);
    const price = finiteNumber(target.price);
    if (!sameNullableNumber(price, savedPrice)) payload[`t${targetNumber}_price`] = price;

    const qty = finiteNumber(target.qty);
    const savedQty = finiteNumber(savedTrade?.[`t${targetNumber}_qty`]);
    const roundedQty = qty == null ? null : Math.round(qty);
    if (!sameNullableNumber(roundedQty, savedQty)) payload[`t${targetNumber}_qty`] = roundedQty;
  });
  return payload;
};

const findBrokerMatch = (positions, trade) => {
  if (!trade?.id || !positions?.length) return null;
  const planMap = buildPortfolioPlanMap(positions, [trade]);
  for (const position of positions) {
    const plan = planMap.get(positionPlanKey(position));
    if (plan?.trade?.id === trade.id || plan?.matches?.some(match => match.id === trade.id)) {
      return { plan, position };
    }
  }
  return null;
};

const clampConviction = (value) => {
  const numberValue = finiteNumber(value);
  if (numberValue == null) return null;
  return Math.max(1, Math.min(10, Math.round(numberValue)));
};

const toInput = (value) => (
  value == null || !Number.isFinite(Number(value)) ? '' : String(value)
);

const finiteNumber = (value) => {
  if (value == null || value === '') return null;
  const numberValue = Number(value);
  return Number.isFinite(numberValue) ? numberValue : null;
};

const sameNumber = (first, second) => (
  first != null && second != null && Math.abs(Number(first) - Number(second)) < 0.000001
);

const sameNullableNumber = (first, second) => (
  (first == null && second == null) || sameNumber(first, second)
);

const formatInputPrice = (value) => {
  if (value == null || !Number.isFinite(Number(value))) return '';
  return Number(value).toFixed(2);
};

const moneyValue = (value) => (value == null ? '-' : `$${fmtMoney(value)}`);

const signedMoney = (value) => {
  if (value == null || !Number.isFinite(Number(value))) return '-';
  return `${Number(value) >= 0 ? '+' : '-'}$${fmtMoney(Math.abs(Number(value)))}`;
};

const formatPct = (value) => {
  if (value == null || !Number.isFinite(Number(value))) return '-';
  return `${Number(value).toFixed(1)}%`;
};

const formatR = (value, signed = false) => {
  if (value == null || !Number.isFinite(Number(value))) return '-';
  return `${signed && Number(value) >= 0 ? '+' : ''}${Number(value).toFixed(2)}R`;
};

const targetValue = (target) => (
  target ? `${target.label} $${fmtMoney(target.price)}` : '-'
);

const targetSub = (target, ladder) => {
  if (target) return `${targetDistance(target)} away`;
  return ladder?.length ? 'Complete' : 'No target';
};

const targetDistance = (target) => {
  if (!target || target.distToTargetPct == null || !Number.isFinite(Number(target.distToTargetPct))) return '-';
  return `${formatPct(target.distToTargetPct)} / ${formatR(target.rToTarget)}`;
};

const sourceLabel = (source) => {
  if (source === 'ibkr') return 'IBKR';
  if (source === 'yf') return 'Live quote';
  if (source === 'fills') return 'Fills';
  return 'No quote';
};

const signedTone = (value) => {
  if (value == null || !Number.isFinite(Number(value))) return null;
  if (Number(value) > 0) return 'success';
  if (Number(value) < 0) return 'danger';
  return 'muted';
};

const toneColor = (tone) => {
  if (tone === 'success') return 'var(--success)';
  if (tone === 'danger' || tone === 'breached') return 'var(--danger)';
  if (tone === 'warning') return 'var(--warning)';
  if (tone === 'target') return 'var(--accent-blue)';
  if (tone === 'muted') return 'var(--text-muted)';
  return 'var(--text-main)';
};
