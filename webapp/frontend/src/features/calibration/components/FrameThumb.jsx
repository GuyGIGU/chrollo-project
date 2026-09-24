import useFrameThumb from '../hooks/useFrameThumb';
import { thumbGeometry } from '../model/frameThumb';

// A fixed 74x34 static-SVG mini of a mark's FROZEN frame with the operator's
// box drawn — scan every mark without loading each one. Never a per-row
// lightweight-charts canvas (the fidelity trap): the backend pre-downsamples
// (frame_store.preview_series), this only draws. The box overlay comes from the
// mark's own rails/span, in the operator hue; the price line stays muted so the
// ground truth is what reads. No digest / no data -> a quiet recessed cell.
function FrameThumb({ ticker, asOf, digest, isBox, r, s, boxStart, boxEnd }) {
  const preview = useFrameThumb(ticker, asOf, digest);
  const box = isBox ? { r, s, boxStart, boxEnd } : null;
  const geom = preview ? thumbGeometry(preview, box) : null;

  const title = digest
    ? `Frozen frame${geom?.box ? ' with your box' : ''}`
    : 'No frozen frame for this mark';

  return (
    <span className="inst-thumb" title={title}>
      {geom && (
        <svg viewBox="0 0 74 34" preserveAspectRatio="none" aria-hidden="true">
          <polyline className="thumb-price" points={geom.points} fill="none" />
          {geom.box && (
            <>
              <rect
                className="thumb-box"
                x={geom.box.x}
                y={geom.box.ry}
                width={geom.box.width}
                height={Math.max(geom.box.sy - geom.box.ry, 0.5)}
              />
              <line className="thumb-rail" x1={geom.box.x} y1={geom.box.ry} x2={geom.box.right} y2={geom.box.ry} />
              <line className="thumb-rail" x1={geom.box.x} y1={geom.box.sy} x2={geom.box.right} y2={geom.box.sy} />
            </>
          )}
        </svg>
      )}
    </span>
  );
}

export default FrameThumb;
