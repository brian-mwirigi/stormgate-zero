"""Saved Meta responses for DS-1482.

The first pass calls api.meta.ai and writes the result here. Later loops
replay that result, so a running board does not bill the same step twice.
The solver still scores the saved orifice vector before it moves a gate.
"""

from __future__ import annotations

import json
from pathlib import Path

from backend.config import ROOT

TRACE_PATH = ROOT / "traces" / "live_models.json"


def load() -> dict:
    if not TRACE_PATH.exists():
        return {"spark": {}, "sam": {}, "wonder": {}, "voice": {}}
    try:
        data = json.loads(TRACE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"spark": {}, "sam": {}, "wonder": {}, "voice": {}}
    for key in ("spark", "sam", "wonder", "voice"):
        data.setdefault(key, {})
    return data


def save(data: dict) -> None:
    TRACE_PATH.parent.mkdir(parents=True, exist_ok=True)
    TRACE_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def jam_key(jammed: dict | None) -> str:
    if not jammed:
        return ""
    parts = []
    for index, value in sorted(jammed.items(), key=lambda item: int(item[0])):
        parts.append(f"{int(index)}:{float(value):.2f}")
    return ",".join(parts)


def spark_id(step: int, jammed: dict | None) -> str:
    from backend.physics.storm_catalog import current

    suffix = f"{int(step)}|{jam_key(jammed)}"
    storm_id = current()["id"]
    if storm_id == "ds-1482":
        return suffix
    return f"{storm_id}|{suffix}"
