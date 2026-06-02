export default function FillsRow({
  addFill,
  fills,
  onSave,
  removeFill,
  toggleFillSide,
  trade,
  updateFill,
  updateStopLoss,
}) {
  return (
    <tr className="fills-row">
      <td colSpan={15}>
        <div className="fills-panel">
          <FillHeader onSave={onSave} trade={trade} updateStopLoss={updateStopLoss} />
          <div className="fills-head">
            <div />
            <div>Action</div>
            <div>Date</div>
            <div>Qty</div>
            <div>Price</div>
            <div>Fee</div>
            <div />
          </div>
          {fills.map(fill => (
            <div key={fill.id} className="fill-row">
              <span style={{ fontSize: 9, color: 'var(--text-faint)', textAlign: 'center' }}>
                {fill.isInitial ? '*' : ''}
              </span>
              <button
                className={`fill-side-btn ${fill.type === 'BUY' ? 'buy' : 'sell'}`}
                onClick={() => toggleFillSide(trade.id, fill.id)}
              >
                {fill.type}
              </button>
              <FillInput type="date" value={fill.date || ''} onChange={value => updateFill(trade.id, fill.id, 'date', value)} />
              <FillInput type="number" placeholder="0" value={fill.quantity ?? ''} onChange={value => updateFill(trade.id, fill.id, 'quantity', value)} />
              <FillInput type="number" step="0.01" placeholder="0.00" value={fill.price ?? ''} onChange={value => updateFill(trade.id, fill.id, 'price', value)} />
              <FillInput type="number" step="0.01" placeholder="0" value={fill.fee ?? ''} onChange={value => updateFill(trade.id, fill.id, 'fee', value)} />
              <button
                className="fill-del"
                disabled={fill.isInitial}
                onClick={() => removeFill(trade.id, fill.id)}
                style={{ opacity: fill.isInitial ? 0.3 : 1 }}
                title={fill.isInitial ? 'Initial fill - edit via cells above' : 'Remove fill'}
              >
                x
              </button>
            </div>
          ))}
          <button className="fill-add" onClick={() => addFill(trade.id)}>+ Add fill</button>
        </div>
      </td>
    </tr>
  );
}

function FillHeader({ onSave, trade, updateStopLoss }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8, gap: 16 }}>
      <span style={{ fontSize: 10, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--text-muted)' }}>
        Fills - {trade.ticker}
      </span>
      <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 10, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--text-muted)', marginLeft: 'auto', marginRight: 8 }}>
        Stop loss
        <input
          type="number"
          step="0.01"
          className="fill-input"
          defaultValue={trade.stop_loss && Number(trade.stop_loss) !== 0 ? trade.stop_loss : ''}
          placeholder="0.00"
          style={{ width: 90, textTransform: 'none' }}
          onBlur={(event) => {
            const value = parseFloat(event.target.value);
            const next = Number.isFinite(value) ? value : 0;
            if (Number(trade.stop_loss || 0) !== next) updateStopLoss(trade, 'stop_loss', next);
          }}
        />
      </label>
      <button
        onClick={onSave}
        style={{
          background: 'var(--accent-blue)',
          border: 'none',
          borderRadius: 4,
          color: '#fff',
          cursor: 'pointer',
          fontSize: 10,
          fontWeight: 600,
          letterSpacing: '0.05em',
          padding: '4px 14px',
          textTransform: 'uppercase',
        }}
      >
        Save fills
      </button>
    </div>
  );
}

function FillInput({ onChange, ...props }) {
  return (
    <input
      className="fill-input"
      onChange={(event) => onChange(event.target.value)}
      {...props}
    />
  );
}
