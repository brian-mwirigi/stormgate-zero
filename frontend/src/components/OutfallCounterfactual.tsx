type Props = { onClose: () => void };

export default function OutfallCounterfactual({ onClose }: Props) {
  return (
    <div className="sg-modal" onClick={onClose} role="presentation">
      <figure onClick={(event) => event.stopPropagation()}>
        <figcaption>
          <span>MUSE IMAGE 1.0 · ANCHORED OUTFALL</span>
          <button className="sg-btn" type="button" onClick={onClose}>
            Close
          </button>
        </figcaption>
        <img src={`/api/outfall/latest?ts=${Date.now()}`} alt="Side by side outfall, baseline spill versus StormGate containment" />
      </figure>
    </div>
  );
}
