import React, { useState, useMemo } from 'react';
import { fx, fmtNum } from '../utils/format';

const PositionCalculator = () => {
  const [riskAmount, setRiskAmount] = useState(50);
  const [entryPrice, setEntryPrice] = useState(48.18);
  const [stopPrice, setStopPrice] = useState(47.57);
  const [direction, setDirection] = useState('LONG');

  // Derive results directly — no useEffect + setState loop needed
  const results = useMemo(() => {
    if (entryPrice > 0 && stopPrice > 0 && riskAmount > 0) {
      // Stop sits below entry for a long, above entry for a short.
      const stopDistance = direction === 'SHORT'
        ? stopPrice - entryPrice
        : entryPrice - stopPrice;
      if (stopDistance > 0) {
        const shares = riskAmount / stopDistance;
        return {
          shares,
          stopSize: stopDistance,
          positionSize: shares * entryPrice,
        };
      }
    }
    return { shares: 0, stopSize: 0, positionSize: 0 };
  }, [riskAmount, entryPrice, stopPrice, direction]);
  const sharesText = fixed(results.shares);
  const stopSizeText = fixed(results.stopSize);
  const positionSizeText = money(results.positionSize);

  return (
    <div className="glass-panel">
      <h2 style={{borderBottom: '1px solid var(--border-color)', paddingBottom: '1rem', marginBottom: '1.5rem'}}>
        Position Sizing
      </h2>

      <div className="grid-cols-2">
        <div className="form-group">
          <label>Direction</label>
          <select value={direction} onChange={(e) => setDirection(e.target.value)}>
            <option value="LONG">Long</option>
            <option value="SHORT">Short</option>
          </select>
        </div>
        <div className="form-group">
          <label>Risk Amount ($)</label>
          <input 
            type="number" 
            value={riskAmount} 
            onChange={(e) => setRiskAmount(Number(e.target.value))} 
          />
        </div>
      </div>

      <div className="grid-cols-2">
        <div className="form-group">
          <label>Entry Price ($)</label>
          <input 
            type="number" 
            value={entryPrice} 
            onChange={(e) => setEntryPrice(Number(e.target.value))}
            step="0.01" 
          />
        </div>
        <div className="form-group">
          <label>Stop Loss Price ($)</label>
          <input 
            type="number" 
            value={stopPrice} 
            onChange={(e) => setStopPrice(Number(e.target.value))}
            step="0.01" 
          />
        </div>
      </div>

      <div style={{marginTop: "1.5rem", padding: "1.5rem", background: "var(--bg-main)", borderRadius: "var(--radius-md)", border: "1px solid var(--border-color)"}}>
        <div style={{display: "flex", justifyContent: "space-between", marginBottom: "0.75rem"}}>
          <span className="text-muted" style={{fontWeight: '600'}}>SHARES TO BUY</span>
          <span style={{fontWeight: "700", fontSize: "1.2rem", color: "var(--accent-blue)"}}>
            {sharesText}
          </span>
        </div>
        <div style={{display: "flex", justifyContent: "space-between", marginBottom: "0.75rem"}}>
          <span className="text-muted" style={{fontWeight: '600'}}>STOP SIZE</span>
          <span style={{fontWeight: '600', color: "var(--text-main)"}}>${stopSizeText}</span>
        </div>
        <div style={{display: "flex", justifyContent: "space-between"}}>
          <span className="text-muted" style={{fontWeight: '600'}}>TOTAL CAPITAL REQUIRED</span>
          <span style={{fontWeight: "700"}}>${positionSizeText}</span>
        </div>
      </div>
    </div>
  );
};

const fixed = (value, digits = 2) => fx(value, digits, '0.00');

const money = (value) => fmtNum(value, 2, '0.00');

export default PositionCalculator;
