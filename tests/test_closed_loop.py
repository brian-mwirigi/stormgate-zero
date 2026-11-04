"""Replay the closed-loop Spark schedule and the radar read. No network."""

from __future__ import annotations

import json

from backend.config import ROOT
from backend.physics.frontier import HEADLINE_JAM_AT, HEADLINE_LOCKS, headline_rain, replay

LOOP = ROOT / "traces" / "double_lock_closed_loop.json"
RADAR = ROOT / "traces" / "glimmer_radar.json"


def test_closed_loop_spark_schedule_holds_at_zero():
    payload = json.loads(LOOP.read_text(encoding="utf-8"))
    steps = payload["steps"]
    assert len(steps) == 18
    ids = []
    for step in steps:
        assert step["origin"] == "muse-spark-1.3"
        assert step["turn2"] is None
        assert step["applied"] == step["best_probe_u"]
        assert step["chosen_gal"] == step["best_probe_gal"]
        ids.append(step["turn1"]["response_id"])
    assert len(set(ids)) == 18
    assert ids[0] == "resp_6ae9e477f80e73f48f264cc5"
    assert ids[-1] == "resp_6ae9e54995a7cf28d83b49cc"
    scored = replay(headline_rain(), [step["applied"] for step in steps], HEADLINE_LOCKS, HEADLINE_JAM_AT)
    assert scored["cso_gallons"] == 0.0
    assert scored["street_gallons"] == 0.0
    assert payload["cso_gallons"] == 0.0
    raw = LOOP.read_text(encoding="utf-8")
    assert "nvapi-" not in raw
    assert "LLM_" not in raw


UNAIDED = ROOT / "traces" / "wonder_unaided_recovery.json"


def test_unaided_wonder_off_grid_vector_holds_at_zero():
    payload = json.loads(UNAIDED.read_text(encoding="utf-8"))
    assert payload["grid_shown_in_prompt"] is False
    assert payload["response_id"] == "resp_6ae9f0ee5b7721d9ff6a4da4"
    assert payload["proposed_u"] == [0.05, 0.9, 0.12, 0.9]
    scored = replay(headline_rain(), payload["orifice"], HEADLINE_LOCKS, HEADLINE_JAM_AT)
    assert scored["cso_gallons"] == 0.0
    assert scored["street_gallons"] == 0.0
    raw = UNAIDED.read_text(encoding="utf-8")
    assert "nvapi-" not in raw
    assert "LLM_" not in raw


def test_glimmer_named_the_heaviest_ida_quadrant():
    payload = json.loads(RADAR.read_text(encoding="utf-8"))
    parsed = json.loads(payload["content"])
    assert payload["finish_reason"] == "stop"
    assert payload["response_id"] == "8ad068e1ef1cadad"
    assert payload["hottest_by_mosaic"] == "SU2"
    assert payload["mosaic_mmhr"]["SU2"] > payload["mosaic_mmhr"]["SU1"]
    assert parsed["hottest_quadrant"] == "SW"
    assert parsed["basin"] == "SU2"
    raw = RADAR.read_text(encoding="utf-8")
    assert "nvapi-" not in raw
    assert "LLM_" not in raw


def test_double_lock_episode_tab_replays_to_zero():
    import asyncio

    from backend.episode import Episode
    from backend.physics.storm_catalog import select

    async def _run():
        ep = Episode()
        await ep.use_storm("double-lock")
        for _ in range(18):
            await ep.step_once()
        st = ep.public_state()
        assert st["done"] is True
        assert st["cso_baseline_gal"] in (26_498_221, 26_498_222)
        assert st["cso_stormgate_gal"] == 0
        assert st["street_stormgate_gal"] == 0.0
        assert st["models"]["muse-wonder-1.0"]["status"] == "LIVE"
        select("ds-1482")

    asyncio.run(_run())

