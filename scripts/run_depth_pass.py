"""Build the real mosaic tapes, segment them with SAM, then run Spark turn 2.

Turn 1 on DS-1482 is already cached. This script only spends a call when the
second-turn vector, or a mosaic frame, is not already in traces/live_models.json.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["STORMGATE_REFINE"] = "1"
os.environ["STORMGATE_OFFLINE"] = "0"

from backend.agents.sam_radar_tracker import segment_pngs
from backend.episode import Episode
from backend.physics.design_storm import VMAX_MG, INIT_FRACTION
from backend.physics.nexrad_mosaic import EVENTS, OUT_DIR, build_event
from backend.physics.storm_catalog import select
from backend.physics.swmm_engine import forecast_window
from backend.agents.wonder_mpc_supervisor import supervise


async def _sam() -> None:
    for storm_id in EVENTS:
        folder = OUT_DIR / storm_id
        paths = sorted(folder.glob("frame_*.png"))
        print(f"sam {storm_id} frames={len(paths)}", flush=True)
        result = await segment_pngs(storm_id, paths)
        counts = [len(frame.get("objects") or []) for frame in result.get("frames") or []]
        print(f"  ok={result.get('ok')} objects={counts} errors={result.get('errors')}", flush=True)


async def _refine() -> None:
    select("ds-1482")
    episode = Episode()
    print("refine DS-1482", flush=True)
    for _ in range(18):
        await episode.step_once()
        step = episode.sim.step_index - 1
        print(
            f"  step {step} selected={episode.decision.get('selected')} "
            f"cso={episode.sim.stormgate.cso_mg:.4f} refine={bool(episode.decision.get('refine_note'))}",
            flush=True,
        )
    volume = VMAX_MG * INIT_FRACTION
    forecast = forecast_window(8, 12)
    jammed = {1: 0.5}
    decision = await supervise(
        volume,
        forecast,
        jammed,
        hosted=True,
        hosted_spark=True,
        step_index=8,
    )
    print(
        f"wonder jam selected={decision.get('selected')} source={decision.get('source')} "
        f"note={(decision.get('wonder_note') or '')[:160]}",
        flush=True,
    )


async def main() -> None:
    for storm_id in EVENTS:
        meta = build_event(storm_id)
        print(f"built {storm_id} frames={len(meta['frames'])}", flush=True)
    await _sam()
    await _refine()


if __name__ == "__main__":
    asyncio.run(main())
