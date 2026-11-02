"""Muse Spark Open rollout worker.

Spark proposes four orifice trajectories and an operator-facing intent
note. The note is the separate commentary channel: it is produced before
any gate moves, and it quotes the depths and the radar ETA the proposal
is actually using. Hosted Spark is asked for the same JSON when an
open-weight endpoint is configured; the physics library below is the
audit trail either way.
"""

from __future__ import annotations

import numpy as np

from backend.agents.meta_client import OfflineModelError, create_response, parse_json_block, response_text
from backend.agents.model_traces import load as load_traces
from backend.agents.model_traces import save as save_traces
from backend.agents.model_traces import spark_id
from backend.config import settings
from backend.physics.design_storm import VMAX_MG
from backend.physics.swmm_engine import constant_trajectory, feedback_trajectory

STRATEGY_NOTES = {
    "A-predrain": "pre-drain Basin 4 and hold upstream inline storage",
    "B-balanced": "throttle every orifice in proportion to its current depth",
    "C-retention": "keep gates nearly shut and spend inline storage first",
    "D-bypass": "open every gate and pass the hydrograph straight to the plant",
}


def _eta_minutes(forecast_mg: np.ndarray) -> int:
    if len(forecast_mg) == 0:
        return 0
    peak = int(np.argmax(forecast_mg[:, 3]))
    return peak * settings.STEP_MINUTES


def local_candidates(volume: np.ndarray, forecast_mg: np.ndarray, jammed: dict[int, float] | None) -> dict:
    """Four diverse trajectories. A is the pre-drain law recorded along the forecast."""
    horizon = len(forecast_mg)
    depth = np.asarray(volume, dtype=float) / VMAX_MG
    plans = [
        ("A-predrain", feedback_trajectory(volume, forecast_mg, "stormgate", jammed)),
        ("B-balanced", constant_trajectory([0.45, 0.42, 0.40, 0.62], horizon, jammed)),
        ("C-retention", constant_trajectory([0.08, 0.08, 0.08, 0.28], horizon, jammed)),
        ("D-bypass", constant_trajectory([1.0, 1.0, 1.0, 1.0], horizon, jammed)),
    ]
    eta = _eta_minutes(forecast_mg)
    d4 = float(depth[3])
    d1 = float(depth[0])
    jam_clause = ""
    if jammed and 1 in jammed:
        jam_clause = (
            f" Orifice OR2 is mechanically locked at {jammed[1]:.0%}, so every "
            "candidate keeps that column fixed and moves the spare storage onto SU1 and SU3."
        )
    menu = " ".join(f"{name} = {blurb}." for name, blurb in STRATEGY_NOTES.items())
    commentary = (
        f"Strategy A pre-drains SU4 from {d4:.0%} while the downstream core is still "
        f"{eta} minutes out, and holds OR1 so SU1 stays near {d1:.0%} instead of dumping "
        f"into the interceptor. B spreads the throttling, C banks every gallon upstream, "
        f"and D abandons storage and bets the plant can take the peak.{jam_clause} "
        f"Library: {menu}"
    )
    return {
        "candidates": [{"name": name, "actions": plan.tolist()} for name, plan in plans],
        "intent_commentary": commentary,
        "source": "spark-open-library",
        "latency_ms": 0.0,
    }


def _clip_u(values, jammed: dict[int, float] | None) -> list[float]:
    numbers = []
    for value in list(values)[:4]:
        try:
            numbers.append(min(1.0, max(0.0, float(value))))
        except (TypeError, ValueError):
            numbers.append(0.5)
    while len(numbers) < 4:
        numbers.append(0.5)
    if jammed:
        for index, locked in jammed.items():
            if isinstance(index, str):
                continue
            numbers[int(index)] = float(locked)
    return [round(v, 4) for v in numbers]


def _with_spark_vector(library: dict, vector: list[float], note: str, source: str, latency_ms: float) -> dict:
    horizon = len(library["candidates"][0]["actions"])
    plan = constant_trajectory(vector, horizon, None)
    library["candidates"].append({"name": "S-spark", "actions": plan.tolist()})
    if note:
        library["intent_commentary"] = note
    library["source"] = source
    library["latency_ms"] = latency_ms
    library["spark_u"] = vector
    return library


async def propose_candidates(
    volume: np.ndarray,
    forecast_mg: np.ndarray,
    jammed: dict[int, float] | None,
    hosted: bool = False,
    step_index: int = 0,
) -> dict:
    library = local_candidates(volume, forecast_mg, jammed)
    if not hosted:
        return library
    cached = load_traces()["spark"].get(spark_id(step_index, jammed))
    if isinstance(cached, dict) and isinstance(cached.get("u"), list):
        return _with_spark_vector(
            library,
            cached["u"],
            str(cached.get("intent_commentary") or ""),
            "muse-spark-1.3",
            float(cached.get("latency_ms") or 0.0),
        )
    depth = (np.asarray(volume, dtype=float) / VMAX_MG).round(3).tolist()
    su4 = [round(float(v), 3) for v in forecast_mg[:6, 3]] if len(forecast_mg) else []
    prompt = (
        "You are Muse Spark 1.3 on a combined-sewer controller. "
        "Propose the orifice openings for the next 5 minutes. "
        'Reply JSON only: {"u": [or1, or2, or3, or4], "intent_commentary": "<one sentence>"}. '
        "Each value is from 0 (shut) to 1 (open). "
        "Keep Basin 4 off the weir: if its forecast is rising, do not open OR4 fully, "
        "and do not dump SU1-SU3 into it. If a gate is jammed, copy its locked value. "
        f"Depth fractions SU1-SU4: {depth}. "
        f"SU4 inflow the next few steps, million gallons: {su4}. "
        f"Jammed orifices: {jammed or {}}."
    )
    try:
        body = await create_response(settings.MODEL_SPARK, prompt, timeout=25.0)
        parsed = parse_json_block(response_text(body)) or {}
        vector = parsed.get("u")
        if not isinstance(vector, list) or len(vector) < 4:
            library["detail"] = "muse-spark-1.3 returned no orifice vector"
            return library
        vector = _clip_u(vector, jammed)
        note = parsed.get("intent_commentary")
        note = note.strip() if isinstance(note, str) else ""
        latency_ms = float(body.get("_latency_ms") or 0.0)
        traces = load_traces()
        traces["spark"][spark_id(step_index, jammed)] = {
            "model": settings.MODEL_SPARK,
            "u": vector,
            "intent_commentary": note,
            "latency_ms": latency_ms,
            "response_id": body.get("id"),
        }
        save_traces(traces)
        return _with_spark_vector(library, vector, note, "muse-spark-1.3", latency_ms)
    except (OfflineModelError, Exception) as exc:
        library["detail"] = str(exc)[:300]
        return library
