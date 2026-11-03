import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["STORMGATE_REFINE"] = "1"
os.environ["STORMGATE_OFFLINE"] = "0"

from backend.episode import Episode
from backend.physics.storm_catalog import select


async def main() -> None:
    select("ds-1482")
    episode = Episode()
    limit = int(os.environ.get("REFINE_STEPS", "18"))
    for _ in range(limit):
        await episode.step_once()
        step = episode.sim.step_index - 1
        print(
            f"step {step} selected={episode.decision.get('selected')} "
            f"refine={(episode.decision.get('refine_note') or '')[:120]}",
            flush=True,
        )


if __name__ == "__main__":
    asyncio.run(main())
