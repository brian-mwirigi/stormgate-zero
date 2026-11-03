"""One Spark call and one Wonder call on the double-lock storm.

The plant scores both schedules. A schedule is kept only when its spill is
within a gallon of the searched physics winner. This script is a recorder,
not part of the live loop.
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
OUT = ROOT / "traces" / "double_lock_hosted.json"


def _rows(parsed: dict | None) -> list[list[float]] | None:
    if not isinstance(parsed, dict):
        return None
    raw = parsed.get("schedule")
    if not isinstance(raw, list):
        one = parsed.get("u")
        if isinstance(one, list) and one and not isinstance(one[0], list):
            raw = [one] * 18
    if not isinstance(raw, list) or not raw:
        return None
    rows: list[list[float]] = []
    for row in raw[:18]:
        if not isinstance(row, list):
            return None
        rows.append(_clip_u(row, None))
    if len(rows) < 18:
        rows.extend([rows[-1]] * (18 - len(rows)))
    return rows


def _play(rain, rows) -> dict:
    plant = Watershed("hosted")
    applied = []
    for step, opening in enumerate(rows):
        jam = HEADLINE_LOCKS if step >= HEADLINE_JAM_AT else None
        plant.step(opening, rain[step], jammed=jam)
        applied.append([round(float(value), 4) for value in plant.orifice_history[-1]])
    return {
        "cso_gallons": round(plant.cso_mg * 1_000_000, 1),
        "street_gallons": round(plant.street_mg * 1_000_000, 1),
        "orifice": applied,
    }


def _prompt(rain, extra: str) -> str:
    table = [[round(float(value), 2) for value in row] for row in rain]
    return (
        "You are scheduling 18 gate moves, one every 5 minutes, on a 4-basin combined sewer. "
        "Each row is [OR1, OR2, OR3, OR4], each number from 0 shut to 1 open. "
        "From step 4 through step 17, OR1 is jammed at 0.05 and OR2 is jammed at 0.90. "
        "Copy those two numbers on those steps. Steps 0-3 are free. "
        "OR3 and OR4 stay free the whole storm. "
        "Rainfall per step in million gallons is [SU1, SU2, SU3, SU4]: "
        f"{table}. "
        "The float switch spills about 26.5 million gallons to the river. "
        "The hand-written pre-drain law spills about 8.5 million gallons and also floods a street. "
        "The best constant opening spills about 4.4 million gallons. "
        "Return a time-varying schedule whose river spill and street flood are both as close to zero as you can make them. "
        'Reply JSON only: {"schedule": [[u1,u2,u3,u4], ... 18 rows ...], "intent_commentary": "<one sentence>"}. '
        + extra
    )


async def _ask(model: str, prompt: str, reasoning: str | None) -> dict:
    body = await create_response(model, prompt, reasoning_effort=reasoning, timeout=90.0)
    text = response_text(body)
    parsed = parse_json_block(text)
    return {
        "model": model,
        "response_id": body.get("id"),
        "latency_ms": body.get("_latency_ms"),
        "excerpt": text[:1200],
        "commentary": (parsed or {}).get("intent_commentary") or (parsed or {}).get("recovery_note"),
        "rows": _rows(parsed),
    }


async def main() -> None:
    if OUT.exists() and "--force" not in sys.argv:
        print("trace exists; pass --force to call the API again")
        return
    rain = headline_rain()
    library = score_schedule(rain, HEADLINE_LOCKS, HEADLINE_JAM_AT)
    searched_harm = library["searched"]["cso_gallons"] + library["searched"]["street_gallons"]
    named = {}
    for name in ("local", "A-predrain", "B-balanced", "C-retention", "D-bypass"):
        named[name] = {
            "cso_gallons": library[name]["cso_gallons"],
            "street_gallons": library[name]["street_gallons"],
        }
    best_name = min(named, key=lambda name: named[name]["cso_gallons"] + named[name]["street_gallons"])

    spark = await _ask(settings.MODEL_SPARK, _prompt(rain, ""), None)
    spark_play = _play(rain, spark["rows"]) if spark["rows"] else None
    if spark_play:
        check = replay(rain, spark_play["orifice"], HEADLINE_LOCKS, HEADLINE_JAM_AT)
        spark_play["replay_cso_gallons"] = check["cso_gallons"]
        spark_play["replay_street_gallons"] = check["street_gallons"]

    spark_harm = None
    if spark_play:
        spark_harm = spark_play["cso_gallons"] + spark_play["street_gallons"]
    wonder_extra = (
        f"A colleague's schedule spilled {spark_harm} gallons of river plus street. "
        f"Best named law is {best_name} at {named[best_name]}. "
        "Do not copy a constant law. Vary OR3 and OR4 after the jam."
        if spark_harm is not None
        else "The first model returned no schedule. Propose the 18 rows yourself."
    )
    wonder = await _ask(settings.MODEL_WONDER, _prompt(rain, wonder_extra), "low")
    wonder_play = _play(rain, wonder["rows"]) if wonder["rows"] else None
    if wonder_play:
        check = replay(rain, wonder_play["orifice"], HEADLINE_LOCKS, HEADLINE_JAM_AT)
        wonder_play["replay_cso_gallons"] = check["cso_gallons"]
        wonder_play["replay_street_gallons"] = check["street_gallons"]

    def verdict(play: dict | None) -> str:
        if play is None:
            return "no-vector"
        harm = play["cso_gallons"] + play["street_gallons"]
        if harm <= searched_harm + 1.0:
            return "kept"
        return "rejected-spilled-more"

    record = {
        "rain": "DS-1482 runoff x 2.2 on every basin",
        "locks": {"OR1": 0.05, "OR2": 0.90},
        "jam_at_step": HEADLINE_JAM_AT,
        "named": named,
        "best_named": best_name,
        "searched": {
            "cso_gallons": library["searched"]["cso_gallons"],
            "street_gallons": library["searched"]["street_gallons"],
        },
        "spark": {key: spark[key] for key in ("model", "response_id", "latency_ms", "commentary", "excerpt")},
        "spark_play": spark_play,
        "spark_verdict": verdict(spark_play),
        "wonder": {key: wonder[key] for key in ("model", "response_id", "latency_ms", "commentary", "excerpt")},
        "wonder_play": wonder_play,
        "wonder_verdict": verdict(wonder_play),
        "guard": "A hosted schedule is kept only when river plus street is within 1 gallon of the searched physics winner.",
    }
    OUT.write_text(json.dumps(record, indent=2), encoding="utf-8")
    text = OUT.read_text(encoding="utf-8")
    print("best_named", best_name, named[best_name])
    print("searched", record["searched"])
    print("spark", spark["response_id"], spark["latency_ms"], record["spark_verdict"])
    if spark_play:
        print("spark_gal", spark_play["cso_gallons"], spark_play["street_gallons"])
    print("spark_commentary", spark["commentary"])
    print("wonder", wonder["response_id"], wonder["latency_ms"], record["wonder_verdict"])
    if wonder_play:
        print("wonder_gal", wonder_play["cso_gallons"], wonder_play["street_gallons"])
    print("wonder_commentary", wonder["commentary"])
    print("leaks", "nvapi-" in text or "LLM_" in text)


if __name__ == "__main__":
    asyncio.run(main())
