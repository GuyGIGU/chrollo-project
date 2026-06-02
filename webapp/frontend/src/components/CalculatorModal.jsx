import PositionCalculator from './PositionCalculator';

function CalculatorModal({ onClose }) {
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" style={{ maxWidth: '600px' }} onClick={event => event.stopPropagation()}>
        <div className="modal-header">
          <h2 style={{ fontSize: '1.2rem', margin: 0 }}>Position Size Utility</h2>
          <button className="modal-close" onClick={onClose}>x</button>
        </div>
        <PositionCalculator />
      </div>
    </div>
  );
}

export default CalculatorModal;
