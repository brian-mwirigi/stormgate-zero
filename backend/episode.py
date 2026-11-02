"""Closed-loop episode: radar, voice faults, Wonder, Spark, Glimmer, hydraulics."""

from __future__ import annotations

import asyncio
from typing import Any

import numpy as np

from backend.agents.sam_radar_tracker import radar_snapshot
from backend.agents.voice_scada_bridge import ingest_transcript
from backend.agents.wonder_mpc_supervisor import supervise
from backend.config import settings
from backend.physics.design_storm import INIT_FRACTION
from backend.physics.swmm_engine import DualSimulation

JAM_LINE = "Operator 4: Sluice Gate 2 is mechanically jammed at 50 percent open."


class Episode:
    def __init__(self) -> None:
        self.sim = DualSimulation()
        self.running = False
        self.transcript: list[dict] = []
        self.faults: list[dict] = []
        self.decision: dict[str, Any] = {}
        self.radar: dict[str, Any] = {}
        self.models: dict[str, dict] = {
            "sam-3.1": {"status": "STANDBY", "latency_ms": None},
            "muse-wonder-1.0": {"status": "STANDBY", "latency_ms": None},
            "muse-spark-open": {"status": "STANDBY", "latency_ms": None},
            "muse-glimmer-30b": {"status": "STANDBY", "latency_ms": None},
            "muse-voice-transcribe-1.0": {"status": "STANDBY", "latency_ms": None},
            "muse-image-1.0": {"status": "STANDBY", "latency_ms": None},
        }
        self.outfall_ready = False
        self._wonder_calls = 0
        self._jam_wonder = False
        self.lock = asyncio.Lock()
        self._task: asyncio.Task | None = None
        self._subscribers: set[asyncio.Queue] = set()
        self.radar = radar_snapshot(0, 0.0)
        self._mark_sam()

    def _mark_sam(self) -> None:
        # The radar tape is seeded locally. A SAM video call is not on the 1-second loop.
        self.models["sam-3.1"] = {"status": "GEOMETRIC FALLBACK", "latency_ms": None}

    def _allow_hosted_wonder(self) -> bool:
        """One hosted Wonder call, on the first beat after a gate jam. The loop stays local."""
        if not settings.meta_enabled or self._wonder_calls >= max(settings.HOSTED_BUDGET, 0):
            return False
        if not self.sim.jammed or self._jam_wonder:
            return False
        self._wonder_calls += 1
        self._jam_wonder = True
        return True

    def subscribe(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=1)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        self._subscribers.discard(queue)

    async def publish(self) -> None:
        payload = self.public_state()
        for queue in list(self._subscribers):
            if queue.full():
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            await queue.put(payload)

    def public_state(self) -> dict:
        glimmer = self.decision.get("glimmer") or {}
        return {
            "t_min": self.sim.step_index * settings.STEP_MINUTES,
            "step": self.sim.step_index,
            "steps_total": settings.EPISODE_STEPS,
            "running": self.running,
            "done": self.sim.done,
            "cso_baseline_gal": int(round(self.sim.baseline.cso_mg * 1_000_000)),
            "cso_stormgate_gal": int(round(self.sim.stormgate.cso_mg * 1_000_000)),
            "street_baseline_gal": round(self.sim.baseline.street_mg * 1_000_000, 1),
            "street_stormgate_gal": round(self.sim.stormgate.street_mg * 1_000_000, 1),
            "baseline_depth": [round(float(v), 4) for v in self.sim.baseline.depth],
            "stormgate_depth": [round(float(v), 4) for v in self.sim.stormgate.depth],
            "baseline_orifice": [round(float(v), 4) for v in (self.sim.baseline.orifice_history[-1] if self.sim.baseline.orifice_history else [1, 1, 1, 0.02])],
            "stormgate_orifice": [round(float(v), 4) for v in (self.sim.stormgate.orifice_history[-1] if self.sim.stormgate.orifice_history else [0.04, 0.04, 0.04, 1])],
            "initial_depth": [round(float(v), 4) for v in INIT_FRACTION],
            "jammed": {f"OR{index + 1}": setting for index, setting in self.sim.jammed.items()},
            "forecast_mm_hr": self.radar.get("forecast_mm_hr", {}),
            "coverage": self.radar.get("coverage", {}),
            "cores": self.radar.get("cores", []),
            "object_prompt": self.radar.get("object_prompt", ""),
            "rollouts": self.decision.get("rollouts", []),
            "selected": self.decision.get("selected"),
            "commentary": self.decision.get("intent_commentary", "Waiting for the first radar beat."),
            "wonder_note": self.decision.get("wonder_note", ""),
            "glimmer": {
                "approved": glimmer.get("approved", True),
                "summary": glimmer.get("glimmer_cot_summary", "Edge interlock has not run."),
                "source": glimmer.get("source"),
            },
            "models": self.models,
            "transcript": self.transcript[-12:],
            "faults": self.faults[-8:],
            "depth_history": {
                "baseline": self.sim.baseline.depth_history[-36:],
                "stormgate": self.sim.stormgate.depth_history[-36:],
            },
            "outfall_ready": self.outfall_ready,
            "polygons": {name: list(box) for name, box in settings.SUBCATCHMENT_POLYGONS.items()},
        }

    async def reset(self) -> None:
        async with self.lock:
            self.sim.reset()
            self.running = False
            self.transcript = []
            self.faults = []
            self.decision = {}
            self.outfall_ready = False
            self.radar = radar_snapshot(0, 0.0)
            self._mark_sam()
        await self.publish()

    async def start(self) -> None:
        if self.sim.done:
            await self.reset()
        self.running = True
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._loop())
        await self.publish()

    async def pause(self) -> None:
        self.running = False
        await self.publish()

    async def _loop(self) -> None:
        while self.running:
            if self.sim.done:
                await self.publish()
                await asyncio.sleep(4.0)
                if not self.running:
                    break
                async with self.lock:
                    self.sim.reset()
                    self.decision = {}
                    self.radar = radar_snapshot(0, 0.0)
                await self.publish()
                continue
            await self.step_once()
            await asyncio.sleep(settings.EPISODE_STEP_SECONDS)

    async def step_once(self) -> None:
        async with self.lock:
            if self.sim.done:
                self.running = False
                return
            step = self.sim.step_index
            t_min = step * settings.STEP_MINUTES
            self.radar = radar_snapshot(step, t_min)
            self._mark_sam()
            decision = await supervise(
                self.sim.stormgate.volume.copy(),
                self.radar["forecast_mg"],
                dict(self.sim.jammed) or None,
                hosted=self._allow_hosted_wonder(),
            )
            self.decision = decision
            self.models["muse-wonder-1.0"] = {
                "status": "LIVE" if decision["source"] == "muse-wonder-1.0" else "PHYSICS RANK",
                "latency_ms": decision.get("latency_ms"),
            }
            self.models["muse-spark-open"] = {
                "status": "LIVE" if decision.get("spark_source") == "muse-spark-open" else "LIBRARY",
                "latency_ms": decision.get("spark_latency_ms"),
            }
            glimmer = decision.get("glimmer") or {}
            self.models["muse-glimmer-30b"] = {
                "status": "LIVE" if glimmer.get("source") == "muse-glimmer-30b" else "LOCAL INVARIANT",
                "latency_ms": glimmer.get("latency_ms"),
            }
            self.sim.advance(np.asarray(decision["command"], dtype=float))
        await self.publish()

    async def inject_transcript(self, text: str, source: str, latency_ms: float | None = None) -> dict:
        async with self.lock:
            t_min = self.sim.step_index * settings.STEP_MINUTES
            parsed = ingest_transcript(text, t_min)
            self.transcript.extend(parsed["turns"])
            for fault in parsed["faults"]:
                self.faults.append(fault)
                if fault["type"] == "valve_jam":
                    self.sim.jammed[int(fault["orifice_index"])] = float(fault["locked_setting"])
            self.models["muse-voice-transcribe-1.0"] = {"status": source, "latency_ms": latency_ms}
            payload = {"turns": parsed["turns"], "faults": parsed["faults"], "jammed": dict(self.sim.jammed)}
        await self.publish()
        return payload

    async def inject_jam(self) -> dict:
        return await self.inject_transcript(JAM_LINE, source="FAULT INJECT")

    async def clear_jam(self) -> None:
        async with self.lock:
            self.sim.jammed.clear()
        await self.publish()


episode = Episode()
