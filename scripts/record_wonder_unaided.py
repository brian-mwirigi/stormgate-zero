"""One unaided Muse Wonder call at the step-4 double lock.

No grid is shown. Wonder sees only the four hand-written laws and their
remaining spill after OR1=0.05 and OR2=0.90 lock at step 4, and must
invent its own continuous post-jam vector [0.05, 0.90, or3, or4].
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from backend.agents.meta_client import create_response, parse_json_block, response_text
from backend.agents.spark_open_worker import _clip_u
from backend.config import settings
from backend.physics.frontier import HEADLINE_JAM_AT, HEADLINE_LOCKS, headline_rain, replay, score_schedule
from backend.physics.swmm_engine import Watershed

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "traces" / "wonder_unaided_recovery.json"
PRE_JAM_U = [0.45, 0.42, 0.40, 0.62]


def _play_post_jam(rain, post_u: list[float]) -> dict:
    plant = Watershed("unaided")
    orifice = []
    for step in range(len(rain)):
        jam = HEADLINE_LOCKS if step >= HEADLINE_JAM_AT else None
        opening = PRE_JAM_U if step < HEADLINE_JAM_AT else post_u
        plant.step(opening, rain[step], jammed=jam)
        orifice.append([round(float(v), 4) for v in plant.orifice_history[-1]])
    return {
        "cso_gallons": round(plant.cso_mg * 1_000_000, 1),
        "street_gallons": round(plant.street_mg * 1_000_000, 1),
        "orifice": orifice,
    }


async def main() -> None:
    if OUT.exists() and "--force" not in sys.argv:
        print("trace exists; pass --force to call again")
        return
    rain = headline_rain()
    base = score_schedule(rain, HEADLINE_LOCKS, HEADLINE_JAM_AT)
    plant = Watershed("pre")
    for step in range(HEADLINE_JAM_AT):
        plant.step(PRE_JAM_U, rain[step], jammed=None)
    depth_at_jam = [round(float(v), 3) for v in plant.depth]

    laws_summary = {
        name: {
            "cso_gallons": base[name]["cso_gallons"],
            "street_gallons": base[name]["street_gallons"],
        }
        for name in ("A-predrain", "B-balanced", "C-retention", "D-bypass")
    }
    prompt = (
        "You are Muse Wonder 1.0, supervisory MPC for a 4-basin combined sewer. "
        "At step 4 (minute 20 of 90), a compound mechanical fault locks OR1=0.05 (nearly shut) "
        "and OR2=0.90 (stuck wide open). Basin depths SU1-SU4 at step 4 are "
        f"{depth_at_jam}. "
        "All four hand-written control laws fail over the storm:\n"
        f"- A-predrain: {laws_summary['A-predrain']}\n"
        f"- B-balanced ([0.05, 0.90, 0.40, 0.62]): {laws_summary['B-balanced']} (OR3=0.40 dumps SU3 into SU4 while OR2 is stuck at 0.90)\n"
        f"- C-retention ([0.05, 0.90, 0.08, 0.28]): {laws_summary['C-retention']} (OR4=0.28 chokes the treatment plant)\n"
        f"- D-bypass ([0.05, 0.90, 1.00, 1.00]): {laws_summary['D-bypass']} (OR3=1.00 floods SU4)\n"
        "Synthesize your own post-jam orifice vector u = [0.05, 0.90, or3, or4] with continuous values in [0, 1] "
        "that holds back Basin 3 (low or3) while draining Basin 4 to the treatment plant (high or4) so both river CSO and street flooding drop to 0. "
        'Reply JSON only: {"u": [0.05, 0.90, or3, or4], "recovery_note": "<two sentences>"}.'
    )
    body = await create_response(settings.MODEL_WONDER, prompt, reasoning_effort="low", timeout=60.0)
    text = response_text(body)
    parsed = parse_json_block(text) or {}
    u = _clip_u(parsed.get("u") or [0.05, 0.90, 0.5, 0.5], HEADLINE_LOCKS)
    played = _play_post_jam(rain, u)
    check = replay(rain, played["orifice"], HEADLINE_LOCKS, HEADLINE_JAM_AT)
    record = {
        "rain": "DS-1482 runoff x 2.2 on every basin",
        "locks": {"OR1": 0.05, "OR2": 0.90},
        "jam_at_step": HEADLINE_JAM_AT,
        "grid_shown_in_prompt": False,
        "model": settings.MODEL_WONDER,
        "response_id": body.get("id"),
        "latency_ms": body.get("_latency_ms"),
        "depth_at_jam": depth_at_jam,
        "named_laws": laws_summary,
        "proposed_u": u,
        "recovery_note": parsed.get("recovery_note"),
        "cso_gallons": played["cso_gallons"],
        "street_gallons": played["street_gallons"],
        "replay_cso_gallons": check["cso_gallons"],
        "replay_street_gallons": check["street_gallons"],
        "orifice": played["orifice"],
    }
    OUT.write_text(json.dumps(record, indent=2), encoding="utf-8")
    raw = OUT.read_text(encoding="utf-8")
    print("response_id", record["response_id"], "latency_ms", record["latency_ms"])
    print("proposed_u", record["proposed_u"])
    print("cso_gallons", record["cso_gallons"], "street_gallons", record["street_gallons"])
    print("recovery_note", record["recovery_note"])
    print("leaks", "nvapi-" in raw or "LLM_" in raw)


if __name__ == "__main__":
    asyncio.run(main())
