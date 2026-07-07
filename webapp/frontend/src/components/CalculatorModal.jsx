import PositionCalculator from './PositionCalculator';
import Modal from './ui/Modal';

function CalculatorModal({ onClose }) {
  return (
    <Modal
      onClose={onClose}
      overlayClassName="modal-overlay"
      overlayStyle={null}
      contentClassName="modal-content"
      contentStyle={{ maxWidth: '600px' }}
    >
      <div className="modal-header">
        <h2 style={{ fontSize: '1.2rem', margin: 0 }}>Position Size Utility</h2>
        <button className="modal-close" onClick={onClose}>x</button>
      </div>
      <PositionCalculator />
    </Modal>
  );
}

export default CalculatorModal;
