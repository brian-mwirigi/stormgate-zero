type Props = { onClose: () => void };

export default function OutfallCounterfactual({ onClose }: Props) {
  return (
    <div className="modal" onClick={onClose} role="presentation">
      <figure onClick={(event) => event.stopPropagation()}>
        <figcaption>
          <span>The same outfall, both ways · Muse Image 1.0 on the solver's gallon counts</span>
          <button className="btn" type="button" onClick={onClose}>
            Close
          </button>
        </figcaption>
        <img src={`/api/outfall/latest?ts=${Date.now()}`} alt="Side by side outfall, float switch spill versus StormGate containment" />
      </figure>
    </div>
  );
}
