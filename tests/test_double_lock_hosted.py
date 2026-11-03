"""Replay the hosted double-lock schedules. This test does not call the network."""

from __future__ import annotations

import json

from backend.config import ROOT
from backend.physics.frontier import HEADLINE_JAM_AT, HEADLINE_LOCKS, headline_rain, replay

TRACE = ROOT / "traces" / "double_lock_hosted.json"


def test_hosted_schedules_were_scored_and_rejected():
    payload = json.loads(TRACE.read_text(encoding="utf-8"))
    rain = headline_rain()
    spark = replay(rain, payload["spark_play"]["orifice"], HEADLINE_LOCKS, HEADLINE_JAM_AT)
    wonder = replay(rain, payload["wonder_play"]["orifice"], HEADLINE_LOCKS, HEADLINE_JAM_AT)
    assert spark["cso_gallons"] == 4333880.8
    assert spark["street_gallons"] == 0.0
    assert wonder["cso_gallons"] == 6966494.7
    assert wonder["street_gallons"] == 0.0
    assert spark["cso_gallons"] < payload["named"]["B-balanced"]["cso_gallons"]
    assert wonder["cso_gallons"] > payload["named"]["B-balanced"]["cso_gallons"]
    assert payload["searched"]["cso_gallons"] == 0.0
    assert payload["spark_verdict"] == "rejected-spilled-more"
    assert payload["wonder_verdict"] == "rejected-spilled-more"
    assert payload["spark"]["response_id"] == "resp_6ae9e184c25d838e5d884bcd"
    assert payload["wonder"]["response_id"] == "resp_6ae9e19fa36ac7ab266e474f"
    raw = TRACE.read_text(encoding="utf-8")
    assert "nvapi-" not in raw
    assert "LLM_" not in raw
