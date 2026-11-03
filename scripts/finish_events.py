"""Segment the Chicago mosaic with a yellow-core prompt, then one Wonder jam call."""

import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["STORMGATE_REFINE"] = "1"
os.environ["STORMGATE_OFFLINE"] = "0"

from backend.agents.sam_radar_tracker import segment_pngs
from backend.agents.wonder_mpc_supervisor import supervise
from backend.physics.design_storm import INIT_FRACTION, VMAX_MG
from backend.physics.nexrad_mosaic import OUT_DIR
from backend.physics.storm_catalog import select
from backend.physics.swmm_engine import forecast_window


async def main() -> None:
    paths = sorted((OUT_DIR / "chicago-2023-0702").glob("frame_*.png"))
    result = await segment_pngs("chicago-2023-0702", paths, concept="yellow storm cell")
    counts = [len(frame.get("objects") or []) for frame in result.get("frames") or []]
    print("chicago objects", counts, "errors", result.get("errors"), flush=True)
    select("ds-1482")
    decision = await supervise(
        VMAX_MG * INIT_FRACTION,
        forecast_window(8, 12),
        {1: 0.5},
        hosted=True,
        hosted_spark=True,
        step_index=8,
    )
    print("wonder", decision.get("source"), decision.get("selected"), flush=True)
    print("detail", (decision.get("detail") or "")[:400], flush=True)
    print("note", (decision.get("wonder_note") or "")[:240], flush=True)


if __name__ == "__main__":
    asyncio.run(main())
