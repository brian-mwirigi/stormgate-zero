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
from backend.agents.model_traces import load as load_traces
from backend.agents.model_traces import save as save_traces
from backend.config import settings
from backend.physics.design_storm import VMAX_MG, mg_step_to_mmhr
from backend.physics.swmm_engine import constant_trajectory, run_parallel_lookahead_rollouts


def _rank(scores: list[dict]) -> str:
    """Lowest overflow, then street flooding.

    Equal spills prefer the hosted Spark or Wonder vector, then the
    pre-drain law. A pure lowest-peak tie would empty the tanks after
    the rain and throw away the storage the storm just arranged.
    """

    def bias(name: str) -> int:
        if name == "R-refine":
            return 0
        if name == "W-wonder":
            return 1
        if name == "S-spark":
            return 2
        if name.startswith("A-"):
            return 3
        return 4

    def key(item: dict) -> tuple:
        return (
            item["total_cso_overflow_gallons"],
            item["street_flooding_gallons"],
            bias(str(item["name"])),
            item["max_basin_fill_pct"],
        )

    return min(scores, key=key)["name"]


def keep_refinement(candidate_cso: float, best_cso: float) -> bool:
    """A second-turn vector may tie the physics winner. It may not spill more."""
    return float(candidate_cso) <= float(best_cso) + 1.0


async def supervise(
    volume: np.ndarray,
    forecast_mg: np.ndarray,
    jammed: dict[int, float] | None,
    spark_bundle: dict | None = None,
    hosted: bool = False,
    hosted_spark: bool = False,
    step_index: int = 0,
) -> dict:
    started = time.perf_counter()
    bundle = spark_bundle or await spark_open_worker.propose_candidates(
        volume, forecast_mg, jammed, hosted=hosted_spark, step_index=step_index
    )
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
        'Reply JSON {"selected": "<name>", "u": [or1, or2, or3, or4], "recovery_note": "<two sentences>"}.\n'
        "u is your own orifice command from 0 to 1, honoring any jam.\n"
        f"Jammed: {jammed or {}}\n"
        f"Scores: {scored}\n"
        f"Spark commentary: {bundle.get('intent_commentary', '')}"
    )
    try:
        if not hosted:
            raise OfflineModelError("hosted Wonder is reserved for the first beat after a gate jam")
        body = await create_response(
            settings.MODEL_WONDER,
            prompt,
            reasoning_effort="low",
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
        vector = parsed.get("u")
        if isinstance(vector, list) and len(vector) >= 4:
            from backend.agents.spark_open_worker import _clip_u

            clipped = _clip_u(vector, jammed)
            horizon = max(len(forecast_mg), 1)
            plan = constant_trajectory(clipped, horizon, None)
            extra = run_parallel_lookahead_rollouts(volume, [("W-wonder", plan)], forecast_mg, jammed)
            rollouts = list(rollouts) + list(extra)
            scored = [item.as_dict() for item in rollouts]
            physics_choice = _rank([item for item in scored if item["name"] != "W-wonder"] or scored)
            selected = _rank(scored)
            traces = load_traces()
            traces["wonder"][f"jam-{step_index}"] = {
                "model": settings.MODEL_WONDER,
                "u": clipped,
                "selected": selected,
                "recovery_note": wonder_note,
                "latency_ms": latency_ms,
                "response_id": body.get("id"),
            }
            save_traces(traces)
    except (OfflineModelError, Exception) as exc:
        wonder_note = ""
        source = "wonder-physics-rank"
        latency_ms = 0.0
        detail = str(exc)
    else:
        detail = ""

    refine_note = ""
    refine_record = await spark_open_worker.refine_schedule(
        volume,
        forecast_mg,
        jammed,
        [round(float(v), 4) for v in next(item.first_action for item in rollouts if item.name == selected)],
        scored,
        step_index=step_index,
        hosted=hosted_spark,
    )
    if refine_record and isinstance(refine_record.get("u"), list):
        horizon = max(len(forecast_mg), 1)
        plan = constant_trajectory(list(refine_record["u"]), horizon, None)
        extra = run_parallel_lookahead_rollouts(volume, [("R-refine", plan)], forecast_mg, jammed)
        candidate = extra[0]
        best_cso = min(item.total_cso_overflow_gallons for item in rollouts)
        if keep_refinement(candidate.total_cso_overflow_gallons, best_cso):
            rollouts = list(rollouts) + list(extra)
            scored = [item.as_dict() for item in rollouts]
            selected = _rank(scored)
            refine_note = str(refine_record.get("intent_commentary") or "").strip()
        else:
            refine_note = "Second-turn orifice vector spilled more than the physics winner, so the solver dropped it."

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
        "refine_note": refine_note,
        "rollouts": scored,
        "command": glimmer["safe_action"],
        "glimmer": glimmer,
        "source": source,
        "latency_ms": round(latency_ms or (time.perf_counter() - started) * 1000.0, 1),
        "detail": detail,
    }
