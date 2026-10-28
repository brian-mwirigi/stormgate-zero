"""Scorecard and closed-loop MPC invariants for design storm DS-1482."""

import asyncio

from backend.episode import Episode
from backend.physics.swmm_engine import run_episode, run_parallel_lookahead_rollouts
from backend.physics.swmm_engine import forecast_window
from backend.agents.spark_open_worker import local_candidates
from backend.physics.design_storm import VMAX_MG, INIT_FRACTION


def test_local_rule_spills_exactly_14820000_gallons():
    result = run_episode("local")
    assert round(result["cso_gallons"]) == 14_820_000
    assert result["street_gallons"] == 0


def test_stormgate_contains_the_storm_including_a_jammed_gate():
    clean = run_episode("stormgate")
    jammed = run_episode("stormgate", jammed_at=8)
    assert clean["cso_gallons"] == 0
    assert jammed["cso_gallons"] == 0
    assert clean["max_depth"][3] < 1.0
    assert jammed["max_depth"][3] < 1.0
    # Pre-drain actually empties the downstream basin before the crest.
    assert clean["min_depth"][3] < 0.20
    assert clean["max_depth"][0] > 0.80


def test_uncontrolled_spills_less_than_the_float_switch():
    open_gates = run_episode("uncontrolled")
    local = run_episode("local")
    assert open_gates["cso_gallons"] > 1_000_000
    assert open_gates["cso_gallons"] < local["cso_gallons"]


def test_rollouts_rank_predrain_first():
    volume = VMAX_MG * INIT_FRACTION
    forecast = forecast_window(0, 12)
    bundle = local_candidates(volume, forecast, None)
    actions = [(item["name"], __import__("numpy").asarray(item["actions"])) for item in bundle["candidates"]]
    scores = run_parallel_lookahead_rollouts(volume, actions, forecast, None)
    winner = min(scores, key=lambda item: item.total_cso_overflow_gallons)
    assert winner.name == "A-predrain"
    assert winner.total_cso_overflow_gallons == 0


def test_closed_loop_supervisor_matches_the_scorecard():
    episode = Episode()

    async def _run() -> None:
        for _ in range(18):
            await episode.step_once()

    asyncio.run(_run())
    assert round(episode.sim.baseline.cso_mg * 1_000_000) == 14_820_000
    assert episode.sim.stormgate.cso_mg == 0
    assert episode.sim.stormgate.depth_history[-1][0] > 0.7
    assert max(row[3] for row in episode.sim.stormgate.depth_history) > 0.85
    assert episode.decision["selected"] == "A-predrain"
