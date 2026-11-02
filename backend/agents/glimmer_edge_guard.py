"""Muse Glimmer 30B edge safety interlock.

Runs conceptually at the basin substation: one local check before a
command is allowed onto the actuators. The invariant from the control
spec is enforced in code so a hosted-model miss cannot open a weir.

    if depth > 0.92 and orifice < 0.25 and inflow > 35 mm/hr:
        force that orifice to 0.60, unless the gate is mechanically jammed.
"""

from __future__ import annotations

from backend.agents.meta_client import OfflineModelError, create_response, parse_json_block, response_text
from backend.config import settings

FREEBOARD = 0.92
MIN_SAFE_ORIFICE = 0.25
FORCE_ORIFICE = 0.60
RAIN_TRIP_MMHR = 35.0


def local_interlock(
    action: list[float],
    depth: list[float],
    inflow_mmhr: list[float],
    jammed: dict[int, float] | None = None,
) -> dict:
    jammed = jammed or {}
    safe = [float(v) for v in action]
    notes: list[str] = []
    adjusted = False
    for index in range(4):
        if index in jammed:
            safe[index] = float(jammed[index])
            notes.append(f"OR{index + 1} is mechanically locked at {jammed[index]:.0%} and cannot be moved.")
            continue
        hot = float(inflow_mmhr[index]) > RAIN_TRIP_MMHR if index < len(inflow_mmhr) else False
        if float(depth[index]) > FREEBOARD and safe[index] < MIN_SAFE_ORIFICE and hot:
            safe[index] = FORCE_ORIFICE
            adjusted = True
            notes.append(
                f"SU{index + 1} is at {float(depth[index]):.0%} with {float(inflow_mmhr[index]):.0f} mm/hr "
                f"inbound and the gate below {MIN_SAFE_ORIFICE:.0%}. Forcing OR{index + 1} to {FORCE_ORIFICE:.0%} "
                "to protect upstream freeboard."
            )
        elif float(depth[index]) > 0.97 and safe[index] < 0.90:
            safe[index] = 1.0
            adjusted = True
            notes.append(f"SU{index + 1} is on the crown. Opening OR{index + 1} fully.")
    if not notes:
        notes.append(
            "Local freeboard holds: no basin is above 92% with a pinched gate under heavy inflow. "
            "Proposed orifice vector passes."
        )
    return {
        "approved": not adjusted,
        "safe_action": [round(v, 4) for v in safe],
        "glimmer_cot_summary": " ".join(notes),
        "source": "glimmer-local-invariant",
        "latency_ms": 0.0,
    }


async def verify(
    action: list[float],
    depth: list[float],
    inflow_mmhr: list[float],
    jammed: dict[int, float] | None = None,
    hosted: bool = False,
) -> dict:
    """Enforce the invariant locally, then ask Glimmer to phrase the ruling."""
    ruling = local_interlock(action, depth, inflow_mmhr, jammed)
    if not hosted:
        return ruling
    prompt = (
        "You are Muse Glimmer, the single-GPU edge safety guard at a sewer basin. "
        "The numeric interlock already ran. Explain the ruling in two sentences for a "
        "plant operator. Reply JSON {\"glimmer_cot_summary\": \"...\"}. "
        f"Ruling: approved={ruling['approved']} action={ruling['safe_action']} "
        f"depth={['%.2f' % d for d in depth]} rain_mmhr={['%.1f' % r for r in inflow_mmhr]} "
        f"draft={ruling['glimmer_cot_summary']}"
    )
    try:
        body = await create_response(
            settings.MODEL_GLIMMER,
            prompt,
            open_weight=True,
            timeout=25.0,
        )
        parsed = parse_json_block(response_text(body)) or {}
        summary = parsed.get("glimmer_cot_summary")
        if isinstance(summary, str) and len(summary) > 20:
            ruling["glimmer_cot_summary"] = summary.strip()
        ruling["source"] = "muse-glimmer-30b"
        ruling["latency_ms"] = body.get("_latency_ms", 0.0)
    except OfflineModelError as exc:
        ruling["detail"] = str(exc)
    return ruling
