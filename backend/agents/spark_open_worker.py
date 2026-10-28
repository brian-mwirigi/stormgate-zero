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


async def propose_candidates(volume: np.ndarray, forecast_mg: np.ndarray, jammed: dict[int, float] | None) -> dict:
    library = local_candidates(volume, forecast_mg, jammed)
    summary = {
        "depth": (volume / np.maximum(volume, volume)).tolist() if False else None,
        "jammed": {str(k): v for k, v in (jammed or {}).items()},
        "eta_min": _eta_minutes(forecast_mg),
        "library": [item["name"] for item in library["candidates"]],
    }
    prompt = (
        "You are Muse Spark Open running as the physics commentary channel for a "
        "combined-sewer MPC. Do not invent a fifth strategy. Reply with JSON "
        '{"intent_commentary": "...", "prefer": "A-predrain"|"B-balanced"|"C-retention"|"D-bypass"}. '
        "The commentary must mention Basin 4 pre-drain timing and any jammed orifice. "
        f"Context: {summary}. Draft: {library['intent_commentary']}"
    )
    try:
        body = await create_response(settings.MODEL_SPARK_OPEN, prompt, open_weight=True, timeout=30.0)
        parsed = parse_json_block(response_text(body)) or {}
        note = parsed.get("intent_commentary")
        if isinstance(note, str) and len(note) > 40:
            library["intent_commentary"] = note.strip()
        library["source"] = "muse-spark-open"
        library["latency_ms"] = body.get("_latency_ms", 0.0)
        library["prefer"] = parsed.get("prefer")
    except OfflineModelError as exc:
        library["detail"] = str(exc)
    return library
