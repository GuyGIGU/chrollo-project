import { useCallback, useEffect, useMemo, useState } from 'react';
import { API_BASE } from '../../../api/base';
import { buildPortfolioPlanMap, positionPlanKey } from '../model/portfolioPlanUtils';
import { inferDirection } from '../model/tradeUtils';
import { deriveTradeRow } from '../model/tradeTableUtils';

// Save / payload-diff engine for the trade-detail drawer. Owns the editable
// draft (entry/stop/qty/side/conviction/targets), the plan draft (thesis), and
// the last-saved trade; exposes a `savePlan()` that PUTs only the changed fields
// (`buildTradePayload`) plus the thesis. Extracted verbatim from
// TradeDetailDrawer.jsx — the diff/merge/broker-match logic is byte-identical,
// only relocated behind a hook so the drawer becomes presentational.

export const emptyPlan = () => ({
  thesis: '',
  entry_plan: '',
  exit_plan: '',
  risk_plan: '',
});

export const buildDraft = (trade) => ({
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

export const normalizePlan = (plan) => ({
  ...emptyPlan(),
  ...plan,
  thesis: plan?.thesis || '',
  entry_plan: plan?.entry_plan || '',
  exit_plan: plan?.exit_plan || '',
  risk_plan: plan?.risk_plan || '',
});

export const mergeDraftIntoTrade = (trade, draft) => {
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

export const buildTradePayload = (draft, savedTrade) => {
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

export const findBrokerMatch = (positions, trade, riskFor) => {
  if (!trade?.id || !positions?.length) return null;
  const planMap = buildPortfolioPlanMap(positions, [trade], riskFor);
  for (const position of positions) {
    const plan = planMap.get(positionPlanKey(position));
    if (plan?.trade?.id === trade.id || plan?.matches?.some(match => match.id === trade.id)) {
      return { plan, position };
    }
  }
  return null;
};

export const clampConviction = (value) => {
  const numberValue = finiteNumber(value);
  if (numberValue == null) return null;
  return Math.max(1, Math.min(10, Math.round(numberValue)));
};

export const toInput = (value) => (
  value == null || !Number.isFinite(Number(value)) ? '' : String(value)
);

export const finiteNumber = (value) => {
  if (value == null || value === '') return null;
  const numberValue = Number(value);
  return Number.isFinite(numberValue) ? numberValue : null;
};

export const sameNumber = (first, second) => (
  first != null && second != null && Math.abs(Number(first) - Number(second)) < 0.000001
);

export const sameNullableNumber = (first, second) => (
  (first == null && second == null) || sameNumber(first, second)
);

export const formatInputPrice = (value) => {
  if (value == null || !Number.isFinite(Number(value))) return '';
  return Number(value).toFixed(2);
};

// Stateful editor hook: mirrors the drawer's original useState/useEffect/useMemo
// wiring exactly (draft rebuilds on `trade` change, plan fetch on `trade.id`,
// working-trade merge, save round-trip). The drawer consumes this instead of
// owning the state itself.
export default function useTradePlanEditor(trade, { onTradeUpdate } = {}) {
  const [savedTrade, setSavedTrade] = useState(trade);
  const [draft, setDraft] = useState(() => buildDraft(trade));
  const [planDraft, setPlanDraft] = useState(emptyPlan);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');

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
  // Sizing preview off the (possibly edited) draft — price-independent, so editing
  // entry/stop/qty updates risk-$ live without a round-trip.
  const draftDerived = useMemo(
    () => (workingTrade ? deriveTradeRow(workingTrade) : null),
    [workingTrade],
  );

  const savePlan = useCallback(async () => {
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
  }, [workingTrade, saving, draft, savedTrade, planDraft, onTradeUpdate]);

  return {
    savedTrade,
    draft,
    setDraft,
    planDraft,
    setPlanDraft,
    saving,
    message,
    setMessage,
    workingTrade,
    draftDerived,
    savePlan,
  };
}
