import { useCallback, useEffect, useMemo, useRef } from 'react';
import useTradePlanEditor, {
  finiteNumber,
  findBrokerMatch,
  formatInputPrice,
} from '../hooks/useTradePlanEditor';
import { fmtMoney as fmtPortfolioMoney, summaryValue } from './portfolioFormat';
import {
  fmtInt,
  fmtMoney,
  buildTradeAlerts,
} from '../utils/tradeTableUtils';
import {
  formatPct,
  formatR,
  moneyValue,
  signedMoney,
  signedTone,
  sourceLabel,
  targetDistance,
  targetSub,
  targetValue,
  toneColor,
} from '../utils/tradeDetailFormat';
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

export default function TradeDetailDrawer({ trade, onClose, onTradeUpdate, riskFor, snapshot }) {
  const overlayRef = useRef(null);
  const {
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
  } = useTradePlanEditor(trade, { onTradeUpdate });

  // Live overlay (price / P&L / to-stop / targets) for the SAVED position from the
  // backend single source of truth; falls back to the draft when no server row.
  const derived = useMemo(
    () => (trade && riskFor ? riskFor(trade) : draftDerived),
    [trade, riskFor, draftDerived],
  );
  const alerts = useMemo(
    () => buildTradeAlerts(workingTrade, derived),
    [derived, workingTrade],
  );
  // Broker link + portfolio-risk-% read the SHARED portfolio snapshot threaded
  // from AppShell (single SSE owner) — the drawer no longer opens its own stream.
  const positions = snapshot?.positions || EMPTY_POSITIONS;
  const netLiquidation = finiteNumber(summaryValue(snapshot?.account_summary, 'NetLiquidation'));
  const brokerMatch = useMemo(
    () => findBrokerMatch(positions, workingTrade, riskFor),
    [positions, workingTrade, riskFor],
  );
  const riskDollars = draftDerived?.riskDistance != null && draftDerived?.riskQty
    ? draftDerived.riskDistance * draftDerived.riskQty * draftDerived.multiplier
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
