"""One free NVIDIA call: Muse Glimmer reads an Ida NEXRAD crop."""

from __future__ import annotations

import asyncio
import base64
import json
import sys
from pathlib import Path

from backend.agents.meta_client import _headers, _ssl_context
from backend.config import settings

ROOT = Path(__file__).resolve().parents[1]
IMAGE = ROOT / "traces" / "nexrad" / "ida-2021-newark" / "frame_02.png"
OUT = ROOT / "traces" / "glimmer_radar.json"


async def main() -> None:
    if OUT.exists() and "--force" not in sys.argv:
        print("trace exists; pass --force to call again")
        return
    encoded = base64.b64encode(IMAGE.read_bytes()).decode("ascii")
    text = (
        "This PNG is a 480x480 NEXRAD reflectivity crop centered on Newark "
        "during Hurricane Ida remnants at 00:00 UTC on 2 Sep 2021. "
        "Quadrants of this image: NW is basin SU1, SW is basin SU2, "
        "NE is basin SU3, SE is basin SU4. "
        "Which quadrant has the strongest echo? Reply JSON only with keys "
        "hottest_quadrant, basin, and operator_note."
    )
    payload_text = text
    # chat_completion sends a string. Call the endpoint with an image part directly.
    import time

    import httpx

    body_json = {
        "model": settings.glimmer_model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{encoded}"}},
                    {"type": "text", "text": payload_text},
                ],
            }
        ],
        "temperature": 0.2,
        "top_p": 0.95,
        "max_tokens": 2048,
        "stream": False,
    }
    started = time.perf_counter()
    async with httpx.AsyncClient(timeout=120.0, verify=_ssl_context()) as client:
        response = await client.post(
            f"{settings.nvidia_base_url}/chat/completions",
            headers=_headers(settings.nvidia_api_key),
            json=body_json,
        )
    latency_ms = round((time.perf_counter() - started) * 1000.0, 1)
    if response.status_code >= 400:
        print("HTTP", response.status_code, response.text[:500])
        return
    data = response.json()
    message = (data.get("choices") or [{}])[0].get("message") or {}
    usage = data.get("usage") or {}
    record = {
        "endpoint": "https://integrate.api.nvidia.com/v1/chat/completions",
        "billing": "nvidia-api-catalog-free-tier",
        "model": settings.glimmer_model,
        "image": "traces/nexrad/ida-2021-newark/frame_02.png",
        "stamp": "202109020000",
        "mosaic_mmhr": {"SU1": 14.4, "SU2": 28.08, "SU3": 9.28, "SU4": 8.55},
        "hottest_by_mosaic": "SU2",
        "response_id": data.get("id"),
        "finish_reason": (data.get("choices") or [{}])[0].get("finish_reason"),
        "latency_ms": latency_ms,
        "usage": {
            "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": usage.get("completion_tokens"),
            "total_tokens": usage.get("total_tokens"),
        },
        "content": message.get("content"),
        "reasoning_excerpt": (message.get("reasoning_content") or "")[:400],
    }
    OUT.write_text(json.dumps(record, indent=2), encoding="utf-8")
    blob = OUT.read_text(encoding="utf-8")
    print("id", record["response_id"])
    print("finish", record["finish_reason"])
    print("usage", record["usage"])
    print("content", record["content"])
    print("leaks", "nvapi-" in blob or "LLM_" in blob)


if __name__ == "__main__":
    asyncio.run(main())
