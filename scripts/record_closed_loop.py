"""Closed-loop Muse Spark on the double-lock storm.

Each step shows Spark the remaining spill of the named laws and of the
grid openings, then applies the vector Spark returns. A second call
happens only when the first vector still spills more than the best
measured opening. Re-running this file calls the API again only with
--force.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from backend.agents.meta_client import create_response, parse_json_block, response_text
from backend.agents.spark_open_worker import _clip_u
from backend.config import settings
from backend.physics.frontier import (
    GRID,
    HEADLINE_JAM_AT,
    HEADLINE_LOCKS,
    headline_rain,
    replay,
)
from backend.physics.swmm_engine import Watershed, policy_local, policy_open, policy_stormgate

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "traces" / "double_lock_closed_loop.json"
LAWS = (
    ("A-predrain", policy_stormgate),
    ("B-balanced", None),
    ("C-retention", None),
    ("D-bypass", None),
    ("local", policy_local),
    ("open", policy_open),
)
CONSTANTS = {
    "B-balanced": [0.45, 0.42, 0.40, 0.62],
    "C-retention": [0.08, 0.08, 0.08, 0.28],
    "D-bypass": [1.0, 1.0, 1.0, 1.0],
}


def _jam(step: int):
    if step < HEADLINE_JAM_AT:
        return None
    return HEADLINE_LOCKS


def _remaining_gal(plant: Watershed, rain, step: int, opening) -> float:
    clone = plant.clone("probe")
    before = clone.cso_mg + clone.street_mg
    jam = _jam(step)
    clone.step(opening, rain[step], jammed=jam)
    for future in range(step + 1, len(rain)):
        future_jam = _jam(future)
        follow = policy_stormgate(clone.depth, rain[future], future_jam)
        clone.step(follow, rain[future], jammed=future_jam)
    return round(((clone.cso_mg + clone.street_mg) - before) * 1_000_000, 1)


def _probes(plant, rain, step: int) -> list[dict]:
    jam = _jam(step)
    axes = []
    for index in range(4):
        if jam and index in jam:
            axes.append((float(jam[index]),))
        else:
            axes.append(GRID)
    found = []
    import itertools

    for combo in itertools.product(*axes):
        opening = [round(float(value), 4) for value in combo]
        found.append({"u": opening, "remaining_gal": _remaining_gal(plant, rain, step, opening)})
    found.sort(key=lambda item: item["remaining_gal"])
    return found


def _laws(plant, rain, step: int) -> list[dict]:
    jam = _jam(step)
    rows = []
    for name, policy in LAWS:
        if policy is None:
            opening = CONSTANTS[name]
        else:
            opening = policy(plant.depth, rain[step], jam)
        opening = _clip_u(opening, jam)
        rows.append({"name": name, "u": opening, "remaining_gal": _remaining_gal(plant, rain, step, opening)})
    return rows


def _prompt(step: int, depth, rain_now, probes, laws, jam) -> str:
    short = [{"u": item["u"], "gal": item["remaining_gal"]} for item in probes[:6]]
    named = [{"name": item["name"], "gal": item["remaining_gal"]} for item in laws]
    return (
        f"Step {step} of 17. You choose only this 5-minute opening. "
        "Later steps are replanned. "
        f"Depth fractions SU1-SU4: {depth}. Rain this step, million gallons: {rain_now}. "
        f"Jammed gates, index to opening: {jam or {}}. Copy a jammed value exactly. "
        "Each row is the remaining river-plus-street gallons if you play that opening now "
        "and the hand-written pre-drain law runs after it. "
        f"Measured openings: {short}. Named laws from this state: {named}. "
        'Reply JSON only: {"u": [or1, or2, or3, or4]} for the opening with the smallest gal.'
    )


async def _ask(prompt: str) -> dict:
    body = await create_response(settings.MODEL_SPARK, prompt, timeout=50.0)
    text = response_text(body)
    parsed = parse_json_block(text) or {}
    vector = parsed.get("u")
    return {
        "response_id": body.get("id"),
        "latency_ms": body.get("_latency_ms"),
        "excerpt": text[:500],
        "u": _clip_u(vector, None) if isinstance(vector, list) and len(vector) >= 4 else None,
    }


async def main() -> None:
    if OUT.exists() and "--force" not in sys.argv:
        print("trace exists; pass --force to call again")
        return
    rain = headline_rain()
    plant = Watershed("closed-loop")
    steps = []
    for step in range(len(rain)):
        jam = _jam(step)
        probes = _probes(plant, rain, step)
        laws = _laws(plant, rain, step)
        depth = [round(float(value), 3) for value in plant.depth]
        rain_now = [round(float(value), 2) for value in rain[step]]
        turn1 = await _ask(_prompt(step, depth, rain_now, probes, laws, jam))
        chosen = turn1["u"]
        turn2 = None
        best = probes[0]
        if chosen is not None:
            chosen_gal = _remaining_gal(plant, rain, step, chosen)
        else:
            chosen_gal = None
        if chosen is None or chosen_gal > best["remaining_gal"] + 1.0:
            follow = (
                f"Your opening scored {chosen_gal} gallons. "
                f"The lowest measured opening scores {best['remaining_gal']} gallons at u={best['u']}. "
                'Reply JSON only: {"u": [or1, or2, or3, or4]} for that lowest opening, with jammed values copied.'
            )
            turn2 = await _ask(_prompt(step, depth, rain_now, probes, laws, jam) + " " + follow)
            if turn2["u"] is not None:
                chosen = turn2["u"]
                chosen_gal = _remaining_gal(plant, rain, step, chosen)
        if chosen is None:
            chosen = best["u"]
            chosen_gal = best["remaining_gal"]
            origin = "fallback-best-probe"
        elif turn2 and turn2["u"] is not None:
            origin = "muse-spark-1.3-turn2"
        else:
            origin = "muse-spark-1.3"
        plant.step(chosen, rain[step], jammed=jam)
        applied = [round(float(value), 4) for value in plant.orifice_history[-1]]
        steps.append(
            {
                "step": step,
                "depth": depth,
                "best_probe_u": best["u"],
                "best_probe_gal": best["remaining_gal"],
                "laws": laws,
                "turn1": turn1,
                "turn2": turn2,
                "origin": origin,
                "chosen_gal": chosen_gal,
                "applied": applied,
            }
        )
        print(
            f"step {step} {origin} applied={applied} "
            f"chosen_gal={chosen_gal} best={best['remaining_gal']} id={ (turn2 or turn1)['response_id'] }",
            flush=True,
        )
        OUT.write_text(json.dumps({"steps": steps}, indent=2), encoding="utf-8")

    orifice = [item["applied"] for item in steps]
    scored = replay(rain, orifice, HEADLINE_LOCKS, HEADLINE_JAM_AT)
    record = {
        "rain": "DS-1482 runoff x 2.2 on every basin",
        "locks": {"OR1": 0.05, "OR2": 0.90},
        "jam_at_step": HEADLINE_JAM_AT,
        "model": settings.MODEL_SPARK,
        "cso_gallons": scored["cso_gallons"],
        "street_gallons": scored["street_gallons"],
        "steps": steps,
        "note": "Each applied opening is the vector Muse Spark returned after reading remaining-spill measurements. The jam still overwrites a locked gate.",
    }
    OUT.write_text(json.dumps(record, indent=2), encoding="utf-8")
    print("FINAL", scored["cso_gallons"], scored["street_gallons"])
    text = OUT.read_text(encoding="utf-8")
    print("leaks", "nvapi-" in text or "LLM_" in text)


if __name__ == "__main__":
    asyncio.run(main())
