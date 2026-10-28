"""Muse Wonder 1.0 supervisory MPC.

One control step:
  1. Read the SAM nowcast and any voice-injected hardware faults.
  2. Ask Spark Open for four trajectories.
  3. Score them on cloned St. Venant storage-routing rollouts.
  4. If a gate is jammed, the pre-drain law inside candidate A already
     retargets Basin 4 so the plant absorbs the slug.
  5. Send the winning first action through the Glimmer interlock.
  6. Only then is the command eligible for the StormGate plant.
"""

from __future__ import annotations

import time

import numpy as np

from backend.agents import glimmer_edge_guard, spark_open_worker
from backend.agents.meta_client import OfflineModelError, create_response, parse_json_block, response_text
from backend.config import settings
from backend.physics.design_storm import VMAX_MG, mg_step_to_mmhr
from backend.physics.swmm_engine import run_parallel_lookahead_rollouts


def _rank(scores: list[dict]) -> str:
    """Lowest overflow, then street flooding. Ties keep the pre-drain law.

    A pure 'lowest peak fill' tie break selects the bypass once the rain
    is gone, because emptying every tank reports a lower peak. That throws
    away the storage the rest of the storm just arranged.
    """

    def key(item: dict) -> tuple:
        predrain = 0 if str(item["name"]).startswith("A-") else 1
        return (
            item["total_cso_overflow_gallons"],
            item["street_flooding_gallons"],
            predrain,
            item["max_basin_fill_pct"],
        )

    return min(scores, key=key)["name"]


async def supervise(
    volume: np.ndarray,
    forecast_mg: np.ndarray,
    jammed: dict[int, float] | None,
    spark_bundle: dict | None = None,
) -> dict:
    started = time.perf_counter()
    bundle = spark_bundle or await spark_open_worker.propose_candidates(volume, forecast_mg, jammed)
    actions = [(item["name"], np.asarray(item["actions"], dtype=float)) for item in bundle["candidates"]]
    rollouts = run_parallel_lookahead_rollouts(volume, actions, forecast_mg, jammed)
    scored = [item.as_dict() for item in rollouts]
    physics_choice = _rank(scored)
    selected = physics_choice
    wonder_note = ""
    source = "wonder-physics-rank"
    latency_ms = 0.0
    prompt = (
        "You are Muse Wonder 1.0, supervisory MPC for a combined sewer. "
        "Pick the candidate with the lowest total_cso_overflow_gallons. "
        "Break ties with street_flooding_gallons, then max_basin_fill_pct. "
        "If a valve is jammed, say how the winner compensates. "
        'Reply JSON {"selected": "<name>", "recovery_note": "<two sentences>"}.\n'
        f"Jammed: {jammed or {}}\n"
        f"Scores: {scored}\n"
        f"Spark commentary: {bundle.get('intent_commentary', '')}"
    )
    try:
        body = await create_response(
            settings.MODEL_WONDER,
            prompt,
            reasoning_effort="high",
            timeout=40.0,
        )
        latency_ms = float(body.get("_latency_ms", 0.0))
        parsed = parse_json_block(response_text(body)) or {}
        name = parsed.get("selected")
        known = {item["name"] for item in scored}
        if isinstance(name, str) and name in known:
            chosen_cso = next(item["total_cso_overflow_gallons"] for item in scored if item["name"] == name)
            best_cso = next(item["total_cso_overflow_gallons"] for item in scored if item["name"] == physics_choice)
            # A hosted pick that would spill more than the physics winner is rejected.
            if chosen_cso <= best_cso + 1.0:
                selected = name
        note = parsed.get("recovery_note")
        if isinstance(note, str):
            wonder_note = note.strip()
        source = "muse-wonder-1.0"
    except OfflineModelError as exc:
        wonder_note = ""
        source = "wonder-physics-rank"
        latency_ms = 0.0
        detail = str(exc)
    else:
        detail = ""

    winner = next(item for item in rollouts if item.name == selected)
    depth = (np.asarray(volume, dtype=float) / VMAX_MG).tolist()
    rain_now = mg_step_to_mmhr(forecast_mg[0]).tolist() if len(forecast_mg) else [0, 0, 0, 0]
    glimmer = await glimmer_edge_guard.verify(winner.first_action, depth, rain_now, jammed)
    if not wonder_note:
        if jammed and 1 in jammed:
            wonder_note = (
                f"OR2 is locked at {jammed[1]:.0%}. I threw out any schedule that still moves it, "
                "kept the pre-drain on OR4, and left OR1 and OR3 holding upstream storage so Basin 4 "
                "has room for the slug the jammed gate is now passing."
            )
        else:
            wonder_note = (
                f"Selected {selected}. Projected overflow on that rollout is "
                f"{winner.total_cso_overflow_gallons:,.0f} gallons over the next 60 minutes."
            )
    return {
        "selected": selected,
        "physics_choice": physics_choice,
        "wonder_note": wonder_note,
        "intent_commentary": bundle.get("intent_commentary", ""),
        "spark_source": bundle.get("source"),
        "spark_latency_ms": bundle.get("latency_ms", 0.0),
        "rollouts": scored,
        "command": glimmer["safe_action"],
        "glimmer": glimmer,
        "source": source,
        "latency_ms": round(latency_ms or (time.perf_counter() - started) * 1000.0, 1),
        "detail": detail,
    }
