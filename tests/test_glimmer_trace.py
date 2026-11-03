"""Replay the recorded NVIDIA catalog phrasing. This test does not call the network."""

from __future__ import annotations

import asyncio
import json

from backend.agents.glimmer_edge_guard import local_interlock, verify
from backend.config import ROOT

TRACE = ROOT / "traces" / "glimmer_nvidia.json"


def test_recorded_glimmer_phrasing_matches_the_local_gate():
    payload = json.loads(TRACE.read_text(encoding="utf-8"))
    ruling = local_interlock(payload["proposed_action"], payload["depth"], payload["rain_mmhr"])
    assert ruling["safe_action"] == [0.6, 0.4, 0.4, 0.62]
    assert payload["safe_action"] == ruling["safe_action"]
    assert payload["approved"] is False
    assert payload["model"] == "meta/muse-glimmer-30b"
    assert payload["source"] == "muse-glimmer-30b"
    assert payload["finish_reason"] == "stop"
    assert payload["response_id"] == "bd76ae3ac432bcce"
    assert payload["usage"]["total_tokens"] == 848
    assert "OR1 is being forced to 60%" in payload["glimmer_cot_summary"]
    raw = TRACE.read_text(encoding="utf-8")
    assert "nvapi-" not in raw
    assert "LLM_" not in raw


def test_offline_verify_does_not_leave_the_local_interlock():
    payload = json.loads(TRACE.read_text(encoding="utf-8"))
    ruling = asyncio.run(
        verify(payload["proposed_action"], payload["depth"], payload["rain_mmhr"], hosted=True)
    )
    assert ruling["source"] == "glimmer-local-invariant"
    assert ruling["safe_action"] == [0.6, 0.4, 0.4, 0.62]
