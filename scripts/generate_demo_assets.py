"""Build the NEXRAD loop, the outfall reference plate, and the SWMM network."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.agents.image_counterfactual import save_reference  # noqa: E402
from backend.agents.sam_radar_tracker import extract_dbz_boxes_frame0  # noqa: E402
from backend.config import DATA_DIR, SWMM_DIR  # noqa: E402
from backend.physics.radar_synthesizer import write_radar_assets  # noqa: E402
from backend.physics.swmm_engine import run_episode, write_interceptor_inp  # noqa: E402


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    radar = write_radar_assets()
    reference = save_reference()
    inp = write_interceptor_inp(SWMM_DIR / "interceptor.inp")
    baseline = run_episode("local")
    stormgate = run_episode("stormgate")
    boxes = extract_dbz_boxes_frame0(radar.get("mp4"))
    summary = {
        "radar": {key: radar[key] for key in ("mp4", "mp4_error", "contact_sheet")},
        "frame_count": len(radar["frames"]),
        "reference": str(reference),
        "inp": str(inp),
        "frame0_boxes": boxes,
        "local_cso_gallons": round(baseline["cso_gallons"], 1),
        "stormgate_cso_gallons": round(stormgate["cso_gallons"], 1),
    }
    out = DATA_DIR / "asset_manifest.json"
    out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
